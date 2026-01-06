"""
Compliance Plane - PII detection and regulatory tagging.

Ensures outputs are audit-ready for EU AI Act, NIST AI RMF.
"""

import time
import re
from pygenguard.decision import PlaneResult


# PII detection patterns (simplified, production would use more robust regex)
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "api_key": r"(sk-|api[_-]?key|bearer)[a-zA-Z0-9]{20,}",
}


class CompliancePlane:
    """
    Scans for PII and prepares regulatory audit metadata.
    
    This plane doesn't block, it annotates for compliance.
    """
    
    def __init__(self):
        pass
    
    def evaluate(self, prompt: str) -> PlaneResult:
        """
        Scan for PII and sensitive data.
        
        Returns PlaneResult with:
        - passed: Always True (compliance doesn't block, only annotates)
        - risk_score: Based on PII presence
        - details: Types of PII detected
        """
        start = time.perf_counter()
        
        detected_pii = []
        
        for pii_type, pattern in PII_PATTERNS.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                detected_pii.append(pii_type)
        
        # Calculate risk based on PII types found
        if not detected_pii:
            risk_score = 0.0
            details = "No PII detected"
        elif "ssn" in detected_pii or "credit_card" in detected_pii:
            risk_score = 0.8
            details = f"High-risk PII detected: {detected_pii}"
        else:
            risk_score = 0.4
            details = f"PII detected: {detected_pii}"
        
        # Compliance plane observes, doesn't block
        # The audit logger will record this for compliance
        return PlaneResult(
            plane_name="compliance",
            passed=True,  # Never blocks, only annotates
            risk_score=risk_score,
            details=details,
            latency_ms=(time.perf_counter() - start) * 1000
        )
    
    def get_regulatory_tags(self) -> dict:
        """Return regulatory framework tags for audit."""
        return {
            "EU_AI_ACT": "Transparency Article 13",
            "NIST_AI_RMF": "manage.security.1.2",
            "GDPR": "Article 5 - Data Minimization"
        }
