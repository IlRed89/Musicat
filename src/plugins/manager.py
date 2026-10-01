"""
Plugin Manager for Musicat.

Handles discovery, loading, lifecycle, and dynamic configuration of plugins.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import threading
from typing import Any, Dict, List, Optional, Type

from src.core.settings import SettingsManager
from src.plugins.base import BasePlugin


class PluginManager:
    """Orchestrates modular plugin discovery and lifecycle."""

    _instance: Optional["PluginManager"] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        settings: Optional[SettingsManager] = None,
        settings_manager: Optional[SettingsManager] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._settings = settings or settings_manager or SettingsManager.get_instance()
        self._registered_plugins: Dict[str, BasePlugin] = {}
        self._active_plugins: Dict[str, BasePlugin] = {}

    @classmethod
    def get_instance(cls, settings: Optional[SettingsManager] = None) -> "PluginManager":
        """Singleton accessor."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(settings)
            return cls._instance

    def register_plugin(self, plugin: BasePlugin) -> None:
        """Registers a plugin instance."""
        with self._lock:
            self._registered_plugins[plugin.plugin_id] = plugin
            # Check if enabled in settings
            enabled = self._settings.get("plugins", f"{plugin.plugin_id}_enabled", False)
            if enabled:
                self.enable_plugin(plugin.plugin_id)

    def discover_plugins(self) -> List[BasePlugin]:
        """Dynamically scans src/plugins package and registers all BasePlugin subclasses."""
        import src.plugins as plugins_pkg

        with self._lock:
            for _, mod_name, _ in pkgutil.iter_modules(plugins_pkg.__path__):
                if mod_name in ("base", "manager"):
                    continue
                try:
                    module = importlib.import_module(f"src.plugins.{mod_name}")
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                            instance = obj()
                            if instance.plugin_id not in self._registered_plugins:
                                self.register_plugin(instance)
                except Exception:
                    pass

            return list(self._registered_plugins.values())

    def get_all_plugins(self) -> List[BasePlugin]:
        """Returns all registered plugins."""
        with self._lock:
            return list(self._registered_plugins.values())

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """Retrieves a plugin by its ID."""
        with self._lock:
            return self._registered_plugins.get(plugin_id)

    def is_enabled(self, plugin_id: str) -> bool:
        """Checks if a plugin is currently active and enabled in settings."""
        with self._lock:
            return bool(self._settings.get("plugins", f"{plugin_id}_enabled", False))

    is_plugin_enabled = is_enabled

    def enable_plugin(self, plugin_id: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Enables and initializes a registered plugin."""
        with self._lock:
            plugin = self._registered_plugins.get(plugin_id)
            if not plugin:
                return False

            try:
                ok = plugin.initialize(context)
                if ok:
                    self._active_plugins[plugin_id] = plugin
                    self._settings.set("plugins", f"{plugin_id}_enabled", True)
                    self._settings.save()
                    return True
            except Exception:
                pass
            return False

    def disable_plugin(self, plugin_id: str) -> None:
        """Disables and shuts down an active plugin."""
        with self._lock:
            if plugin_id in self._active_plugins:
                plugin = self._active_plugins.pop(plugin_id)
                try:
                    plugin.shutdown()
                except Exception:
                    pass
            self._settings.set("plugins", f"{plugin_id}_enabled", False)
            self._settings.save()

    def get_plugin_setting(self, plugin_id: str, key: str, default: Any = None) -> Any:
        """Retrieves custom setting for a specific plugin."""
        with self._lock:
            return self._settings.get("plugins", f"{plugin_id}_{key}", default)

    def set_plugin_setting(self, plugin_id: str, key: str, value: Any) -> None:
        """Saves custom setting for a specific plugin."""
        with self._lock:
            self._settings.set("plugins", f"{plugin_id}_{key}", value)
            self._settings.save()

    def run_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Executes a hook across all currently active/enabled plugins."""
        with self._lock:
            results = []
            for plugin in list(self._active_plugins.values()):
                try:
                    res = plugin.run_hook(hook_name, *args, **kwargs)
                    if res is not None:
                        results.append(res)
                except Exception:
                    pass
            return results
