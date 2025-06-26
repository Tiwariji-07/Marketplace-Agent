from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, HttpUrl, Field
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class Message(BaseModel):
    role: MessageRole = MessageRole.USER
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[Message]
    session_id: Optional[str] = None
    stream: bool = False
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = None

class ChatResponse(BaseModel):
    message: Message
    session_id: str
    tool_calls: Optional[List[Dict[str, Any]]] = None

class GitHubRepoRequest(BaseModel):
    url: HttpUrl
    analyze_code: bool = True
    include_issues: bool = False
    include_pull_requests: bool = False

class GitHubRepoResponse(BaseModel):
    stars: int
    contributors: List[str]
    description: str
    appname: str
    reponame: str
    features: str
    usecases: str
    codebase_analysis: Dict[str, Any]
    languages: Dict[str, int]
    license_info: Optional[Dict[str, Any]] = None
    last_updated: str

class APICallRequest(BaseModel):
    url: HttpUrl
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, str]] = None
    body: Optional[Union[Dict[str, Any], str]] = None
    auth: Optional[Dict[str, str]] = None

class APICallResponse(BaseModel):
    status_code: int
    headers: Dict[str, str]
    content: Union[Dict[str, Any], str, bytes]
    is_success: bool
    error: Optional[str] = None

class ToolResult(BaseModel):
    tool_name: str
    result: Union[Dict[str, Any], str]

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
