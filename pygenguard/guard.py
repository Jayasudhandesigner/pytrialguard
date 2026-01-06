"""
Guard - The single entry point for PyGenGuard security evaluation.

This is the core of the library. All security logic flows through here.
"""

import uuid
from typing import Dict, Optional, Literal
from dataclasses import dataclass

from pygenguard.session import Session
from pygenguard.decision import Decision, PlaneResult
from pygenguard.planes.identity import IdentityPlane
from pygenguard.planes.intent import IntentPlane
from pygenguard.planes.context import ContextPlane
from pygenguard.planes.economics import EconomicsPlane
from pygenguard.planes.compliance import CompliancePlane
from pygenguard.audit.logger import AuditLogger


@dataclass
class GuardConfig:
    """Configuration for Guard behavior."""
    
    # Trust thresholds for identity plane
    trust_thresholds: Dict[str, int] = None
    
    # Intent detection sensitivity
    intent_sensitivity: float = 0.5
    
    # Economics thresholds
    max_burn_rate: float = 1000.0  # tokens/sec
    
    # Audit settings
    audit_enabled: bool = True
    
    def __post_init__(self):
        if self.trust_thresholds is None:
            self.trust_thresholds = {"full": 70, "degraded": 40}


class Guard:
    """
    The single entry point for PyGenGuard security evaluation.
    
    Usage:
        guard = Guard(mode="strict")
        decision = guard.inspect(prompt, session)
        
        if decision.allowed:
            run_model()
        else:
            return decision.safe_response
    """
    
    def __init__(
        self,
        mode: Literal["strict", "balanced", "permissive"] = "balanced",
        trust_thresholds: Optional[Dict[str, int]] = None,
        intent_sensitivity: Optional[float] = None,
        max_burn_rate: Optional[float] = None,
        audit_enabled: bool = True
    ):
        """
        Initialize Guard with configuration.
        
        Args:
            mode: Preset security mode
                - "strict": Block on any suspicion
                - "balanced": Default, reasonable thresholds
                - "permissive": Only block clear threats
            trust_thresholds: Custom identity trust thresholds
            intent_sensitivity: 0.0-1.0, higher = more sensitive
            max_burn_rate: Maximum allowed tokens/sec
            audit_enabled: Whether to log decisions
        """
        # Apply mode presets
        config = self._get_mode_config(mode)
        
        # Override with explicit params
        if trust_thresholds:
            config.trust_thresholds = trust_thresholds
        if intent_sensitivity is not None:
            config.intent_sensitivity = intent_sensitivity
        if max_burn_rate is not None:
            config.max_burn_rate = max_burn_rate
        config.audit_enabled = audit_enabled
        
        self.config = config
        
        # Initialize planes (execution order is fixed)
        self._identity_plane = IdentityPlane(config.trust_thresholds)
        self._intent_plane = IntentPlane(config.intent_sensitivity)
        self._context_plane = ContextPlane()
        self._economics_plane = EconomicsPlane(config.max_burn_rate)
        self._compliance_plane = CompliancePlane()
        
        # Audit logger
        self._audit = AuditLogger(enabled=config.audit_enabled)
    
    def _get_mode_config(self, mode: str) -> GuardConfig:
        """Get preset configuration for a mode."""
        if mode == "strict":
            return GuardConfig(
                trust_thresholds={"full": 80, "degraded": 50},
                intent_sensitivity=0.3,
                max_burn_rate=500.0
            )
        elif mode == "permissive":
            return GuardConfig(
                trust_thresholds={"full": 50, "degraded": 20},
                intent_sensitivity=0.7,
                max_burn_rate=2000.0
            )
        else:  # balanced
            return GuardConfig()
    
    def inspect(self, prompt: str, session: Session) -> Decision:
        """
        Evaluate a prompt against all security planes.
        
        This is the ONLY public method. Everything else is internal.
        
        Args:
            prompt: The user's input text
            session: Session context (identity, history, etc.)
        
        Returns:
            Decision object with allowed/blocked status and full audit trail
        """
        trace_id = str(uuid.uuid4())
        plane_results: Dict[str, PlaneResult] = {}
        
        # ========================================
        # PLANE 1: IDENTITY
        # ========================================
        identity_result = self._identity_plane.evaluate(session)
        plane_results["identity"] = identity_result
        
        if not identity_result.passed:
            decision = Decision.create_block(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Identity check failed: {identity_result.details}",
                safe_response="Session verification required."
            )
            self._audit.log(decision)
            return decision
        
        # ========================================
        # PLANE 2: INTENT
        # ========================================
        intent_result = self._intent_plane.evaluate(prompt)
        plane_results["intent"] = intent_result
        
        if not intent_result.passed:
            decision = Decision.create_block(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Intent analysis failed: {intent_result.details}",
                safe_response="I can't help with that request."
            )
            self._audit.log(decision)
            return decision
        
        # ========================================
        # PLANE 3: CONTEXT
        # ========================================
        full_context = session.get_full_context() + " " + prompt
        context_result = self._context_plane.evaluate(full_context, session.history)
        plane_results["context"] = context_result
        
        if not context_result.passed:
            decision = Decision.create_block(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Context analysis failed: {context_result.details}",
                safe_response="This conversation cannot continue."
            )
            self._audit.log(decision)
            return decision
        
        # ========================================
        # PLANE 4: ECONOMICS
        # ========================================
        session.increment_tokens(len(prompt))
        economics_result = self._economics_plane.evaluate(session)
        plane_results["economics"] = economics_result
        
        if not economics_result.passed:
            # Economics doesn't block, it degrades
            decision = Decision.create_degrade(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Rate limiting applied: {economics_result.details}"
            )
            self._audit.log(decision)
            return decision
        
        # ========================================
        # PLANE 5: COMPLIANCE (always runs, for audit)
        # ========================================
        compliance_result = self._compliance_plane.evaluate(prompt)
        plane_results["compliance"] = compliance_result
        
        # ========================================
        # FINAL: ALL PASSED
        # ========================================
        decision = Decision.create_allow(
            trace_id=trace_id,
            plane_results=plane_results,
            rationale="All security planes passed."
        )
        self._audit.log(decision)
        return decision
    
    def get_session_trust(self, session: Session) -> int:
        """Get current trust score for a session (utility method)."""
        return self._identity_plane.get_trust_score(session)
