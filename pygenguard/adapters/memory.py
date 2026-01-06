"""
In-Memory Session Store - Default storage backend.

For local development and testing. Not suitable for distributed systems.
"""

from typing import Optional, Dict, List
from threading import Lock
from datetime import datetime

from pygenguard.adapters.base import BaseSessionStore, SessionData, AsyncBaseSessionStore


class InMemorySessionStore(BaseSessionStore):
    """
    Thread-safe in-memory session store.
    
    This is the default storage backend. Data is lost when
    the process exits.
    
    Features:
    - Thread-safe with locking
    - Optional automatic expiry
    - Good for testing and single-instance deployments
    
    Usage:
        store = InMemorySessionStore(default_ttl=3600)
        
        # Store session
        data = SessionData(user_id="user123", fingerprint="abc")
        store.set("user123", data)
        
        # Retrieve
        session = store.get("user123")
    """
    
    def __init__(self, default_ttl: Optional[int] = None):
        """
        Args:
            default_ttl: Default TTL in seconds for new sessions
        """
        self._store: Dict[str, tuple] = {}  # {user_id: (SessionData, expiry_time)}
        self._lock = Lock()
        self._default_ttl = default_ttl
    
    def _is_expired(self, expiry: Optional[float]) -> bool:
        """Check if a session has expired."""
        if expiry is None:
            return False
        return datetime.utcnow().timestamp() > expiry
    
    def _cleanup_expired(self) -> None:
        """Remove expired sessions (called internally)."""
        now = datetime.utcnow().timestamp()
        expired = [
            uid for uid, (_, expiry) in self._store.items()
            if expiry and now > expiry
        ]
        for uid in expired:
            del self._store[uid]
    
    def get(self, user_id: str) -> Optional[SessionData]:
        """Retrieve session data."""
        with self._lock:
            if user_id not in self._store:
                return None
            
            data, expiry = self._store[user_id]
            
            if self._is_expired(expiry):
                del self._store[user_id]
                return None
            
            return data
    
    def set(self, user_id: str, data: SessionData, ttl: Optional[int] = None) -> bool:
        """Store session data."""
        with self._lock:
            effective_ttl = ttl if ttl is not None else self._default_ttl
            expiry = None
            if effective_ttl:
                expiry = datetime.utcnow().timestamp() + effective_ttl
            
            self._store[user_id] = (data, expiry)
            return True
    
    def delete(self, user_id: str) -> bool:
        """Delete session data."""
        with self._lock:
            if user_id in self._store:
                del self._store[user_id]
                return True
            return False
    
    def exists(self, user_id: str) -> bool:
        """Check if session exists and is not expired."""
        with self._lock:
            if user_id not in self._store:
                return False
            
            _, expiry = self._store[user_id]
            if self._is_expired(expiry):
                del self._store[user_id]
                return False
            
            return True
    
    def get_all_users(self) -> List[str]:
        """Get all active user IDs."""
        with self._lock:
            self._cleanup_expired()
            return list(self._store.keys())
    
    def clear_all(self) -> int:
        """Clear all sessions."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count
    
    def size(self) -> int:
        """Get number of active sessions."""
        with self._lock:
            self._cleanup_expired()
            return len(self._store)


class AsyncInMemorySessionStore(AsyncBaseSessionStore):
    """
    Async wrapper around InMemorySessionStore.
    
    For consistency when using async code. Operations are
    still synchronous under the hood (memory is fast).
    """
    
    def __init__(self, default_ttl: Optional[int] = None):
        self._sync_store = InMemorySessionStore(default_ttl)
    
    async def get(self, user_id: str) -> Optional[SessionData]:
        return self._sync_store.get(user_id)
    
    async def set(self, user_id: str, data: SessionData, ttl: Optional[int] = None) -> bool:
        return self._sync_store.set(user_id, data, ttl)
    
    async def delete(self, user_id: str) -> bool:
        return self._sync_store.delete(user_id)
    
    async def exists(self, user_id: str) -> bool:
        return self._sync_store.exists(user_id)
