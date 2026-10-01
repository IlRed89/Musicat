"""
Unit Tests for Cross-Platform PathResolver (Windows drive letters & macOS /Volumes/).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.path_resolver import PathResolver


class TestPathResolverCrossPlatform(unittest.TestCase):
    """Tests portable path translation across Windows, macOS, and Linux."""

    def test_standard_data_dir_per_platform(self):
        """Verifies OS-specific data directory resolution."""
        # 1. macOS: ~/Library/Application Support/Musicat
        with patch("sys.platform", "darwin"), patch.object(PathResolver, "is_portable_mode", return_value=False):
            data_dir = PathResolver.get_data_dir()
            expected = Path.home() / "Library" / "Application Support" / "Musicat"
            self.assertEqual(data_dir, expected)

        # 2. Linux: ~/.config/musicat
        with patch("sys.platform", "linux"), patch.object(PathResolver, "is_portable_mode", return_value=False):
            data_dir = PathResolver.get_data_dir()
            expected = Path.home() / ".config" / "musicat"
            self.assertEqual(data_dir, expected)

        # 3. Windows: %APPDATA%/Musicat
        with patch("sys.platform", "win32"), patch.object(PathResolver, "is_portable_mode", return_value=False):
            data_dir = PathResolver.get_data_dir()
            self.assertIn("Musicat", str(data_dir))

    def test_mac_volumes_portable_translation(self):
        """Verifies macOS /Volumes/DiskName/ paths are translated to [VOL:DiskName] tokens."""
        sample_mac_path = "/Volumes/DJ_SSD/House/Carl_Cox.mp3"
        portable, vol_id = PathResolver.to_portable_path(sample_mac_path)

        self.assertEqual(portable, "[VOL:DJ_SSD]/House/Carl_Cox.mp3")
        self.assertEqual(vol_id, "DJ_SSD")

    def test_app_relative_portable_translation(self):
        """Verifies paths inside the app directory are translated to [APP]/ token."""
        app_dir = PathResolver.get_app_dir()
        track_in_app = app_dir / "musicat_data" / "demo.mp3"
        portable, vol_id = PathResolver.to_portable_path(str(track_in_app))

        self.assertTrue(portable.startswith("[APP]/"))
        self.assertIsNone(vol_id)

        # Resolving back
        resolved = PathResolver.to_absolute_path(portable)
        self.assertEqual(Path(resolved), track_in_app.resolve())


if __name__ == "__main__":
    unittest.main()
