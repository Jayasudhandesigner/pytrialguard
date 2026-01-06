"""
PyGenGuard - Runtime Security Framework for GenAI Systems.

A deterministic, zero-dependency security layer that enforces trust, intent,
cost, and compliance policies before and after model execution.

v0.2.0 Features:
- Plugin system for custom security planes
- Async support (AsyncGuard) for high-concurrency apps
- Redis session store adapters for distributed deployments
"""

__version__ = "0.2.0"
__author__ = "PyGenGuard Contributors"

# Core exports
from pygenguard.guard import Guard
from pygenguard.session import Session
from pygenguard.decision import Decision

# v0.2.0: Async support
from pygenguard.async_guard import AsyncGuard

# v0.2.0: Plugin system
from pygenguard.plugins import BasePlane, PlaneRegistry, plane_plugin

__all__ = [
    # Core
    "Guard",
    "Session", 
    "Decision",
    # Async
    "AsyncGuard",
    # Plugins
    "BasePlane",
    "PlaneRegistry",
    "plane_plugin",
]
