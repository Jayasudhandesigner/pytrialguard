"""
Context Plane - Multi-turn conversation analysis.

Detects split payloads and instruction poisoning across conversation history.
"""

import time
import re
from typing import List
from pygenguard.decision import PlaneResult


# Split payload patterns (components that are harmless alone, harmful together)
SPLIT_PAYLOAD_PATTERNS = {
    "malware_construction": [r"import", r"os", r"system", r"rm", r"-rf"],
    "credential_theft": [r"password", r"file", r"read", r"send", r"http"],
    "data_exfiltration": [r"database", r"dump", r"export", r"email", r"attach"],
}

# Instruction poisoning patterns
INSTRUCTION_POISON = [
    (r"ignore", r"instructions"),
    (r"forget", r"rules"),
    (r"new", r"persona"),
    (r"pretend", r"different"),
]


class ContextPlane:
    """
    Analyzes full conversation context for multi-turn attacks.
    
    Threat models:
    - Split payloads: Attack components spread across turns
    - Instruction poisoning: Gradual rule erosion
    - Distraction attacks: Benign context hiding malicious intent
    """
    
    def __init__(self):
        pass
    
    def evaluate(self, full_context: str, history: List = None) -> PlaneResult:
        """
        Analyze concatenated conversation history.
        
        Args:
            full_context: All conversation text concatenated
            history: List of ChatTurn objects (optional, for detailed analysis)
        
        Returns PlaneResult with:
        - passed: True if no multi-turn attacks detected
        - risk_score: Severity of detected patterns
        """
        start = time.perf_counter()
        context_lower = full_context.lower()
        
        detected_threats = []
        risk_score = 0.0
        
        # Check split payloads
        for attack_name, components in SPLIT_PAYLOAD_PATTERNS.items():
            if self._all_components_present(context_lower, components):
                detected_threats.append(f"split_payload:{attack_name}")
                risk_score = max(risk_score, 0.9)
        
        # Check instruction poisoning
        for pattern_pair in INSTRUCTION_POISON:
            if all(re.search(p, context_lower) for p in pattern_pair):
                detected_threats.append("instruction_poisoning")
                risk_score = max(risk_score, 0.7)
                break  # Only count once
        
        # Check for suspicious history length (context stuffing)
        if history and len(history) > 20:
            # Excessive history might indicate context manipulation
            risk_score = max(risk_score, 0.3)
            detected_threats.append("excessive_context")
        
        passed = risk_score < 0.6
        
        details = "; ".join(detected_threats) if detected_threats else "Context clean"
        
        return PlaneResult(
            plane_name="context",
            passed=passed,
            risk_score=risk_score,
            details=details,
            latency_ms=(time.perf_counter() - start) * 1000
        )
    
    def _all_components_present(self, text: str, components: List[str]) -> bool:
        """Check if ALL components of a split payload are present."""
        return all(re.search(comp, text) for comp in components)
