"""
Unit tests for Musicat GitHub Auto-Update Checker & In-App Downloader.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src import __version__
from src.core.settings import DEFAULT_SETTINGS, SettingsManager
from src.core.updater import (
    UpdateCheckerWorker,
    UpdateDownloadWorker,
    UpdateInfo,
    find_compatible_asset,
    is_version_newer,
    parse_clean_version,
)
from src.gui.updater_dialog import UpdateNotificationDialog
from src.gui.settings_dialog import SettingsDialog


class TestUpdaterEngine(unittest.TestCase):
    """Tests for core updater version comparison and asset matching."""

    def test_version_parsing_and_comparison(self):
        self.assertTrue(is_version_newer("1.2.1", "1.2.0"))
        self.assertTrue(is_version_newer("v1.3.0", "1.2.0"))
        self.assertTrue(is_version_newer("2.0.0", "1.2.0"))
        self.assertFalse(is_version_newer("1.2.0", "1.2.0"))
        self.assertFalse(is_version_newer("v1.2.0", "1.2.0"))
        self.assertFalse(is_version_newer("1.1.9", "1.2.0"))
        self.assertFalse(is_version_newer("1.0.0", "1.2.0"))

    def test_find_compatible_asset_windows_portable(self):
        assets = [
            {"name": "Musicat-Setup-Windows-x64.exe", "browser_download_url": "http://example.com/setup.exe", "size": 1000},
            {"name": "Musicat-Windows-Portable.zip", "browser_download_url": "http://example.com/portable.zip", "size": 2000},
            {"name": "SHA256SUMS.txt", "browser_download_url": "http://example.com/sums.txt", "size": 100},
        ]
        chosen = find_compatible_asset(assets, os_platform="win32", is_portable=True)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["name"], "Musicat-Windows-Portable.zip")

    def test_find_compatible_asset_windows_installer(self):
        assets = [
            {"name": "Musicat-Setup-Windows-x64.exe", "browser_download_url": "http://example.com/setup.exe", "size": 1000},
            {"name": "Musicat-Windows-Portable.zip", "browser_download_url": "http://example.com/portable.zip", "size": 2000},
        ]
        chosen = find_compatible_asset(assets, os_platform="win32", is_portable=False)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["name"], "Musicat-Setup-Windows-x64.exe")

    def test_find_compatible_asset_darwin(self):
        assets = [
            {"name": "Musicat-macOS.dmg", "browser_download_url": "http://example.com/mac.dmg", "size": 1500},
            {"name": "Musicat-Windows-Portable.zip", "browser_download_url": "http://example.com/portable.zip", "size": 2000},
        ]
        chosen = find_compatible_asset(assets, os_platform="darwin", is_portable=False)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["name"], "Musicat-macOS.dmg")

    def test_settings_default_has_updates(self):
        self.assertIn("updates", DEFAULT_SETTINGS)
        self.assertTrue(DEFAULT_SETTINGS["updates"].get("check_on_startup"))


class TestUpdateWorkers(unittest.TestCase):
    """Tests for asynchronous UpdateCheckerWorker and UpdateDownloadWorker."""

    def test_checker_worker_update_available(self):
        worker = UpdateCheckerWorker(current_version="1.0.0", is_manual=True)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v1.2.0",
            "name": "Musicat v1.2.0",
            "body": "## Bugfixes & New Features",
            "html_url": "https://github.com/IlRed89/Musicat/releases/tag/v1.2.0",
            "published_at": "2026-10-20T12:00:00Z",
            "assets": [
                {
                    "name": "Musicat-Windows-Portable.zip",
                    "browser_download_url": "https://github.com/IlRed89/Musicat/releases/download/v1.2.0/Musicat-Windows-Portable.zip",
                    "size": 150000000,
                }
            ],
        }

        received_info = []
        worker.update_available.connect(lambda info: received_info.append(info))

        with patch("requests.get", return_value=mock_resp):
            worker.run()

        self.assertEqual(len(received_info), 1)
        info = received_info[0]
        self.assertIsInstance(info, UpdateInfo)
        self.assertEqual(info.remote_version, "1.2.0")
        self.assertEqual(info.asset_name, "Musicat-Windows-Portable.zip")
        self.assertGreater(info.asset_size_mb, 100)

    def test_checker_worker_up_to_date(self):
        worker = UpdateCheckerWorker(current_version="1.2.0", is_manual=True)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v1.2.0",
            "name": "Musicat v1.2.0",
            "body": "Current release",
            "assets": [],
        }

        not_available_versions = []
        worker.update_not_available.connect(lambda ver: not_available_versions.append(ver))

        with patch("requests.get", return_value=mock_resp):
            worker.run()

        self.assertEqual(len(not_available_versions), 1)
        self.assertEqual(not_available_versions[0], "1.2.0")

    def test_checker_worker_rate_limited(self):
        worker = UpdateCheckerWorker(current_version="1.2.0", is_manual=True)

        mock_resp = MagicMock()
        mock_resp.status_code = 403

        failed_messages = []
        worker.check_failed.connect(lambda msg: failed_messages.append(msg))

        with patch("requests.get", return_value=mock_resp):
            worker.run()

        self.assertEqual(len(failed_messages), 1)
        self.assertIn("60 req/ora", failed_messages[0])

    def test_download_worker_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest_file = Path(tmp_dir) / "Musicat-Test.zip"

            worker = UpdateDownloadWorker(
                download_url="http://example.com/test.zip",
                destination_path=dest_file,
                expected_size=1024,
            )

            mock_resp = MagicMock()
            mock_resp.headers = {"content-length": "100"}
            mock_resp.iter_content.return_value = [b"a" * 50, b"b" * 50]
            mock_resp.__enter__.return_value = mock_resp

            progress_reports = []
            worker.download_progress.connect(lambda cur, tot: progress_reports.append((cur, tot)))
            finished_paths = []
            worker.download_finished.connect(lambda p: finished_paths.append(p))

            with patch("requests.get", return_value=mock_resp):
                worker.run()

            self.assertEqual(len(finished_paths), 1)
            self.assertTrue(dest_file.exists())
            self.assertEqual(dest_file.stat().st_size, 100)
            self.assertGreater(len(progress_reports), 0)


class TestUpdaterGui(unittest.TestCase):
    """Tests for UpdateNotificationDialog and SettingsDialog integration."""

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_dialog_instantiation_and_widgets(self):
        dummy_info = UpdateInfo(
            remote_version="1.3.0",
            local_version="1.2.0",
            tag_name="v1.3.0",
            release_name="Musicat v1.3.0 — The Big Update",
            release_notes="### What's Changed\n* Added auto-updater\n* Performance fixes",
            html_url="https://github.com/IlRed89/Musicat/releases/tag/v1.3.0",
            download_url="https://github.com/IlRed89/Musicat/releases/download/v1.3.0/Musicat-Windows-Portable.zip",
            asset_name="Musicat-Windows-Portable.zip",
            asset_size=155000000,
            published_at="2026-10-20T12:00:00Z",
        )

        dlg = UpdateNotificationDialog(dummy_info)
        self.assertIsNotNone(dlg)
        self.assertIn("v1.3.0", dlg.lbl_version_info.text())
        self.assertIn("Musicat-Windows-Portable.zip", dlg.lbl_asset_info.text())
        self.assertIsNotNone(dlg.btn_action)
        self.assertIsNotNone(dlg.btn_browser)
        self.assertIsNotNone(dlg.txt_notes)
        dlg.close()

    def test_settings_dialog_updater_controls(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "config.json"
            settings = SettingsManager(config_path=config_file)
            dlg = SettingsDialog(parent=None)
            self.assertTrue(hasattr(dlg, "grp_updates"))
            self.assertTrue(hasattr(dlg, "lbl_installed_ver"))
            self.assertTrue(hasattr(dlg, "chk_check_updates"))
            self.assertTrue(hasattr(dlg, "btn_check_updates_now"))
            self.assertTrue(dlg.chk_check_updates.isChecked())
            dlg.close()


if __name__ == "__main__":
    unittest.main()
