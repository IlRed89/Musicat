"""
Unit tests for SettingsManager and Plugin Architecture in Musicat.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from src.core.settings import SettingsManager
from src.plugins.base import BasePlugin
from src.plugins.manager import PluginManager
from src.plugins.acoustid_plugin import AcoustIdPlugin
from src.plugins.lyrics_plugin import LyricsPlugin


class DummyTestPlugin(BasePlugin):
    """Mock plugin for testing."""

    @property
    def plugin_id(self) -> str:
        return "dummy_test"

    @property
    def name(self) -> str:
        return "Dummy Test Plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Plugin for test coverage"

    def get_config_schema(self):
        return {"custom_param": "default_val"}

    def run_hook(self, hook_name: str, *args, **kwargs):
        if hook_name == "on_test":
            return "hook_executed_successfully"
        return None


class TestSettingsManager(unittest.TestCase):
    """Tests for SettingsManager configuration store."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.settings = SettingsManager(config_path=self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_settings_created(self):
        """Settings file should be created with default values."""
        self.assertTrue(self.config_path.exists())
        ui_theme = self.settings.get("ui.theme")
        self.assertEqual(ui_theme, "light")
        audio_dev = self.settings.get("audio.output_device")
        self.assertEqual(audio_dev.lower(), "default")
        perf_gpu = self.settings.get("performance.gpu_acceleration")
        self.assertTrue(perf_gpu)

    def test_set_and_save_value(self):
        """Updating a setting should persist to disk."""
        self.settings.set("ui.theme", "dark_dj")
        self.settings.set("audio.buffer_ms", 150)
        self.assertEqual(self.settings.get("ui.theme"), "dark_dj")
        self.assertEqual(self.settings.get("audio.buffer_ms"), 150)

        # Reload from disk
        reloaded = SettingsManager(config_path=self.config_path)
        self.assertEqual(reloaded.get("ui.theme"), "dark_dj")
        self.assertEqual(reloaded.get("audio.buffer_ms"), 150)

    def test_get_fallback_default(self):
        """Requesting non-existent key returns default parameter."""
        val = self.settings.get("nonexistent.nested.key", default="fallback")
        self.assertEqual(val, "fallback")

    def test_reset_to_defaults(self):
        """Reset restores original defaults."""
        self.settings.set("ui.theme", "club_contrast")
        self.settings.reset_to_defaults()
        self.assertEqual(self.settings.get("ui.theme"), "light")


class TestPluginSystem(unittest.TestCase):
    """Tests for BasePlugin and PluginManager."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.settings = SettingsManager(config_path=self.config_path)
        self.manager = PluginManager(settings_manager=self.settings)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_manual_plugin_registration(self):
        """Registering a plugin dynamically adds it to the registry."""
        dummy = DummyTestPlugin()
        self.manager.register_plugin(dummy)

        plugin_ids = [p.plugin_id for p in self.manager.get_all_plugins()]
        self.assertIn("dummy_test", plugin_ids)
        self.assertFalse(self.manager.is_plugin_enabled("dummy_test"))

        # Enable plugin
        self.manager.enable_plugin("dummy_test")
        self.assertTrue(self.manager.is_plugin_enabled("dummy_test"))

        # Test hook execution
        results = self.manager.run_hook("on_test")
        self.assertEqual(results, ["hook_executed_successfully"])

    def test_enable_disable_plugin(self):
        """Enabling and disabling persists state and stops hooks."""
        dummy = DummyTestPlugin()
        self.manager.register_plugin(dummy)

        self.manager.enable_plugin("dummy_test")
        self.assertTrue(self.manager.is_plugin_enabled("dummy_test"))
        self.assertEqual(self.manager.run_hook("on_test"), ["hook_executed_successfully"])

        self.manager.disable_plugin("dummy_test")
        self.assertFalse(self.manager.is_plugin_enabled("dummy_test"))
        self.assertEqual(self.manager.run_hook("on_test"), [])

    def test_builtin_plugins_schema(self):
        """Built-in AcoustId and Lyrics plugins expose configuration schemas."""
        acoust = AcoustIdPlugin()
        self.assertEqual(acoust.plugin_id, "acoustid_fingerprint")
        schema = acoust.get_config_schema()
        self.assertTrue(any(item.get("key") == "client_api_key" for item in schema))

        lyrics = LyricsPlugin()
        self.assertEqual(lyrics.plugin_id, "lyrics_fetcher")
        schema_lyrics = lyrics.get_config_schema()
        self.assertTrue(any(item.get("key") == "prefer_synced" for item in schema_lyrics))


class TestThemeAndHardwareFeatures(unittest.TestCase):
    """Tests for dynamic theme indicator styling, default ffmpeg resolution and GPU diagnostics."""

    def test_ffmpeg_resolution_and_validation(self):
        """Bundled or system ffmpeg should be resolved and validated."""
        from src.core.path_resolver import PathResolver
        ffmpeg_path = PathResolver.get_default_ffmpeg_path()
        self.assertTrue(len(ffmpeg_path) > 0, "Default ffmpeg path should not be empty")
        is_valid, msg = PathResolver.validate_ffmpeg(ffmpeg_path)
        self.assertTrue(is_valid, f"FFmpeg validation failed: {msg}")
        self.assertTrue(msg.startswith("v"), f"Expected version string starting with 'v', got: {msg}")

    def test_theme_checkbox_and_groupbox_indicators(self):
        """Stylesheets must define 18px indicators for both QCheckBox and QGroupBox across themes."""
        from src.gui.styles import get_theme_stylesheet
        for theme_id in ["light", "dark_dj", "high_contrast"]:
            qss = get_theme_stylesheet(theme_id)
            self.assertIn("QCheckBox::indicator, QGroupBox::indicator", qss, f"Indicator grouping missing in {theme_id}")
            self.assertIn("width: 18px;", qss, f"18px width indicator missing in {theme_id}")
            self.assertIn("height: 18px;", qss, f"18px height indicator missing in {theme_id}")

    def test_gpu_diagnostic_details(self):
        """GpuDetector.get_diagnostic_details returns hardware and runtime breakdown."""
        from src.core.gpu_detector import GpuDetector
        diag = GpuDetector.get_diagnostic_details()
        self.assertIsInstance(diag, dict)
        self.assertIn("hardware_gpu", diag)
        self.assertIn("pytorch", diag)
        self.assertIn("onnxruntime", diag)
        self.assertIn("active_backend", diag)
        self.assertIn("is_available", diag)


if __name__ == "__main__":
    unittest.main()

