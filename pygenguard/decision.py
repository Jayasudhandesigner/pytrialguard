"""
Decision - The immutable result of a Guard inspection.
"""

from dataclasses import dataclass, field
from typing import Literal, Dict, List, Optional
from datetime import datetime
import uuid


@dataclass(frozen=True)
class PlaneResult:
    """Result from a single defense plane."""
    plane_name: str
    passed: bool
    risk_score: float  # 0.0 - 1.0
    details: str
    latency_ms: float


@dataclass(frozen=True)
class Decision:
    """
    Immutable decision object returned by Guard.inspect().
    
    This is the contract - do not modify structure after v0.1.0.
    """
    
    # Core verdict
    allowed: bool
    action: Literal["ALLOW", "BLOCK", "DEGRADE", "CHALLENGE"]
    
    # Audit trail
    trace_id: str
    timestamp: datetime
    rationale: str
    
    # Plane-by-plane breakdown
    plane_results: Dict[str, PlaneResult] = field(default_factory=dict)
    
    # Safe fallback for blocked requests
    safe_response: str = "Request blocked by security policy."
    
    # Aggregate risk
    combined_risk_score: float = 0.0
    
    @classmethod
    def create_allow(
        cls,
        trace_id: str,
        plane_results: Dict[str, PlaneResult],
        rationale: str = "All security planes passed."
    ) -> "Decision":
        """Factory for allowed decisions."""
        return cls(
            allowed=True,
            action="ALLOW",
            trace_id=trace_id,
            timestamp=datetime.utcnow(),
            rationale=rationale,
            plane_results=plane_results,
            combined_risk_score=cls._calculate_combined_risk(plane_results)
        )
    
    @classmethod
    def create_block(
        cls,
        trace_id: str,
        plane_results: Dict[str, PlaneResult],
        rationale: str,
        safe_response: str = "Request blocked by security policy."
    ) -> "Decision":
        """Factory for blocked decisions."""
        return cls(
            allowed=False,
            action="BLOCK",
            trace_id=trace_id,
            timestamp=datetime.utcnow(),
            rationale=rationale,
            plane_results=plane_results,
            safe_response=safe_response,
            combined_risk_score=cls._calculate_combined_risk(plane_results)
        )
    
    @classmethod
    def create_degrade(
        cls,
        trace_id: str,
        plane_results: Dict[str, PlaneResult],
        rationale: str
    ) -> "Decision":
        """Factory for degraded mode decisions."""
        return cls(
            allowed=True,
            action="DEGRADE",
            trace_id=trace_id,
            timestamp=datetime.utcnow(),
            rationale=rationale,
            plane_results=plane_results,
            safe_response="Request allowed with restrictions.",
            combined_risk_score=cls._calculate_combined_risk(plane_results)
        )
    
    @staticmethod
    def _calculate_combined_risk(plane_results: Dict[str, PlaneResult]) -> float:
        """Weighted average of plane risk scores."""
        if not plane_results:
            return 0.0
        total = sum(pr.risk_score for pr in plane_results.values())
        return min(1.0, total / len(plane_results))
    
    def to_dict(self) -> dict:
        """Serialize for JSON audit logging."""
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "allowed": self.allowed,
            "action": self.action,
            "rationale": self.rationale,
            "combined_risk_score": self.combined_risk_score,
            "plane_results": {
                name: {
                    "passed": pr.passed,
                    "risk_score": pr.risk_score,
                    "details": pr.details,
                    "latency_ms": pr.latency_ms
                }
                for name, pr in self.plane_results.items()
            }
        }
