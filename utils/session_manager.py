import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import redis
import logging
from functools import lru_cache

from utils.config import settings

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages user sessions and chat history using Redis for persistence.
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the session manager with Redis connection."""
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis = self._get_redis_connection()
        self.session_expire_seconds = settings.SESSION_EXPIRE_SECONDS
    
    def _get_redis_connection(self):
        """Create and return a Redis connection."""
        try:
            return redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fallback to in-memory storage if Redis is not available
            return None
    
    def create_session(self, initial_data: Optional[Dict] = None) -> str:
        """
        Create a new session with optional initial data.
        
        Args:
            initial_data: Optional initial data to store in the session
            
        Returns:
            str: The newly created session ID
        """
        session_id = str(uuid.uuid4())
        session_data = {
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "data": initial_data or {},
            "chat_history": [],
        }
        
        if self.redis:
            try:
                self.redis.set(
                    f"session:{session_id}",
                    json.dumps(session_data),
                    ex=self.session_expire_seconds
                )
            except Exception as e:
                logger.error(f"Error creating session in Redis: {e}")
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Retrieve a session by its ID.
        
        Args:
            session_id: The session ID to retrieve
            
        Returns:
            Optional[Dict]: The session data or None if not found
        """
        if not session_id:
            return None
            
        if self.redis:
            try:
                session_data = self.redis.get(f"session:{session_id}")
                if session_data:
                    session = json.loads(session_data)
                    # Update the updated_at timestamp
                    session["updated_at"] = datetime.utcnow().isoformat()
                    self.redis.set(
                        f"session:{session_id}",
                        json.dumps(session),
                        ex=self.session_expire_seconds
                    )
                    return session
            except Exception as e:
                logger.error(f"Error getting session from Redis: {e}")
                
        return None
    
    def update_session(self, session_id: str, data: Dict) -> bool:
        """
        Update session data.
        
        Args:
            session_id: The session ID to update
            data: The data to update in the session
            
        Returns:
            bool: True if the update was successful, False otherwise
        """
        if not session_id or not data:
            return False
            
        if self.redis:
            try:
                session = self.get_session(session_id)
                if not session:
                    return False
                    
                # Update the session data
                session["data"].update(data)
                session["updated_at"] = datetime.utcnow().isoformat()
                
                self.redis.set(
                    f"session:{session_id}",
                    json.dumps(session),
                    ex=self.session_expire_seconds
                )
                return True
            except Exception as e:
                logger.error(f"Error updating session in Redis: {e}")
                
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: The session ID to delete
            
        Returns:
            bool: True if the session was deleted, False otherwise
        """
        if not session_id:
            return False
            
        if self.redis:
            try:
                return bool(self.redis.delete(f"session:{session_id}"))
            except Exception as e:
                logger.error(f"Error deleting session from Redis: {e}")
                
        return False
    
    def get_chat_history(self, session_id: str) -> List[Dict]:
        """
        Get the chat history for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            List[Dict]: The chat history as a list of messages
        """
        session = self.get_session(session_id)
        if session and "chat_history" in session:
            return session["chat_history"]
        return []
    
    def update_chat_history(self, session_id: str, messages: List[Dict]) -> bool:
        """
        Update the chat history for a session.
        
        Args:
            session_id: The session ID
            messages: List of messages to add to the history
            
        Returns:
            bool: True if the update was successful, False otherwise
        """
        if not session_id or not messages:
            return False
            
        if self.redis:
            try:
                session = self.get_session(session_id)
                if not session:
                    session = {"chat_history": []}
                
                # Ensure chat_history exists
                if "chat_history" not in session:
                    session["chat_history"] = []
                
                # Add new messages to history
                session["chat_history"].extend([
                    msg if isinstance(msg, dict) else msg.dict()
                    for msg in messages
                ])
                
                # Keep only the last N messages to prevent excessive memory usage
                max_history = 50  # Adjust based on your needs
                session["chat_history"] = session["chat_history"][-max_history:]
                
                session["updated_at"] = datetime.utcnow().isoformat()
                
                self.redis.set(
                    f"session:{session_id}",
                    json.dumps(session),
                    ex=self.session_expire_seconds
                )
                return True
            except Exception as e:
                logger.error(f"Error updating chat history in Redis: {e}")
                
        return False
    
    def clear_chat_history(self, session_id: str) -> bool:
        """
        Clear the chat history for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            bool: True if the history was cleared, False otherwise
        """
        return self.update_chat_history(session_id, [])
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear all data for a session (alias for delete_session).
        
        Args:
            session_id: The session ID to clear
            
        Returns:
            bool: True if the session was cleared, False otherwise
        """
        return self.delete_session(session_id)

# Create a singleton instance
_session_manager = None

def get_session_manager() -> SessionManager:
    """
    Get or create a singleton instance of SessionManager.
    
    Returns:
        SessionManager: The session manager instance
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
