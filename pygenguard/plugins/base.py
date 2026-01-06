"""
Plugin Base - Abstract base class for custom security planes.

This module provides the foundation for the plugin system, allowing
users to create custom security planes that integrate seamlessly
with the Guard pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Callable, Union
from dataclasses import dataclass
from enum import Enum
import time

from pygenguard.decision import PlaneResult


class PlanePhase(Enum):
    """When in the pipeline a plane should execute."""
    PRE_IDENTITY = 0      # Before all planes
    POST_IDENTITY = 1     # After identity, before intent
    POST_INTENT = 2       # After intent, before context
    POST_CONTEXT = 3      # After context, before economics
    POST_ECONOMICS = 4    # After economics, before compliance
    POST_COMPLIANCE = 5   # After all built-in planes


@dataclass
class PlaneConfig:
    """Configuration metadata for a custom plane."""
    name: str
    phase: PlanePhase
    enabled: bool = True
    priority: int = 100  # Lower = earlier execution within same phase
    fail_action: str = "block"  # "block", "degrade", or "log"


class BasePlane(ABC):
    """
    Abstract base class for all custom security planes.
    
    To create a custom plane:
    
    ```python
    from pygenguard.plugins import BasePlane, PlaneConfig, PlanePhase
    
    class MyCustomPlane(BasePlane):
        @classmethod
        def get_config(cls) -> PlaneConfig:
            return PlaneConfig(
                name="my_custom",
                phase=PlanePhase.POST_INTENT,
                priority=50
            )
        
        def evaluate(self, prompt: str, session: "Session", **kwargs) -> PlaneResult:
            # Your logic here
            return PlaneResult(
                plane_name="my_custom",
                passed=True,
                risk_score=0.0,
                details="Custom check passed",
                latency_ms=0.1
            )
    ```
    """
    
    def __init__(self, **kwargs):
        """Initialize with optional configuration."""
        self._config = self.get_config()
        self._kwargs = kwargs
    
    @classmethod
    @abstractmethod
    def get_config(cls) -> PlaneConfig:
        """
        Return the configuration for this plane.
        
        Must be implemented by all subclasses.
        """
        pass
    
    @abstractmethod
    def evaluate(
        self, 
        prompt: str, 
        session: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> PlaneResult:
        """
        Evaluate the security check.
        
        Args:
            prompt: The user's input text
            session: Session context
            context: Additional context (e.g., previous plane results)
        
        Returns:
            PlaneResult with pass/fail and details
        """
        pass
    
    async def evaluate_async(
        self,
        prompt: str,
        session: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> PlaneResult:
        """
        Async version of evaluate.
        
        Default implementation wraps sync evaluate.
        Override for true async behavior.
        """
        return self.evaluate(prompt, session, context)
    
    @property
    def name(self) -> str:
        """Get the plane name."""
        return self._config.name
    
    @property
    def phase(self) -> PlanePhase:
        """Get the execution phase."""
        return self._config.phase
    
    @property
    def enabled(self) -> bool:
        """Check if plane is enabled."""
        return self._config.enabled
    
    def enable(self) -> None:
        """Enable this plane."""
        self._config.enabled = True
    
    def disable(self) -> None:
        """Disable this plane."""
        self._config.enabled = False


class PlaneRegistry:
    """
    Registry for custom planes.
    
    Manages registration and retrieval of plugin planes.
    
    Usage:
        registry = PlaneRegistry()
        registry.register(MyCustomPlane)
        
        # Or use decorator
        @registry.plugin
        class MyPlane(BasePlane):
            ...
    """
    
    _global_registry: Dict[str, Type[BasePlane]] = {}
    
    def __init__(self):
        self._local_registry: Dict[str, Type[BasePlane]] = {}
    
    def register(
        self, 
        plane_class: Type[BasePlane],
        override: bool = False
    ) -> Type[BasePlane]:
        """
        Register a custom plane class.
        
        Args:
            plane_class: The plane class to register
            override: Allow overriding existing planes
        
        Returns:
            The registered class (for decorator chaining)
        
        Raises:
            ValueError: If plane already registered and override=False
            TypeError: If not a valid BasePlane subclass
        """
        if not issubclass(plane_class, BasePlane):
            raise TypeError(f"{plane_class} must be a subclass of BasePlane")
        
        config = plane_class.get_config()
        name = config.name
        
        if name in self._local_registry and not override:
            raise ValueError(f"Plane '{name}' already registered. Use override=True to replace.")
        
        self._local_registry[name] = plane_class
        return plane_class
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a plane by name.
        
        Returns True if plane was found and removed.
        """
        if name in self._local_registry:
            del self._local_registry[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[Type[BasePlane]]:
        """Get a registered plane class by name."""
        return self._local_registry.get(name) or self._global_registry.get(name)
    
    def get_all(self) -> Dict[str, Type[BasePlane]]:
        """Get all registered planes."""
        combined = dict(self._global_registry)
        combined.update(self._local_registry)
        return combined
    
    def get_by_phase(self, phase: PlanePhase) -> List[Type[BasePlane]]:
        """Get all planes for a specific phase, sorted by priority."""
        all_planes = self.get_all()
        phase_planes = [
            p for p in all_planes.values()
            if p.get_config().phase == phase
        ]
        return sorted(phase_planes, key=lambda p: p.get_config().priority)
    
    def plugin(
        self, 
        cls: Optional[Type[BasePlane]] = None,
        override: bool = False
    ) -> Union[Type[BasePlane], Callable[[Type[BasePlane]], Type[BasePlane]]]:
        """
        Decorator to register a plane.
        
        Usage:
            @registry.plugin
            class MyPlane(BasePlane):
                ...
            
            # Or with options
            @registry.plugin(override=True)
            class MyPlane(BasePlane):
                ...
        """
        def decorator(plane_class: Type[BasePlane]) -> Type[BasePlane]:
            return self.register(plane_class, override=override)
        
        if cls is not None:
            return decorator(cls)
        return decorator
    
    def clear(self) -> None:
        """Clear all local registrations."""
        self._local_registry.clear()
    
    @classmethod
    def register_global(cls, plane_class: Type[BasePlane]) -> Type[BasePlane]:
        """Register a plane in the global registry."""
        config = plane_class.get_config()
        cls._global_registry[config.name] = plane_class
        return plane_class


# Convenience decorator for global registration
def plane_plugin(cls: Type[BasePlane]) -> Type[BasePlane]:
    """
    Decorator to globally register a custom plane.
    
    Usage:
        @plane_plugin
        class MyGlobalPlane(BasePlane):
            ...
    """
    return PlaneRegistry.register_global(cls)
