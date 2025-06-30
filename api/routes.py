from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
import logging
import json

from utils.config import settings
from . import models
from agents.main_agent import get_agent
from utils.session_manager import get_session_manager

router = APIRouter()
# Alias exported for main application import
api_router = router
logger = logging.getLogger(__name__)

@router.post("/chat", response_model=models.ChatResponse)
async def chat(
    request: models.ChatRequest,
    session_manager=Depends(get_session_manager),
):
    """
    Handle chat messages and return AI responses.
    """
    try:
        # Get or create session
        session_id = request.session_id or session_manager.create_session()
        
        # Get chat history from session
        chat_history = session_manager.get_chat_history(session_id)
        
        # Add new messages to history
        new_msgs = [msg.dict() for msg in request.messages]
        chat_history.extend(new_msgs)

        # Get agent response with full history
        agent = get_agent()
        response = await agent.arun(
            messages=chat_history,
            session_id=session_id,
            stream=request.stream,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        # Persist updated history (including agent reply)
        chat_history.append(response["message"])
        session_manager.update_chat_history(
            session_id=session_id,
            messages=chat_history
        )
        
        return {
            "message": response["message"],
            "session_id": session_id,
            "tool_calls": response.get("tool_calls"),
        }
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/github", response_model=models.GitHubRepoResponse)
async def analyze_github_repo(
    request: models.GitHubRepoRequest,
    session_manager=Depends(get_session_manager),
):
    """
    Analyze a GitHub repository and return structured information.
    """
    try:
        from agents.tools.git_analyzer import GitHubAnalyzer
        
        analyzer = GitHubAnalyzer()
        result = await analyzer.analyze_repository(
            url=str(request.url),
            analyze_code=request.analyze_code,
            include_issues=request.include_issues,
            include_pull_requests=request.include_pull_requests,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing GitHub repo: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/call", response_model=models.APICallResponse)
async def call_api(
    request: models.APICallRequest,
):
    """
    Make an HTTP API call based on the provided request.
    """
    try:
        from agents.tools.api_caller import APICaller
        
        caller = APICaller()
        response = await caller.call(
            url=str(request.url),
            method=request.method,
            headers=request.headers or {},
            params=request.params or {},
            body=request.body,
            auth=request.auth,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error making API call: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/image/generate", response_model=models.ImageGenResponse)
async def generate_image(request: models.ImageGenRequest):
    """Generate an app icon or banner image given a name and kind."""
    try:
        from agents.tools.image_generator import ImageGenerator
        generator = ImageGenerator()
        result = await generator.generate(name=request.name, kind=request.kind, size=request.size)
        return result
    except Exception as e:
        logger.error(f"Error generating image: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/clear")
async def clear_session(
    session_id: str,
    session_manager=Depends(get_session_manager),
):
    """
    Clear a specific session's chat history.
    """
    try:
        session_manager.clear_session(session_id)
        return {"status": "success", "message": f"Session {session_id} cleared"}
    except Exception as e:
        logger.error(f"Error clearing session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint for the API."""
    return {"status": "ok"}
