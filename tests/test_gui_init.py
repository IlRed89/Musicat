"""
Unit tests for Musicat GUI components and MainWindow initialization.
"""

import sys
import unittest
import tempfile
from pathlib import Path

# Ensure project root in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.settings import SettingsManager
from src.core.i18n import I18n


class TestGuiInitialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()
        SettingsManager.get_instance()
        I18n.get_instance("it_IT")

    def test_main_window_and_views_instantiation(self):
        from src.gui.main_view import MainWindow
        from src.gui.settings_dialog import SettingsDialog
        from src.gui.analysis_dialog import AcousticAnalysisDialog
        from src.gui.views.quality_view import QualityDiagnosisDialog
        from src.gui.views.similar_dialog import SimilarTracksDialog
        from src.gui.live_filters import CamelotWheelDialog

        with tempfile.TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "test_gui.db"
            db = Database(db_file)
            window = MainWindow(db=db)
            self.assertIsNotNone(window)
            self.assertIsNotNone(window.filter_bar)
            self.assertIsNotNone(window.player_widget)
            self.assertTrue(hasattr(window.player_widget.breadcrumb_bar, "directory_selected"))
            self.assertTrue(hasattr(window.db, "get_crates"))
            self.assertTrue(hasattr(window.home_view, "refresh_library_status"))
            self.assertIsNotNone(window.crates_view)

            # Test switching views across all 6 workspaces
            for view_idx in range(6):
                window._switch_view(view_idx)
                self.assertEqual(window.view_stack.currentIndex(), view_idx)
            window._switch_view(0)

            # Test dialogs
            dlg_settings = SettingsDialog(window)
            self.assertIsNotNone(dlg_settings)

            dlg_analysis = AcousticAnalysisDialog([], db, window)
            self.assertIsNotNone(dlg_analysis)

            dlg_quality = QualityDiagnosisDialog("test.mp3", db=db, parent=window)
            self.assertIsNotNone(dlg_quality)

            dlg_similar = SimilarTracksDialog({"title": "T", "artist": "A"}, db, window, auto_start=False)
            self.assertIsNotNone(dlg_similar)
            dlg_similar.cleanup()

            dlg_camelot = CamelotWheelDialog("8A", window)
            self.assertIsNotNone(dlg_camelot)

            # Cleanup Qt widgets to prevent fast-fail on process exit
            dlg_settings.close()
            dlg_analysis.close()
            dlg_quality.close()
            dlg_similar.close()
            dlg_camelot.close()
            window.close()
            window.deleteLater()
            self.app.processEvents()
            db.close()



if __name__ == "__main__":
    unittest.main()
