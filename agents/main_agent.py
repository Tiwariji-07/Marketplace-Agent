import os
import json
import logging
from typing import Dict, List, Optional, Any, Union, AsyncGenerator
from datetime import datetime

from langchain.agents import AgentExecutor, Tool, AgentType
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from langchain_community.chat_models import ChatOpenAI
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.agents.agent_toolkits import create_conversational_retrieval_agent
from langchain_community.agent_toolkits.github.toolkit import GitHubToolkit
from langchain_community.utilities.github import GitHubAPIWrapper
from langchain.agents.openai_functions_agent.agent_token_buffer_memory import (
    AgentTokenBufferMemory
)
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.prompts import MessagesPlaceholder
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain.agents.agent import AgentExecutor
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.schema.messages import SystemMessage

from utils.config import settings
from .tools.git_analyzer import GitHubAnalyzer
from .tools.api_caller import APICaller
# Only MessageRole is needed here; use absolute import to avoid relative-package issues
from api.models import MessageRole

logger = logging.getLogger(__name__)

# Initialize tools
github_analyzer = GitHubAnalyzer()
api_caller = APICaller()

def get_llm():
    """Initialize and return the language model."""
    return ChatOpenAI(
        model_name=settings.OPENAI_MODEL,
        temperature=0.7,
        openai_api_key=settings.OPENAI_API_KEY,
        request_timeout=60,
        max_retries=3,
    )

def get_tools() -> List[Tool]:
    """Return the list of available tools for the agent."""

    class APICallSchema(BaseModel):
        url: str = Field(..., description="Full URL to request")
        method: str = Field("GET", description="HTTP method (GET, POST, etc.)")
        headers: Dict[str, Any] | None = Field(default_factory=dict)
        params: Dict[str, Any] | None = Field(default_factory=dict)
        data: Any | None = None
        json_data: Any | None = None
        auth: Dict[str, Any] | None = None
        timeout: int | None = 30
        allow_redirects: bool | None = True
        verify_ssl: bool | None = True

    async def _call_api_tool(**kwargs):
        return await api_caller.call(**kwargs)

    analyze_repo_tool = Tool(
        name="analyze_github_repo",
        func=lambda **kwargs: "Running GitHub analysis...",  # placeholder for sync calls
        coroutine=github_analyzer.analyze_repository,
        description="""
        Analyze a GitHub repository from its URL and return structured insights.
        Accepts: url (str, required), analyze_code (bool, default True), include_issues (bool), include_pull_requests (bool).
        """,
    )

    call_api_tool = StructuredTool.from_function(
        func=_call_api_tool,
        name="call_api",
        description="Make an HTTP request to any REST endpoint and return the parsed response.",
        args_schema=APICallSchema,
        coroutine=_call_api_tool,
    )

    return [analyze_repo_tool, call_api_tool]

def get_system_prompt() -> str:
    """Return the system prompt for the agent."""
    return """
    You are a helpful AI assistant with the ability to analyze GitHub repositories and make API calls.
    You can help users with:
    1. Answering general questions and having natural conversations
    2. Analyzing GitHub repositories by providing a URL
    3. Making API calls to interact with web services
    
    When analyzing GitHub repositories, you'll receive detailed information about the codebase,
    including its structure, dependencies, and key components.
    
    When making API calls, you'll need the endpoint URL, method, and any required parameters or authentication.
    
    Be concise, helpful, and provide clear explanations of your actions.
    """

def create_agent_executor(llm=None, tools=None, **kwargs):
    """Create and return an agent executor."""
    if llm is None:
        llm = get_llm()
    
    if tools is None:
        tools = get_tools()
    
    # Define the prompt
    system_message = SystemMessage(content=get_system_prompt())
    prompt = OpenAIFunctionsAgent.create_prompt(
        system_message=system_message,
        extra_prompt_messages=[MessagesPlaceholder(variable_name="chat_history")],
    )
    
    # Create the agent
    agent = OpenAIFunctionsAgent(llm=llm, tools=tools, prompt=prompt)
    
    # Create the agent executor
    return AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        **kwargs
    )

class MultiAgent:
    """Main agent class that handles conversation and tool orchestration."""
    
    def __init__(self):
        """Initialize the agent with tools and LLM."""
        self.llm = get_llm()
        self.tools = get_tools()
        self.agent_executor = create_agent_executor(self.llm, self.tools)
        
    async def arun(
        self,
        messages: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process a list of messages and return the agent's response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            session_id: Optional session ID for maintaining conversation context
            stream: Whether to stream the response
            **kwargs: Additional arguments to pass to the agent
            
        Returns:
            Dict containing the agent's response and any tool calls
        """
        try:
            # Convert messages to LangChain message format
            chat_history = []
            last_user_message = None
            
            for msg in messages:
                # Support both plain dicts and Pydantic Message objects
                if isinstance(msg, dict):
                    role = msg.get("role")
                    content = msg.get("content", "")
                else:
                    # Assume pydantic model with attributes
                    role = getattr(msg, "role", None)
                    content = getattr(msg, "content", "")
                
                if role == MessageRole.USER:
                    last_user_message = content
                    chat_history.append(HumanMessage(content=content))
                elif role == MessageRole.ASSISTANT:
                    chat_history.append(AIMessage(content=content))
                elif role == MessageRole.SYSTEM:
                    chat_history.append(SystemMessage(content=content))
            
            if not last_user_message:
                return {
                    "message": {
                        "role": MessageRole.ASSISTANT,
                        "content": "I didn't receive any user message to process."
                    },
                    "tool_calls": None
                }
            
            # Run the agent
            result = await self.agent_executor.ainvoke({
                "input": last_user_message,
                "chat_history": chat_history[:-1] if len(chat_history) > 1 else [],
            }, **kwargs)
            
            # Process the result
            response_content = result.get('output', 'I apologize, but I encountered an error processing your request.')
            
            # Check for tool calls in the intermediate steps
            tool_calls = []
            if 'intermediate_steps' in result:
                for step in result['intermediate_steps']:
                    if len(step) >= 2 and hasattr(step[0], 'tool'):
                        tool_calls.append({
                            'tool_name': step[0].tool,
                            'tool_input': step[0].tool_input,
                            'result': step[1],
                        })
            
            return {
                "message": {
                    "role": MessageRole.ASSISTANT,
                    "content": response_content,
                },
                "tool_calls": tool_calls if tool_calls else None
            }
            
        except Exception as e:
            logger.error(f"Error in agent execution: {str(e)}", exc_info=True)
            return {
                "message": {
                    "role": MessageRole.ASSISTANT,
                    "content": f"I encountered an error while processing your request: {str(e)}"
                },
                "tool_calls": None
            }

# Singleton instance
_agent_instance = None

def get_agent() -> MultiAgent:
    """Get or create the agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = MultiAgent()
    return _agent_instance
