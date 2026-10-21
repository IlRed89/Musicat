import unittest
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
from src.gui.styles import get_theme_stylesheet
from src.gui.mp3tag_workspace import Mp3tagWorkspaceWindow
from src.gui.settings_dialog import GpuDiagnosticDialog
from src.gui.sorter_dialog import SorterDialog

class TestUiRefinements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(get_theme_stylesheet('light'))

    def test_mp3tag_columns_autosize(self):
        sample_tracks = [{
            'filename': 'A long sample filename for testing column auto-sizing.mp3',
            'title': 'Very Long Extended Title Example',
            'artist': 'Artist Name Here',
            'album': 'Album Name Here',
            'directory': 'C:/Music/Path/Example'
        }]
        win = Mp3tagWorkspaceWindow(sample_tracks)
        widths = [win.grid.columnWidth(c) for c in range(win.grid.columnCount())]
        self.assertGreater(widths[0], 200, "Filename column should fit long content")
        self.assertGreater(widths[1], 150, "Title column should fit long content")

    def test_gpu_diagnostic_dialog_instantiation(self):
        dlg = GpuDiagnosticDialog()
        self.assertIsNotNone(dlg)
        self.assertTrue(dlg.lbl_active_badge.text())

    def test_sorter_dialog_radio_buttons(self):
        dlg = SorterDialog()
        self.assertFalse(dlg.radio_selected.isChecked())
        self.assertTrue(dlg.radio_folder.isChecked())
        dlg.radio_selected.setChecked(True)
        self.assertTrue(dlg.radio_selected.isChecked())
        self.assertFalse(dlg.radio_folder.isChecked())

if __name__ == '__main__':
    unittest.main()
