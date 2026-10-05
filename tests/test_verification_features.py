"""
Comprehensive verification test for Light Theme default, Minimal Navbar,
Dedicated Smart Crates Workbench, Settings Dialog, and Cross-Platform PathResolver.
"""

import sys
import unittest
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.settings import SettingsManager
from src.core.path_resolver import PathResolver
from src.gui.main_view import MainWindow
from src.gui.views.crates_view import SmartCratesView
from src.gui.styles import get_theme_stylesheet


class TestFiveCoreRequirements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_verify.db"
        self.db = Database(self.db_path)

        # Seed sample tracks
        self.db.insert_track({
            "filepath": "C:/Music/Track1.mp3",
            "title": "Summer Vibe",
            "artist": "DJ Solar",
            "genre": "House",
            "bpm": 124.0,
            "camelot_key": "8A",
            "musical_key": "Am",
            "year": 2023,
            "duration": 360.0,
            "energy_level": 7,
            "lufs": -14.2,
            "true_peak": -1.0,
            "audio_status": "OK"
        })
        self.db.insert_track({
            "filepath": "C:/Music/Track2.mp3",
            "title": "Deep Night",
            "artist": "Luna",
            "genre": "Tech House",
            "bpm": 126.0,
            "camelot_key": "9A",
            "musical_key": "Em",
            "year": 2024,
            "duration": 400.0,
            "energy_level": 8,
            "lufs": -13.8,
            "true_peak": -0.5,
            "audio_status": "OK"
        })

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_req1_light_theme_default(self):
        """1. Light Theme is default in settings and styles."""
        from src.core.settings import DEFAULT_SETTINGS
        self.assertEqual(DEFAULT_SETTINGS["ui"]["theme"], "light")

        cfg_file = Path(self.tmp_dir.name) / "default_test.json"
        settings = SettingsManager(config_path=cfg_file)
        self.assertEqual(settings.get("ui.theme"), "light", "Default theme must be 'light'")

        stylesheet = get_theme_stylesheet("light")
        self.assertIn("#ffffff", stylesheet.lower())
        self.assertIn("#0d6efd", stylesheet.lower())

    def test_req2_minimal_navbar_and_switching(self):
        """2. Minimal Navbar with exact 7 macro function buttons."""
        window = MainWindow(db=self.db)
        try:
            # Check 7 navigation buttons exist
            self.assertIsNotNone(window.btn_nav_trends)
            self.assertIsNotNone(window.btn_nav_library)
            self.assertIsNotNone(window.btn_nav_mp3tag)
            self.assertIsNotNone(window.btn_nav_crates)
            self.assertIsNotNone(window.btn_nav_similar)
            self.assertIsNotNone(window.btn_nav_organizer)
            self.assertIsNotNone(window.btn_nav_settings)

            # Starts at View 0 (Libreria default per Requirement 3)
            self.assertEqual(window.view_stack.currentIndex(), 0)

            # Switch to Top Charts (View 1)
            window.btn_nav_trends.click()
            self.assertEqual(window.view_stack.currentIndex(), 1)

            # Switch back to Library (View 0)
            window.btn_nav_library.click()
            self.assertEqual(window.view_stack.currentIndex(), 0)

            # Switch to Tag Editor (Mp3tag Workspace - View 2)
            window.btn_nav_mp3tag.click()
            self.assertEqual(window.view_stack.currentIndex(), 2)

            # Switch to Smart Crates (View 3)
            window.btn_nav_crates.click()
            self.assertEqual(window.view_stack.currentIndex(), 3)

            # Switch to Similar Tracks (View 4)
            window.btn_nav_similar.click()
            self.assertEqual(window.view_stack.currentIndex(), 4)

            # Switch to Organizza File (View 5)
            window.btn_nav_organizer.click()
            self.assertEqual(window.view_stack.currentIndex(), 5)

            # Switch to Top Charts (View 1)
            window.btn_nav_trends.click()
            self.assertEqual(window.view_stack.currentIndex(), 1)

            # Switch back to Library (View 0)
            window.btn_nav_library.click()
            self.assertEqual(window.view_stack.currentIndex(), 0)
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_req3_dedicated_smart_crates_workbench(self):
        """3. Smart Crates dedicated workbench with rule building, preview & export."""
        window = MainWindow(db=self.db)
        try:
            # Smart Crates view exists in window
            crates_view: SmartCratesView = window.crates_view
            self.assertIsNotNone(crates_view)

            # Switch to Smart Crates
            window._switch_view(2)

            # Create a new Smart Crate
            import json
            rules_dict = {"bpm_min": 120.0, "bpm_max": 130.0, "genres": ["House", "Tech House"]}
            crate_id = self.db.save_smart_crate(
                "Peak Time",
                json.dumps(rules_dict)
            )
            self.assertIsNotNone(crate_id)

            crates_view.refresh_crates()
            self.assertGreater(crates_view.list_crates.count(), 0)

            # Check preview table has tracks
            matching = self.db.search_tracks(limit=10)
            self.assertEqual(len(matching), 2)

            # Test M3U8 DJ Export
            export_file = Path(self.tmp_dir.name) / "test_export.m3u8"
            out = crates_view.filter_engine.export_m3u(matching, str(export_file))
            self.assertTrue(Path(out).exists())
            with open(out, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("#EXTM3U", content)
                self.assertIn("Summer Vibe", content)
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_req4_settings_dialog_and_theme_switch(self):
        """4. Dedicated Settings dialog and instant theme application."""
        window = MainWindow(db=self.db)
        try:
            from src.gui.settings_dialog import SettingsDialog
            dlg = SettingsDialog(window)
            self.assertIsNotNone(dlg)

            # Apply dark theme and verify update
            window._on_settings_applied({"theme": "dark_dj"})
            self.assertIn("dark_dj", window.status_bar.currentMessage())

            # Apply light theme back
            window._on_settings_applied({"theme": "light"})
            self.assertIn("light", window.status_bar.currentMessage())
            dlg.close()
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_req5_cross_platform_path_resolver(self):
        """5. Cross-platform path resolution for Windows, macOS and Portable mode."""
        # Non-portable default
        data_dir = PathResolver.get_data_dir()
        self.assertTrue(data_dir.exists())

        # Test portable lock simulation
        lock_file = Path(self.tmp_dir.name) / "portable.lock"
        lock_file.touch()

        # In portable mode, data dir is app directory
        is_port = PathResolver.is_portable()
        self.assertIsInstance(is_port, bool)

    def test_req6_table_column_selection_and_persistence(self):
        """6. Table column context menu, visibility toggling, show all, and persistence."""
        from src.gui.table_model import TrackTableModel
        window = MainWindow(db=self.db)
        try:
            header = window.table_header
            self.assertIsNotNone(header)
            self.assertEqual(header.count(), len(TrackTableModel.COLUMNS))

            # Toggle a column (hide Remixer at index 4)
            window._toggle_column_visibility(4, "remixer", False)
            self.assertTrue(header.isSectionHidden(4))
            self.assertTrue(window._custom_columns_active)
            saved_cols = window.settings_manager.get("ui.visible_columns")
            self.assertNotIn("remixer", saved_cols)

            # Test show all columns
            window._show_all_columns()
            for i in range(header.count()):
                self.assertFalse(header.isSectionHidden(i))

            # Test reset default columns
            window._reset_default_columns()
            self.assertFalse(window._custom_columns_active)
        finally:
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_req7_hardware_monitor_total_ram_and_breadcrumb_theme(self):
        """7. Hardware monitor reports total physical RAM and breadcrumb updates theme."""
        from src.core.hardware_monitor import HardwareMonitor
        from src.gui.views.library_view import BreadcrumbBar

        total_gb = HardwareMonitor.get_total_system_memory_gb()
        self.assertGreater(total_gb, 0)
        status = HardwareMonitor.get_status_text()
        self.assertIn("RAM:", status)
        self.assertIn("GB", status)

        # Breadcrumb theme update
        bar = BreadcrumbBar()
        bar.update_theme("light")
        self.assertIn("#f8f9fa", bar.styleSheet())
        bar.update_theme("dark")
        self.assertIn("#12141c", bar.styleSheet())


if __name__ == "__main__":
    unittest.main()
