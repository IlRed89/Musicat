"""
Settings & Configuration Management for Musicat.

Handles persistent application configuration saved in `config.json`.
Automatically selects local application folder in portable mode (portable.lock)
or system AppData/Application Support in standard mode.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.path_resolver import PathResolver


DEFAULT_SETTINGS: Dict[str, Any] = {
    "ui": {
        "language": "it",  # "it" (Italiano, default) or "en" (English)
        "theme": "light",  # "light" (Default), "dark_dj", "high_contrast"
        "dpi_scale": "auto",  # "auto", "100%", "125%", "150%"
        "font_size": 12,
        "row_height": 28,
        "visible_columns": [
            "title",
            "artist",
            "album",
            "genre",
            "year",
            "bpm",
            "camelot_key",
            "duration",
            "bitrate",
        ],
        "sidebar_collapsed": False,
    },
    "audio": {
        "output_device": "Default",
        "buffer_ms": 150,
        "autoplay_on_click": True,
        "pitch_range": 8,  # +/- 8% or +/- 16%
    },
    "performance": {
        "cpu_cores": max(1, (os.cpu_count() or 4) - 1),
        "ram_cache_mb": 512,
        "gpu_acceleration": True,
        "batch_size": 25,
    },
    "scrapers": {
        "discogs_token": "",
        "spotify_client_id": "",
        "spotify_client_secret": "",
        "beatport_username": "",
        "beatport_password": "",
    },
    "plugins": {},
}


class SettingsManager:
    """Thread-safe configuration manager for Musicat."""

    _instance: Optional["SettingsManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initializes SettingsManager with target configuration file path."""
        self._lock = threading.RLock()
        if config_path:
            self._config_path = Path(config_path)
        else:
            self._config_path = PathResolver.get_data_dir() / "config.json"

        self._settings: Dict[str, Any] = {}
        self.load()

    @classmethod
    def get_instance(cls, config_path: Optional[Path] = None) -> "SettingsManager":
        """Singleton accessor for global SettingsManager."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(config_path)
            return cls._instance

    @property
    def config_path(self) -> Path:
        """Returns the configuration file path."""
        return self._config_path

    def load(self) -> None:
        """Loads configuration from disk, applying defaults for missing keys."""
        with self._lock:
            # Deep copy defaults
            self._settings = json.loads(json.dumps(DEFAULT_SETTINGS))

            if self._config_path.exists():
                try:
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        disk_data = json.load(f)
                    if isinstance(disk_data, dict):
                        # Merge top-level sections
                        for section, values in disk_data.items():
                            if isinstance(values, dict) and section in self._settings:
                                self._settings[section].update(values)
                            else:
                                self._settings[section] = values
                except Exception:
                    pass
            else:
                self.save()

    def save(self) -> bool:
        """Saves current configuration to disk.

        Returns:
            True if saved successfully, False otherwise.
        """
        with self._lock:
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(self._settings, f, indent=2, ensure_ascii=False)
                return True
            except Exception:
                return False

    def get(self, section_or_key: str, key_or_default: Any = None, default: Any = None) -> Any:
        """Retrieves a configuration value using section+key or dot-notation."""
        with self._lock:
            if "." in section_or_key:
                sec, k = section_or_key.split(".", 1)
                def_val = key_or_default if default is None else default
                return self._settings.get(sec, {}).get(k, def_val)
            else:
                sec = section_or_key
                k = key_or_default
                return self._settings.get(sec, {}).get(k, default)

    def set(self, section_or_key: str, key_or_value: Any, value: Any = Ellipsis) -> None:
        """Sets a configuration value using section+key or dot-notation, persisting to disk."""
        with self._lock:
            if value is Ellipsis:
                if "." in section_or_key:
                    sec, k = section_or_key.split(".", 1)
                else:
                    sec, k = section_or_key, ""
                val = key_or_value
            else:
                sec = section_or_key
                k = key_or_value
                val = value

            if sec not in self._settings or not isinstance(self._settings[sec], dict):
                self._settings[sec] = {}
            self._settings[sec][k] = val
            self.save()

    def get_section(self, section: str) -> Dict[str, Any]:
        """Returns a copy of an entire section dictionary."""
        with self._lock:
            return dict(self._settings.get(section, {}))

    def reset_defaults(self) -> None:
        """Resets all settings to factory defaults."""
        with self._lock:
            self._settings = json.loads(json.dumps(DEFAULT_SETTINGS))
            self.save()

    def reset_to_defaults(self) -> None:
        """Alias for reset_defaults."""
        self.reset_defaults()
