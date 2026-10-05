"""
Unit tests for macOS Launch Diagnostics & Early Bootstrap Tracing Suite.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.boot_diagnostics import (
    EarlyBootLogger,
    boot_log,
    check_rosetta_emulation,
    get_macos_version_info,
    get_critical_env_vars,
    check_macos_permissions,
    probe_vlc_libraries,
    log_full_boot_report,
    get_qt_display_diagnostics,
)


class TestBootDiagnostics(unittest.TestCase):
    """Verifies the early bootstrap logging and diagnostic engine."""

    def test_early_boot_logger_init_and_write(self):
        """Tests that EarlyBootLogger initializes and writes flushed lines to disk."""
        logger = EarlyBootLogger.initialize()
        self.assertIsNotNone(logger)
        self.assertTrue(len(logger.active_log_paths) > 0)

        # Write test lines
        logger.log("Unit test early boot log message", level="INFO")
        logger.flush()

        # Verify at least the primary target file was created and contains the message
        primary_path = Path(logger.active_log_paths[0])
        self.assertTrue(primary_path.exists())
        content = primary_path.read_text(encoding="utf-8")
        self.assertIn("Unit test early boot log message", content)

    def test_boot_log_shorthand(self):
        """Tests global convenience helper boot_log."""
        logger = EarlyBootLogger.get_instance()
        boot_log("Convenience test message", level="DEBUG")
        logger.flush()

        primary_path = Path(logger.active_log_paths[0])
        content = primary_path.read_text(encoding="utf-8")
        self.assertIn("Convenience test message", content)

    def test_rosetta_emulation_detection(self):
        """Verifies Rosetta 2 detector structure and fallback on non-macOS."""
        info = check_rosetta_emulation()
        self.assertIn("is_macos", info)
        self.assertIn("machine", info)
        self.assertIn("is_rosetta", info)
        self.assertIn("description", info)
        self.assertIsInstance(info["is_rosetta"], bool)

    def test_macos_version_info(self):
        """Verifies macOS version inspection."""
        vinfo = get_macos_version_info()
        self.assertIn("is_macos", vinfo)
        self.assertIn("platform_str", vinfo)
        self.assertIn("product_version", vinfo)
        self.assertIn("build_version", vinfo)

    def test_critical_env_vars(self):
        """Verifies capture of critical runtime environment variables."""
        env_vars = get_critical_env_vars()
        self.assertIn("PATH", env_vars)
        self.assertIn("DYLD_LIBRARY_PATH", env_vars)
        self.assertIn("QT_QPA_PLATFORM", env_vars)
        self.assertIn("PYTHON_VLC_LIB_PATH", env_vars)

    def test_check_macos_permissions(self):
        """Verifies macOS permissions check function runs safely."""
        perms = check_macos_permissions()
        self.assertIsInstance(perms, list)
        if sys.platform == "darwin":
            self.assertTrue(len(perms) >= 3)
            for p in perms:
                self.assertIn("name", p)
                self.assertIn("status", p)

    def test_probe_vlc_libraries(self):
        """Verifies dynamic probe of libVLC candidates."""
        report = probe_vlc_libraries()
        self.assertIn("verified_path", report)
        self.assertIn("plugins_path", report)
        self.assertIn("candidates_checked", report)
        self.assertIn("errors", report)
        self.assertTrue(len(report["candidates_checked"]) > 0)
        for cand in report["candidates_checked"]:
            self.assertIn("path", cand)
            self.assertIn("exists", cand)
            self.assertIn("dlopen_ok", cand)

    def test_log_full_boot_report(self):
        """Verifies full bootstrap report execution without raising exceptions."""
        logger = EarlyBootLogger.initialize()
        # Should execute completely and flush
        log_full_boot_report(logger)
        primary_path = Path(logger.active_log_paths[0])
        content = primary_path.read_text(encoding="utf-8")
        self.assertIn("MUSICAT EARLY BOOTSTRAP & HARDWARE DIAGNOSTICS SUITE", content)

    def test_get_qt_display_diagnostics_mock(self):
        """Verifies Qt display diagnostics with mocked QApplication."""
        mock_app = MagicMock()
        mock_app.platformName.return_value = "cocoa"
        mock_screen = MagicMock()
        mock_screen.name.return_value = "Retina Built-in"
        mock_geom = MagicMock()
        mock_geom.width.return_value = 2880
        mock_geom.height.return_value = 1800
        mock_screen.geometry.return_value = mock_geom
        mock_screen.devicePixelRatio.return_value = 2.0
        mock_screen.logicalDotsPerInch.return_value = 144.0
        mock_app.screens.return_value = [mock_screen]

        diag = get_qt_display_diagnostics(mock_app)
        self.assertEqual(diag["platform_name"], "cocoa")
        self.assertEqual(diag["screens_count"], 1)
        self.assertEqual(diag["screens"][0]["name"], "Retina Built-in")
        self.assertEqual(diag["screens"][0]["resolution"], "2880x1800")
        self.assertEqual(diag["screens"][0]["device_pixel_ratio"], 2.0)


if __name__ == "__main__":
    unittest.main()
