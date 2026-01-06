"""
Redis Session Store - Distributed session persistence.

Provides Redis-backed session storage for distributed deployments.
Requires the `redis` optional dependency.
"""

from typing import Optional, List, Union
from datetime import datetime
import json
import logging

from pygenguard.adapters.base import BaseSessionStore, SessionData, AsyncBaseSessionStore

logger = logging.getLogger("pygenguard.adapters.redis")


class RedisSessionStore(BaseSessionStore):
    """
    Redis-backed session store for distributed systems.
    
    Features:
    - Distributed session sharing across instances
    - Automatic TTL-based expiry
    - Atomic operations for trust score updates
    - Connection pooling
    
    Requirements:
        pip install redis
    
    Usage:
        from pygenguard.adapters import RedisSessionStore
        
        # Simple connection
        store = RedisSessionStore("redis://localhost:6379/0")
        
        # With authentication
        store = RedisSessionStore(
            "redis://user:password@redis.example.com:6379/0",
            key_prefix="myapp:sessions:"
        )
        
        # Use with Guard
        guard = Guard(mode="balanced", session_store=store)
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "pygenguard:session:",
        default_ttl: int = 86400,  # 24 hours
        socket_timeout: float = 5.0,
        decode_responses: bool = True
    ):
        """
        Initialize Redis session store.
        
        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all session keys
            default_ttl: Default TTL in seconds (24h default)
            socket_timeout: Connection timeout in seconds
            decode_responses: Decode Redis responses to strings
        """
        try:
            import redis
        except ImportError:
            raise ImportError(
                "Redis support requires the 'redis' package. "
                "Install with: pip install 'pygenguard[redis]' or pip install redis"
            )
        
        self._redis = redis.from_url(
            redis_url,
            socket_timeout=socket_timeout,
            decode_responses=decode_responses
        )
        self._prefix = key_prefix
        self._default_ttl = default_ttl
        
        # Test connection
        try:
            self._redis.ping()
            logger.info(f"Connected to Redis at {redis_url}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _key(self, user_id: str) -> str:
        """Generate full Redis key."""
        return f"{self._prefix}{user_id}"
    
    def get(self, user_id: str) -> Optional[SessionData]:
        """Retrieve session data from Redis."""
        try:
            data = self._redis.get(self._key(user_id))
            if data is None:
                return None
            return SessionData.from_json(data)
        except Exception as e:
            logger.error(f"Redis GET error for {user_id}: {e}")
            return None
    
    def set(self, user_id: str, data: SessionData, ttl: Optional[int] = None) -> bool:
        """Store session data in Redis."""
        try:
            effective_ttl = ttl if ttl is not None else self._default_ttl
            key = self._key(user_id)
            
            if effective_ttl:
                self._redis.setex(key, effective_ttl, data.to_json())
            else:
                self._redis.set(key, data.to_json())
            
            return True
        except Exception as e:
            logger.error(f"Redis SET error for {user_id}: {e}")
            return False
    
    def delete(self, user_id: str) -> bool:
        """Delete session from Redis."""
        try:
            result = self._redis.delete(self._key(user_id))
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error for {user_id}: {e}")
            return False
    
    def exists(self, user_id: str) -> bool:
        """Check if session exists in Redis."""
        try:
            return bool(self._redis.exists(self._key(user_id)))
        except Exception as e:
            logger.error(f"Redis EXISTS error for {user_id}: {e}")
            return False
    
    def update_trust(self, user_id: str, trust_score: int) -> bool:
        """
        Atomically update trust score using Lua script.
        
        More efficient than get-modify-set for frequent updates.
        """
        lua_script = """
        local key = KEYS[1]
        local new_trust = tonumber(ARGV[1])
        local now = tonumber(ARGV[2])
        
        local data = redis.call('GET', key)
        if not data then
            return 0
        end
        
        local session = cjson.decode(data)
        session.trust_score = new_trust
        session.last_seen = now
        
        local ttl = redis.call('TTL', key)
        if ttl > 0 then
            redis.call('SETEX', key, ttl, cjson.encode(session))
        else
            redis.call('SET', key, cjson.encode(session))
        end
        
        return 1
        """
        
        try:
            now = datetime.utcnow().timestamp()
            result = self._redis.eval(
                lua_script, 
                1, 
                self._key(user_id),
                trust_score,
                now
            )
            return result == 1
        except Exception as e:
            logger.warning(f"Lua script failed, falling back: {e}")
            # Fallback to base implementation
            return super().update_trust(user_id, trust_score)
    
    def increment_tokens(self, user_id: str, count: int) -> bool:
        """Atomically increment token count."""
        lua_script = """
        local key = KEYS[1]
        local count = tonumber(ARGV[1])
        local now = tonumber(ARGV[2])
        
        local data = redis.call('GET', key)
        if not data then
            return 0
        end
        
        local session = cjson.decode(data)
        session.tokens_used = (session.tokens_used or 0) + count
        session.last_seen = now
        
        local ttl = redis.call('TTL', key)
        if ttl > 0 then
            redis.call('SETEX', key, ttl, cjson.encode(session))
        else
            redis.call('SET', key, cjson.encode(session))
        end
        
        return session.tokens_used
        """
        
        try:
            now = datetime.utcnow().timestamp()
            result = self._redis.eval(
                lua_script,
                1,
                self._key(user_id),
                count,
                now
            )
            return result > 0
        except Exception as e:
            logger.warning(f"Lua script failed, falling back: {e}")
            return super().increment_tokens(user_id, count)
    
    def get_all_users(self) -> List[str]:
        """Get all user IDs with sessions."""
        try:
            keys = self._redis.keys(f"{self._prefix}*")
            return [k.replace(self._prefix, "") for k in keys]
        except Exception as e:
            logger.error(f"Redis KEYS error: {e}")
            return []
    
    def clear_all(self) -> int:
        """Clear all sessions."""
        try:
            keys = self._redis.keys(f"{self._prefix}*")
            if keys:
                return self._redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear_all error: {e}")
            return 0
    
    def close(self) -> None:
        """Close Redis connection."""
        try:
            self._redis.close()
        except Exception:
            pass


class AsyncRedisSessionStore(AsyncBaseSessionStore):
    """
    Async Redis session store using redis.asyncio.
    
    For high-concurrency async applications.
    
    Requirements:
        pip install redis (includes asyncio support in redis>=4.2.0)
    
    Usage:
        from pygenguard.adapters import AsyncRedisSessionStore
        
        store = AsyncRedisSessionStore("redis://localhost:6379/0")
        
        # Use with AsyncGuard
        async_guard = AsyncGuard(mode="balanced", session_store=store)
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "pygenguard:session:",
        default_ttl: int = 86400
    ):
        """Initialize async Redis store."""
        try:
            import redis.asyncio as aioredis
        except ImportError:
            raise ImportError(
                "Async Redis support requires redis>=4.2.0. "
                "Install with: pip install 'redis>=4.2.0'"
            )
        
        self._redis = aioredis.from_url(
            redis_url,
            decode_responses=True
        )
        self._prefix = key_prefix
        self._default_ttl = default_ttl
        self._connected = False
    
    def _key(self, user_id: str) -> str:
        """Generate full Redis key."""
        return f"{self._prefix}{user_id}"
    
    async def _ensure_connected(self) -> None:
        """Verify connection on first use."""
        if not self._connected:
            try:
                await self._redis.ping()
                self._connected = True
                logger.info("Connected to Redis (async)")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    async def get(self, user_id: str) -> Optional[SessionData]:
        """Retrieve session data asynchronously."""
        await self._ensure_connected()
        try:
            data = await self._redis.get(self._key(user_id))
            if data is None:
                return None
            return SessionData.from_json(data)
        except Exception as e:
            logger.error(f"Async Redis GET error: {e}")
            return None
    
    async def set(self, user_id: str, data: SessionData, ttl: Optional[int] = None) -> bool:
        """Store session data asynchronously."""
        await self._ensure_connected()
        try:
            effective_ttl = ttl if ttl is not None else self._default_ttl
            key = self._key(user_id)
            
            if effective_ttl:
                await self._redis.setex(key, effective_ttl, data.to_json())
            else:
                await self._redis.set(key, data.to_json())
            
            return True
        except Exception as e:
            logger.error(f"Async Redis SET error: {e}")
            return False
    
    async def delete(self, user_id: str) -> bool:
        """Delete session asynchronously."""
        await self._ensure_connected()
        try:
            result = await self._redis.delete(self._key(user_id))
            return result > 0
        except Exception as e:
            logger.error(f"Async Redis DELETE error: {e}")
            return False
    
    async def exists(self, user_id: str) -> bool:
        """Check if session exists asynchronously."""
        await self._ensure_connected()
        try:
            return bool(await self._redis.exists(self._key(user_id)))
        except Exception as e:
            logger.error(f"Async Redis EXISTS error: {e}")
            return False
    
    async def close(self) -> None:
        """Close Redis connection."""
        try:
            await self._redis.close()
        except Exception:
            pass
