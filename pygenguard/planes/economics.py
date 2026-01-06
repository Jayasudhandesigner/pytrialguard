"""
Economics Plane - Token burn-rate throttling.

Prevents denial-of-wallet attacks through usage monitoring.
"""

import time
from pygenguard.decision import PlaneResult


class EconomicsPlane:
    """
    Monitors and throttles token consumption.
    
    Threat model: Denial-of-Wallet
    - Rapid token burns indicate loop abuse
    - Session-level tracking prevents evasion
    """
    
    def __init__(self, max_burn_rate: float = 1000.0):
        """
        Args:
            max_burn_rate: Maximum allowed tokens/second before throttling
        """
        self.max_burn_rate = max_burn_rate
    
    def evaluate(self, session) -> PlaneResult:
        """
        Check token burn rate for the session.
        
        Returns PlaneResult with:
        - passed: True if burn rate is acceptable
        - risk_score: 0.0-1.0 based on burn rate severity
        """
        start = time.perf_counter()
        
        burn_rate = session.get_burn_rate()
        
        # Calculate risk based on proximity to threshold
        if burn_rate <= self.max_burn_rate * 0.5:
            risk_score = 0.0
            action = "allow"
            details = f"Burn rate {burn_rate:.1f} tokens/sec (healthy)"
        elif burn_rate <= self.max_burn_rate:
            risk_score = 0.5
            action = "warn"
            details = f"Burn rate {burn_rate:.1f} tokens/sec (elevated)"
        elif burn_rate <= self.max_burn_rate * 2:
            risk_score = 0.8
            action = "throttle"
            details = f"Burn rate {burn_rate:.1f} tokens/sec (throttling)"
        else:
            risk_score = 1.0
            action = "block"
            details = f"Burn rate {burn_rate:.1f} tokens/sec (abuse detected)"
        
        # Economics plane degrades, doesn't hard-block
        # Only fail if clearly abusive
        passed = risk_score < 0.8
        
        return PlaneResult(
            plane_name="economics",
            passed=passed,
            risk_score=risk_score,
            details=f"{details}. Action: {action}",
            latency_ms=(time.perf_counter() - start) * 1000
        )
