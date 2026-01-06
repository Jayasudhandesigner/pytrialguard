"""
Base Session Store - Abstract interface for session persistence.

Defines the contract for session storage backends.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
import json


@dataclass
class SessionData:
    """
    Serializable session data for storage.
    
    This is the data that gets persisted to the storage backend.
    """
    user_id: str
    fingerprint: str
    trust_score: int = 100
    last_seen: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    tokens_used: int = 0
    session_start: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    history_summary: str = ""  # Compact history representation
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "SessionData":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


class BaseSessionStore(ABC):
    """
    Abstract base class for session storage backends.
    
    Implementations must provide these methods for storing
    and retrieving session state.
    
    The session store is used by the IdentityPlane to:
    - Track trust scores across requests
    - Detect fingerprint drift
    - Manage session lifecycle
    
    Usage with Guard:
    ```python
    from pygenguard import Guard
    from pygenguard.adapters import RedisSessionStore
    
    store = RedisSessionStore(redis_url="redis://localhost:6379")
    guard = Guard(mode="balanced", session_store=store)
    ```
    """
    
    @abstractmethod
    def get(self, user_id: str) -> Optional[SessionData]:
        """
        Retrieve session data for a user.
        
        Args:
            user_id: The user identifier
        
        Returns:
            SessionData if found, None otherwise
        """
        pass
    
    @abstractmethod
    def set(self, user_id: str, data: SessionData, ttl: Optional[int] = None) -> bool:
        """
        Store session data for a user.
        
        Args:
            user_id: The user identifier
            data: SessionData to store
            ttl: Time-to-live in seconds (None = no expiry)
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """
        Delete session data for a user.
        
        Args:
            user_id: The user identifier
        
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    def exists(self, user_id: str) -> bool:
        """
        Check if a session exists.
        
        Args:
            user_id: The user identifier
        
        Returns:
            True if session exists
        """
        pass
    
    def update_trust(self, user_id: str, trust_score: int) -> bool:
        """
        Update just the trust score for a session.
        
        Default implementation gets, modifies, and sets.
        Override for atomic updates.
        """
        data = self.get(user_id)
        if data is None:
            return False
        data.trust_score = trust_score
        data.last_seen = datetime.utcnow().timestamp()
        return self.set(user_id, data)
    
    def increment_tokens(self, user_id: str, count: int) -> bool:
        """
        Increment token count for a session.
        
        Default implementation gets, modifies, and sets.
        Override for atomic updates.
        """
        data = self.get(user_id)
        if data is None:
            return False
        data.tokens_used += count
        data.last_seen = datetime.utcnow().timestamp()
        return self.set(user_id, data)
    
    def touch(self, user_id: str) -> bool:
        """
        Update last_seen timestamp.
        
        Keeps the session alive.
        """
        data = self.get(user_id)
        if data is None:
            return False
        data.last_seen = datetime.utcnow().timestamp()
        return self.set(user_id, data)
    
    def get_all_users(self) -> List[str]:
        """
        Get all user IDs with active sessions.
        
        Default returns empty list. Override for full support.
        """
        return []
    
    def clear_all(self) -> int:
        """
        Clear all sessions.
        
        Returns count of deleted sessions.
        Default returns 0. Override for full support.
        """
        return 0
    
    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass


class AsyncBaseSessionStore(ABC):
    """
    Async version of session store for high-concurrency applications.
    """
    
    @abstractmethod
    async def get(self, user_id: str) -> Optional[SessionData]:
        """Retrieve session data asynchronously."""
        pass
    
    @abstractmethod
    async def set(self, user_id: str, data: SessionData, ttl: Optional[int] = None) -> bool:
        """Store session data asynchronously."""
        pass
    
    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        """Delete session data asynchronously."""
        pass
    
    @abstractmethod
    async def exists(self, user_id: str) -> bool:
        """Check if session exists asynchronously."""
        pass
    
    async def update_trust(self, user_id: str, trust_score: int) -> bool:
        """Update trust score asynchronously."""
        data = await self.get(user_id)
        if data is None:
            return False
        data.trust_score = trust_score
        data.last_seen = datetime.utcnow().timestamp()
        return await self.set(user_id, data)
    
    async def close(self) -> None:
        """Clean up resources asynchronously."""
        pass
