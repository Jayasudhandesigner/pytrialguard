"""
Plugin Loader - Dynamic loading of plugin modules.

Supports loading plugins from:
- Python modules/packages
- Entry points (setuptools)
- File paths
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import List, Optional, Type, Dict, Any
import logging

from pygenguard.plugins.base import BasePlane, PlaneRegistry


logger = logging.getLogger("pygenguard.plugins")


class PluginLoader:
    """
    Dynamic plugin loader for PyGenGuard.
    
    Usage:
        loader = PluginLoader(registry)
        
        # Load from module
        loader.load_module("myapp.guards.custom_planes")
        
        # Load from file
        loader.load_file("/path/to/custom_plane.py")
        
        # Load from entry points
        loader.load_entry_points("pygenguard.planes")
    """
    
    def __init__(self, registry: Optional[PlaneRegistry] = None):
        """
        Initialize loader with optional registry.
        
        Args:
            registry: PlaneRegistry to register loaded planes.
                     If None, uses a new registry.
        """
        self.registry = registry or PlaneRegistry()
        self._loaded_modules: Dict[str, Any] = {}
    
    def load_module(self, module_name: str) -> List[Type[BasePlane]]:
        """
        Load planes from a Python module.
        
        Args:
            module_name: Fully qualified module name (e.g., "myapp.guards")
        
        Returns:
            List of loaded plane classes
        
        Raises:
            ImportError: If module cannot be imported
        """
        try:
            module = importlib.import_module(module_name)
            self._loaded_modules[module_name] = module
            return self._discover_planes(module)
        except ImportError as e:
            logger.error(f"Failed to import module '{module_name}': {e}")
            raise
    
    def load_file(self, file_path: str) -> List[Type[BasePlane]]:
        """
        Load planes from a Python file.
        
        Args:
            file_path: Path to Python file
        
        Returns:
            List of loaded plane classes
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ImportError: If file cannot be loaded as module
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Plugin file not found: {file_path}")
        
        if not path.suffix == ".py":
            raise ValueError(f"Plugin file must be a .py file: {file_path}")
        
        module_name = f"pygenguard_plugin_{path.stem}"
        
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        try:
            spec.loader.exec_module(module)
            self._loaded_modules[str(path)] = module
            return self._discover_planes(module)
        except Exception as e:
            del sys.modules[module_name]
            logger.error(f"Failed to load plugin file '{file_path}': {e}")
            raise ImportError(f"Failed to load plugin: {e}") from e
    
    def load_entry_points(self, group: str = "pygenguard.planes") -> List[Type[BasePlane]]:
        """
        Load planes from setuptools entry points.
        
        This allows third-party packages to register planes by defining
        entry points in their setup.py or pyproject.toml:
        
        ```toml
        [project.entry-points."pygenguard.planes"]
        my_plane = "mypackage.planes:MyCustomPlane"
        ```
        
        Args:
            group: Entry point group name
        
        Returns:
            List of loaded plane classes
        """
        loaded = []
        
        try:
            # Python 3.10+
            from importlib.metadata import entry_points
            eps = entry_points(group=group)
        except TypeError:
            # Python 3.9
            from importlib.metadata import entry_points as get_entry_points
            all_eps = get_entry_points()
            eps = all_eps.get(group, [])
        
        for ep in eps:
            try:
                plane_class = ep.load()
                if isinstance(plane_class, type) and issubclass(plane_class, BasePlane):
                    self.registry.register(plane_class)
                    loaded.append(plane_class)
                    logger.info(f"Loaded plane '{ep.name}' from entry point")
                else:
                    logger.warning(f"Entry point '{ep.name}' is not a valid BasePlane")
            except Exception as e:
                logger.error(f"Failed to load entry point '{ep.name}': {e}")
        
        return loaded
    
    def load_directory(self, directory: str, pattern: str = "*.py") -> List[Type[BasePlane]]:
        """
        Load all planes from Python files in a directory.
        
        Args:
            directory: Path to directory
            pattern: Glob pattern for files (default: "*.py")
        
        Returns:
            List of loaded plane classes
        """
        path = Path(directory)
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        loaded = []
        for file_path in path.glob(pattern):
            if file_path.name.startswith("_"):
                continue
            try:
                planes = self.load_file(str(file_path))
                loaded.extend(planes)
            except Exception as e:
                logger.warning(f"Skipping '{file_path}': {e}")
        
        return loaded
    
    def _discover_planes(self, module: Any) -> List[Type[BasePlane]]:
        """
        Discover and register all BasePlane subclasses in a module.
        
        Args:
            module: Imported Python module
        
        Returns:
            List of discovered plane classes
        """
        loaded = []
        
        for name in dir(module):
            if name.startswith("_"):
                continue
            
            obj = getattr(module, name)
            
            # Check if it's a class and a BasePlane subclass
            if (
                isinstance(obj, type) 
                and issubclass(obj, BasePlane) 
                and obj is not BasePlane
            ):
                try:
                    self.registry.register(obj)
                    loaded.append(obj)
                    logger.info(f"Registered plane '{obj.get_config().name}' from {module.__name__}")
                except ValueError as e:
                    logger.warning(f"Skipping '{name}': {e}")
                except Exception as e:
                    logger.error(f"Failed to register '{name}': {e}")
        
        return loaded
    
    def get_loaded_modules(self) -> Dict[str, Any]:
        """Get all loaded modules/files."""
        return dict(self._loaded_modules)
