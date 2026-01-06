"""
Identity Plane - Continuous Trust Scoring (CTS).

Evaluates session fingerprint stability and assigns trust tiers.
"""

import time
from typing import Dict
from pygenguard.decision import PlaneResult
from pygenguard.utils.hashing import compute_fingerprint


class IdentityPlane:
    """
    Implements Continuous Trust Scoring (CTS).
    
    Trust model:
    - New sessions start at 100
    - Fingerprint drift causes immediate penalty
    - Time-based decay after inactivity
    """
    
    def __init__(self, thresholds: Dict[str, int]):
        """
        Args:
            thresholds: {"full": 70, "degraded": 40}
        """
        self.thresholds = thresholds
        self._session_store: Dict[str, dict] = {}
    
    def evaluate(self, session) -> PlaneResult:
        """
        Evaluate identity trust for a session.
        
        Returns PlaneResult with:
        - passed: True if trust >= degraded threshold
        - risk_score: Inverse of trust (0.0 = fully trusted)
        """
        start = time.perf_counter()
        
        current_fp = session.get_fingerprint()
        user_id = session.user_id
        
        # New session
        if user_id not in self._session_store:
            self._session_store[user_id] = {
                "fingerprint": current_fp,
                "trust": 100,
                "last_seen": time.time()
            }
            return PlaneResult(
                plane_name="identity",
                passed=True,
                risk_score=0.0,
                details=f"New session established. Trust: 100",
                latency_ms=(time.perf_counter() - start) * 1000
            )
        
        profile = self._session_store[user_id]
        trust = profile["trust"]
        
        # Fingerprint drift detection
        if profile["fingerprint"] != current_fp:
            trust -= 50  # Major penalty
            details = "Fingerprint mismatch detected (-50)"
        else:
            details = "Fingerprint stable"
        
        # Time-based decay
        time_diff = time.time() - profile["last_seen"]
        if time_diff > 3600:  # 1 hour
            trust -= 5
            details += ", session aged (-5)"
        
        # Clamp
        trust = max(0, min(100, trust))
        
        # Update store
        self._session_store[user_id] = {
            "fingerprint": current_fp,
            "trust": trust,
            "last_seen": time.time()
        }
        
        # Determine pass/fail
        passed = trust >= self.thresholds.get("degraded", 40)
        risk_score = 1.0 - (trust / 100.0)
        
        tier = "locked"
        if trust >= self.thresholds.get("full", 70):
            tier = "full"
        elif trust >= self.thresholds.get("degraded", 40):
            tier = "degraded"
        
        return PlaneResult(
            plane_name="identity",
            passed=passed,
            risk_score=risk_score,
            details=f"Trust: {trust}, Tier: {tier}. {details}",
            latency_ms=(time.perf_counter() - start) * 1000
        )
    
    def get_trust_score(self, session) -> int:
        """Get current trust score for a session."""
        user_id = session.user_id
        if user_id in self._session_store:
            return self._session_store[user_id]["trust"]
        return 100  # New session default
