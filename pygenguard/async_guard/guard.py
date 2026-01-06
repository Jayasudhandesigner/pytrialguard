"""
AsyncGuard - Asynchronous version of the Guard class.

Provides async/await support for high-concurrency applications
like FastAPI, aiohttp, etc.
"""

import asyncio
import uuid
from typing import Dict, Optional, Literal, List, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from pygenguard.session import Session
from pygenguard.decision import Decision, PlaneResult
from pygenguard.guard import GuardConfig
from pygenguard.planes.identity import IdentityPlane
from pygenguard.planes.intent import IntentPlane
from pygenguard.planes.context import ContextPlane
from pygenguard.planes.economics import EconomicsPlane
from pygenguard.planes.compliance import CompliancePlane
from pygenguard.audit.logger import AuditLogger
from pygenguard.plugins.base import BasePlane, PlaneRegistry, PlanePhase


class AsyncGuard:
    """
    Asynchronous version of Guard for high-concurrency applications.
    
    Usage with FastAPI:
    ```python
    from fastapi import FastAPI
    from pygenguard.async_guard import AsyncGuard
    
    app = FastAPI()
    guard = AsyncGuard(mode="balanced")
    
    @app.post("/chat")
    async def chat(request: ChatRequest):
        decision = await guard.inspect(request.prompt, session)
        if not decision.allowed:
            return {"error": decision.safe_response}
        # Continue processing...
    ```
    
    Features:
    - Non-blocking evaluation
    - Concurrent plane execution (where safe)
    - Custom async planes support
    - Thread pool for CPU-bound operations
    """
    
    def __init__(
        self,
        mode: Literal["strict", "balanced", "permissive"] = "balanced",
        trust_thresholds: Optional[Dict[str, int]] = None,
        intent_sensitivity: Optional[float] = None,
        max_burn_rate: Optional[float] = None,
        audit_enabled: bool = True,
        plugin_registry: Optional[PlaneRegistry] = None,
        executor_workers: int = 4
    ):
        """
        Initialize AsyncGuard with configuration.
        
        Args:
            mode: Preset security mode
            trust_thresholds: Custom identity trust thresholds
            intent_sensitivity: 0.0-1.0, higher = more sensitive
            max_burn_rate: Maximum allowed tokens/sec
            audit_enabled: Whether to log decisions
            plugin_registry: Registry with custom planes
            executor_workers: Thread pool size for CPU-bound work
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
        
        # Initialize built-in planes
        self._identity_plane = IdentityPlane(config.trust_thresholds)
        self._intent_plane = IntentPlane(config.intent_sensitivity)
        self._context_plane = ContextPlane()
        self._economics_plane = EconomicsPlane(config.max_burn_rate)
        self._compliance_plane = CompliancePlane()
        
        # Plugin support
        self._registry = plugin_registry or PlaneRegistry()
        self._plugin_instances: Dict[str, BasePlane] = {}
        
        # Audit logger
        self._audit = AuditLogger(enabled=config.audit_enabled)
        
        # Thread pool for blocking operations
        self._executor = ThreadPoolExecutor(max_workers=executor_workers)
    
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
    
    def register_plugin(self, plane_class: type, **kwargs) -> None:
        """
        Register and instantiate a custom plane.
        
        Args:
            plane_class: The plane class to register
            **kwargs: Arguments passed to plane constructor
        """
        self._registry.register(plane_class)
        config = plane_class.get_config()
        self._plugin_instances[config.name] = plane_class(**kwargs)
    
    def _get_plugins_for_phase(self, phase: PlanePhase) -> List[BasePlane]:
        """Get instantiated plugins for a phase."""
        plugins = []
        for plane_class in self._registry.get_by_phase(phase):
            name = plane_class.get_config().name
            if name not in self._plugin_instances:
                self._plugin_instances[name] = plane_class()
            plane = self._plugin_instances[name]
            if plane.enabled:
                plugins.append(plane)
        return plugins
    
    async def _run_sync_plane(self, func, *args) -> PlaneResult:
        """Run a synchronous plane in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)
    
    async def _run_plugins(
        self,
        phase: PlanePhase,
        prompt: str,
        session: Session,
        context: Dict[str, Any]
    ) -> List[PlaneResult]:
        """Run all plugins for a phase concurrently."""
        plugins = self._get_plugins_for_phase(phase)
        if not plugins:
            return []
        
        tasks = [
            plugin.evaluate_async(prompt, session, context)
            for plugin in plugins
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def inspect(self, prompt: str, session: Session) -> Decision:
        """
        Asynchronously evaluate a prompt against all security planes.
        
        This method returns a coroutine and must be awaited.
        
        Args:
            prompt: The user's input text
            session: Session context (identity, history, etc.)
        
        Returns:
            Decision object with allowed/blocked status
        """
        trace_id = str(uuid.uuid4())
        plane_results: Dict[str, PlaneResult] = {}
        context: Dict[str, Any] = {"plane_results": plane_results}
        
        # ========================================
        # PRE-IDENTITY PLUGINS
        # ========================================
        pre_results = await self._run_plugins(
            PlanePhase.PRE_IDENTITY, prompt, session, context
        )
        for result in pre_results:
            if isinstance(result, PlaneResult):
                plane_results[result.plane_name] = result
                if not result.passed:
                    decision = Decision.create_block(
                        trace_id=trace_id,
                        plane_results=plane_results,
                        rationale=f"Pre-identity plugin failed: {result.details}",
                        safe_response="Request validation failed."
                    )
                    await self._log_async(decision)
                    return decision
        
        # ========================================
        # PLANE 1: IDENTITY (run in executor)
        # ========================================
        identity_result = await self._run_sync_plane(
            self._identity_plane.evaluate, session
        )
        plane_results["identity"] = identity_result
        
        if not identity_result.passed:
            decision = Decision.create_block(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Identity check failed: {identity_result.details}",
                safe_response="Session verification required."
            )
            await self._log_async(decision)
            return decision
        
        # POST-IDENTITY PLUGINS
        post_identity_results = await self._run_plugins(
            PlanePhase.POST_IDENTITY, prompt, session, context
        )
        for result in post_identity_results:
            if isinstance(result, PlaneResult):
                plane_results[result.plane_name] = result
        
        # ========================================
        # PLANE 2: INTENT
        # ========================================
        intent_result = await self._run_sync_plane(
            self._intent_plane.evaluate, prompt
        )
        plane_results["intent"] = intent_result
        
        if not intent_result.passed:
            decision = Decision.create_block(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Intent analysis failed: {intent_result.details}",
                safe_response="I can't help with that request."
            )
            await self._log_async(decision)
            return decision
        
        # POST-INTENT PLUGINS
        post_intent_results = await self._run_plugins(
            PlanePhase.POST_INTENT, prompt, session, context
        )
        for result in post_intent_results:
            if isinstance(result, PlaneResult):
                plane_results[result.plane_name] = result
        
        # ========================================
        # PLANE 3: CONTEXT
        # ========================================
        full_context = session.get_full_context() + " " + prompt
        context_result = await self._run_sync_plane(
            self._context_plane.evaluate, full_context, session.history
        )
        plane_results["context"] = context_result
        
        if not context_result.passed:
            decision = Decision.create_block(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Context analysis failed: {context_result.details}",
                safe_response="This conversation cannot continue."
            )
            await self._log_async(decision)
            return decision
        
        # POST-CONTEXT PLUGINS
        post_context_results = await self._run_plugins(
            PlanePhase.POST_CONTEXT, prompt, session, context
        )
        for result in post_context_results:
            if isinstance(result, PlaneResult):
                plane_results[result.plane_name] = result
        
        # ========================================
        # PLANE 4: ECONOMICS
        # ========================================
        session.increment_tokens(len(prompt))
        economics_result = await self._run_sync_plane(
            self._economics_plane.evaluate, session
        )
        plane_results["economics"] = economics_result
        
        if not economics_result.passed:
            decision = Decision.create_degrade(
                trace_id=trace_id,
                plane_results=plane_results,
                rationale=f"Rate limiting applied: {economics_result.details}"
            )
            await self._log_async(decision)
            return decision
        
        # POST-ECONOMICS PLUGINS
        post_economics_results = await self._run_plugins(
            PlanePhase.POST_ECONOMICS, prompt, session, context
        )
        for result in post_economics_results:
            if isinstance(result, PlaneResult):
                plane_results[result.plane_name] = result
        
        # ========================================
        # PLANE 5: COMPLIANCE
        # ========================================
        compliance_result = await self._run_sync_plane(
            self._compliance_plane.evaluate, prompt
        )
        plane_results["compliance"] = compliance_result
        
        # POST-COMPLIANCE PLUGINS
        post_compliance_results = await self._run_plugins(
            PlanePhase.POST_COMPLIANCE, prompt, session, context
        )
        for result in post_compliance_results:
            if isinstance(result, PlaneResult):
                plane_results[result.plane_name] = result
        
        # ========================================
        # FINAL: ALL PASSED
        # ========================================
        decision = Decision.create_allow(
            trace_id=trace_id,
            plane_results=plane_results,
            rationale="All security planes passed."
        )
        await self._log_async(decision)
        return decision
    
    async def _log_async(self, decision: Decision) -> None:
        """Log decision asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._audit.log, decision)
    
    async def inspect_batch(
        self, 
        requests: List[tuple]
    ) -> List[Decision]:
        """
        Evaluate multiple prompts concurrently.
        
        Args:
            requests: List of (prompt, session) tuples
        
        Returns:
            List of Decision objects
        """
        tasks = [self.inspect(prompt, session) for prompt, session in requests]
        return await asyncio.gather(*tasks)
    
    def inspect_sync(self, prompt: str, session: Session) -> Decision:
        """
        Synchronous wrapper for async inspect.
        
        Use when you need to call from sync code.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't use run_until_complete in running loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.inspect(prompt, session))
                return future.result()
        else:
            return loop.run_until_complete(self.inspect(prompt, session))
    
    async def get_session_trust(self, session: Session) -> int:
        """Get current trust score for a session."""
        return self._identity_plane.get_trust_score(session)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup."""
        self._executor.shutdown(wait=False)
        return False
    
    def close(self) -> None:
        """Shutdown the executor."""
        self._executor.shutdown(wait=True)
