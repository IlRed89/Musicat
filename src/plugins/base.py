"""
Base Plugin Interface for Musicat.

Defines the contract for optional scrapers, audio processors, and catalog extensions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BasePlugin(ABC):
    """Abstract base class for all Musicat plugins and modular extensions."""

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique machine identifier for the plugin (e.g. 'acoustid_pro')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name."""
        pass

    @property
    def version(self) -> str:
        """Semantic version of the plugin."""
        return "1.0.0"

    @property
    def author(self) -> str:
        """Plugin author name or organization."""
        return "Musicat Community"

    @property
    def description(self) -> str:
        """Brief description of plugin capabilities."""
        return ""

    def get_config_schema(self) -> List[Dict[str, Any]]:
        """Returns metadata for settings fields needed by this plugin.

        Each field is a dictionary with:
        - 'key': str (setting identifier)
        - 'label': str (display label)
        - 'type': str ('str', 'password', 'int', 'bool', 'choice')
        - 'default': Any
        - 'choices': Optional[List[str]] (if type == 'choice')
        - 'description': Optional[str]
        """
        return []

    def initialize(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """Invoked when the plugin is enabled and loaded into runtime.

        Args:
            context: Optional application context (database, settings, logger).

        Returns:
            True if initialization was successful, False otherwise.
        """
        return True

    def shutdown(self) -> None:
        """Invoked before the plugin is unloaded or application exits."""
        pass
