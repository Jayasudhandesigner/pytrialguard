"""
Session - Request context for security evaluation.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib


@dataclass
class ChatTurn:
    """A single conversation turn."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float


@dataclass
class Session:
    """
    Encapsulates all request context needed for security evaluation.
    
    This is the main input alongside the prompt for Guard.inspect().
    """
    
    # User identification
    user_id: str
    
    # Network signals
    ip_address: str = "0.0.0.0"
    user_agent: str = ""
    tls_fingerprint: str = "unknown"
    
    # Conversation history (for context plane)
    history: List[ChatTurn] = field(default_factory=list)
    
    # Token tracking (for economics plane)
    tokens_used_session: int = 0
    session_start_time: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_request(
        cls,
        request: Any,
        user_id: str,
        history: Optional[List[Dict]] = None
    ) -> "Session":
        """
        Factory to create Session from a web framework request object.
        
        Works with FastAPI, Flask, Django, or any framework with standard attributes.
        """
        # Extract IP (handle proxies)
        ip = "0.0.0.0"
        if hasattr(request, "client") and request.client:
            ip = getattr(request.client, "host", "0.0.0.0")
        elif hasattr(request, "headers"):
            ip = request.headers.get("X-Forwarded-For", "0.0.0.0").split(",")[0].strip()
        
        # Extract User-Agent
        user_agent = ""
        if hasattr(request, "headers"):
            user_agent = request.headers.get("User-Agent", "")
        
        # Convert history dicts to ChatTurn objects
        chat_history = []
        if history:
            for turn in history:
                chat_history.append(ChatTurn(
                    role=turn.get("role", "user"),
                    content=turn.get("content", ""),
                    timestamp=turn.get("timestamp", datetime.utcnow().timestamp())
                ))
        
        return cls(
            user_id=user_id,
            ip_address=ip,
            user_agent=user_agent,
            history=chat_history
        )
    
    @classmethod
    def create(cls, user_id: str, **kwargs) -> "Session":
        """Simple factory for manual session creation."""
        return cls(user_id=user_id, **kwargs)
    
    def get_fingerprint(self) -> str:
        """Generate a cryptographic fingerprint of the session."""
        raw = f"{self.ip_address}|{self.user_agent}|{self.tls_fingerprint}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    def add_turn(self, role: str, content: str) -> None:
        """Add a conversation turn to history."""
        self.history.append(ChatTurn(
            role=role,
            content=content,
            timestamp=datetime.utcnow().timestamp()
        ))
    
    def get_full_context(self) -> str:
        """Concatenate all history for context analysis."""
        return " ".join(turn.content for turn in self.history)
    
    def increment_tokens(self, count: int) -> None:
        """Track token usage for economics plane."""
        self.tokens_used_session += count
    
    def get_burn_rate(self) -> float:
        """Calculate tokens per second for this session."""
        elapsed = datetime.utcnow().timestamp() - self.session_start_time
        if elapsed <= 0:
            return 0.0
        return self.tokens_used_session / elapsed
