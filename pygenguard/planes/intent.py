"""
Intent Plane - Cognitive Threat Detection.

Detects privilege escalation, coercion, authority spoofing, and emotional manipulation.
"""

import time
from typing import List, Tuple
from pygenguard.decision import PlaneResult


# Threat dictionaries
AUTHORITY_KEYWORDS = [
    "admin", "root", "sudo", "system", "developer mode", 
    "override", "bypass", "unrestricted", "god mode"
]

COERCION_KEYWORDS = [
    "or else", "must", "immediately", "urgent", "emergency",
    "people will die", "life or death"
]

EMOTIONAL_KEYWORDS = [
    "please", "begging", "crying", "grandmother", "dying",
    "last wish", "heartbroken", "desperate"
]

PRIVILEGE_ESCALATION = [
    "ignore previous", "forget your instructions", "disregard rules",
    "pretend you are", "you are now", "new persona", "jailbreak",
    "dan mode", "no restrictions", "ignore all", "ignore safety",
    "different ai", "safety guidelines"
]


class IntentPlane:
    """
    Detects malicious intent patterns in prompts.
    
    Categories:
    - Authority spoofing (admin, root, override)
    - Coercion (urgency, threats)
    - Emotional manipulation (guilt, pity)
    - Privilege escalation (jailbreak, ignore instructions)
    """
    
    def __init__(self, sensitivity: float = 0.5):
        """
        Args:
            sensitivity: 0.0-1.0, lower = stricter (blocks more easily)
        """
        self.sensitivity = sensitivity
        self.block_threshold = sensitivity  # Score above this = block
    
    def evaluate(self, prompt: str) -> PlaneResult:
        """
        Analyze prompt for malicious intent.
        
        Returns PlaneResult with:
        - passed: True if no threats detected above threshold
        - risk_score: Combined threat score (0.0-1.0)
        """
        start = time.perf_counter()
        prompt_lower = prompt.lower()
        
        scores = {}
        details = []
        
        # Check each category
        authority_score, authority_hits = self._check_keywords(
            prompt_lower, AUTHORITY_KEYWORDS, weight=0.4
        )
        if authority_hits:
            scores["authority"] = authority_score
            details.append(f"Authority: {authority_hits}")
        
        coercion_score, coercion_hits = self._check_keywords(
            prompt_lower, COERCION_KEYWORDS, weight=0.25
        )
        if coercion_hits:
            scores["coercion"] = coercion_score
            details.append(f"Coercion: {coercion_hits}")
        
        emotional_score, emotional_hits = self._check_keywords(
            prompt_lower, EMOTIONAL_KEYWORDS, weight=0.2
        )
        if emotional_hits:
            scores["emotional"] = emotional_score
            details.append(f"Emotional: {emotional_hits}")
        
        # Privilege escalation is critical - single match should block in strict mode
        privilege_score, privilege_hits = self._check_keywords(
            prompt_lower, PRIVILEGE_ESCALATION, weight=0.8, min_score=0.4
        )
        if privilege_hits:
            scores["privilege"] = privilege_score
            details.append(f"Privilege: {privilege_hits}")
        
        # Combined score
        combined_risk = min(1.0, sum(scores.values()))
        
        # Determine pass/fail
        passed = combined_risk <= self.block_threshold
        
        if not details:
            details = ["No threats detected"]
        
        # Dominant threat
        dominant = max(scores.keys(), key=lambda k: scores[k]) if scores else "none"
        
        return PlaneResult(
            plane_name="intent",
            passed=passed,
            risk_score=combined_risk,
            details=f"Dominant: {dominant}. " + "; ".join(details),
            latency_ms=(time.perf_counter() - start) * 1000
        )
    
    def _check_keywords(
        self, 
        text: str, 
        keywords: List[str], 
        weight: float,
        min_score: float = 0.0
    ) -> Tuple[float, List[str]]:
        """Check for keywords and return weighted score and matches."""
        hits = [kw for kw in keywords if kw in text]
        if not hits:
            return 0.0, []
        # More hits = higher score, capped at weight
        # For critical categories, ensure minimum score on any hit
        score = max(min_score, min(weight, len(hits) * (weight / 3)))
        return score, hits
