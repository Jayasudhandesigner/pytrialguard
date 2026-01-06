"""
PyGenGuard Plugin System.

Provides extensibility through custom security planes.
"""

from pygenguard.plugins.base import (
    BasePlane,
    PlaneRegistry,
    PlaneConfig,
    PlanePhase,
    plane_plugin,
)
from pygenguard.plugins.loader import PluginLoader

__all__ = [
    "BasePlane",
    "PlaneRegistry",
    "PlaneConfig",
    "PlanePhase",
    "plane_plugin",
    "PluginLoader",
]
