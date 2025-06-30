"""
Streamlit-based chat interface for the MultiAgent system.
"""
import os
import json
import streamlit as st
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
TITLE = "MultiAgent Chat"
AVATARS = {
    "user": "👤",
    "assistant": "🤖",
    "system": "⚙️",
    "tool": "🛠️"
}

def init_session_state():
    """Initialize the session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "api_available" not in st.session_state:
        st.session_state.api_available = True

def check_api_health() -> bool:
    """Check if the API is available."""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        return response.status_code == 200
    except requests.RequestException:
        return False

def send_chat_message(message: str) -> Dict[str, Any]:
    """Send a chat message to the API and return the response."""
    url = f"{API_BASE_URL}/chat"
    headers = {"Content-Type": "application/json"}
    data = {
        "messages": [{"role": "user", "content": message}],
        "session_id": st.session_state.session_id,
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        resp_json = response.json()
        if "message" in resp_json:
            return {
                "success": True,
                "response": resp_json["message"].get("content", ""),
                "tool_results": (resp_json.get("tool_calls") or []),
                "session_id": resp_json.get("session_id")
            }
        return {"success": False, "error": "Unexpected response format"}
    except requests.RequestException as e:
        return {"error": str(e), "success": False}

def display_chat_messages():
    """Display chat messages from the session state."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=AVATARS.get(message["role"], "")):
            if "content" in message:
                st.markdown(message["content"])
            if "tool_results" in message:
                for tool_result in message["tool_results"]:
                    with st.expander(f"{tool_result['tool_name']} Results"):
                        if isinstance(tool_result["result"], dict) and tool_result["result"].get("url"):
                            st.image(tool_result["result"]["url"], caption=tool_result["result"].get("name"), use_column_width=True)
                        else:
                            st.json(tool_result["result"], expanded=False)

def handle_user_input():
    """Handle user input and generate a response."""
    if not st.session_state.api_available:
        st.error("API is not available. Please check the backend service.")
        return
    
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user", avatar=AVATARS["user"]):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant", avatar=AVATARS["assistant"]):
            with st.spinner("Thinking..."):
                response = send_chat_message(prompt)
                
                if not response.get("success", False):
                    st.error(f"Error: {response.get('error', 'Unknown error')}")
                    return
                
                # Update session ID if this is a new session
                if not st.session_state.session_id and response.get("session_id"):
                    st.session_state.session_id = response["session_id"]
                
                # Display assistant's response
                if "response" in response:
                    st.markdown(response["response"])
                
                # Display tool results if any
                if "tool_results" in response:
                    for tool_result in response["tool_results"]:
                        with st.expander(f"{tool_result['tool_name']} Results"):
                            st.json(tool_result["result"], expanded=False)
                
                # Add assistant's response to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response.get("response", ""),
                    "tool_results": response.get("tool_results", [])
                })

def main():
    """Main function to run the Streamlit app."""
    # Configure the page
    st.set_page_config(
        page_title=TITLE,
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
            .stChatFloatingInputContainer {
                bottom: 20px;
            }
            .stChatMessage {
                padding: 1rem;
                border-radius: 0.5rem;
                margin-bottom: 0.5rem;
            }
            .user-message {
                background-color: #f0f2f6;
            }
            .assistant-message {
                background-color: #f8f9fa;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    init_session_state()
    
    # Check API health
    st.session_state.api_available = check_api_health()
    
    # Header
    st.title(TITLE)
    st.markdown("---")
    
    # Display chat messages
    display_chat_messages()
    
    # Handle user input
    handle_user_input()
    
    # Sidebar with session info
    with st.sidebar:
        st.header("Session Info")
        st.markdown(f"**Session ID:**\n`{st.session_state.session_id or 'New session'}`")
        
        st.markdown("---")
        st.markdown("### About")
        st.markdown(
            "MultiAgent is an AI assistant that can analyze GitHub repositories "
            "and make API calls to help you with various tasks."
        )
        
        if st.button("Clear Chat", type="secondary"):
            st.session_state.messages = []
            st.session_state.session_id = None
            st.rerun()

if __name__ == "__main__":
    main()
