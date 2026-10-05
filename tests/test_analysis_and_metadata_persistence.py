"""
Unit Tests for Explicit Analysis Button, Async Background Worker,
Reconciler Dialog Layout/Localization, and Physical Tag Persistence.
"""

import sys
import unittest
import tempfile
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QHeaderView
from PySide6.QtCore import Qt

from src.core.db import Database
from src.gui.main_view import MainWindow, AsyncAnalysisWorker
from src.gui.live_filters import LiveFilterBar
from src.gui.reconciler_dialog import ReconcilerDialog
from src.tags.editor import AudioTagEditor
from src.core.i18n import _t


class TestAnalysisAndMetadataPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_persist.db"
        self.db = Database(self.db_path)

        # Create dummy test audio file (WAV)
        self.test_audio_path = Path(self.tmp_dir.name) / "TestArtist - TestTitle.wav"
        self._create_dummy_wav(self.test_audio_path)

        # Insert track record with merged artist/title in title and empty artist
        self.db.insert_track({
            "filepath": str(self.test_audio_path),
            "filename": self.test_audio_path.name,
            "title": "TestArtist - TestTitle",
            "artist": "",
            "album": "",
            "genre": "",
            "bpm": 0.0,
            "camelot_key": "",
            "musical_key": "",
        })

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def _create_dummy_wav(self, path: Path) -> None:
        import wave
        import struct
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            data = struct.pack("<h", 0) * 44100  # 1 sec silence
            wf.writeframes(data)

    def test_point1_toolbar_analyze_button(self):
        """Point 1: Dedicated [⚡ Analizza Selezionate] button in LiveFilterBar."""
        filter_bar = LiveFilterBar(self.db)
        self.assertTrue(hasattr(filter_bar, "btn_analyze"))
        self.assertIn("Analizza", filter_bar.btn_analyze.text())

        # Test signal emission
        emitted = []
        filter_bar.analyze_requested.connect(lambda: emitted.append(True))
        filter_bar.btn_analyze.click()
        self.assertEqual(len(emitted), 1)

    def test_point1_empty_selection_shows_notice(self):
        """Point 1: Clicking analyze with empty selection and empty library shows notice."""
        empty_db_path = Path(self.tmp_dir.name) / "empty.db"
        empty_db = Database(empty_db_path)
        window = MainWindow(db=empty_db)
        try:
            window.table_model.set_tracks([])
            window._on_toolbar_analyze_clicked()
            msg = window.status_bar.currentMessage()
            self.assertIn("Seleziona almeno una traccia", msg)
        finally:
            window.close()
            empty_db.close()

    def test_point2_async_analysis_worker(self):
        """Point 2: Background AsyncAnalysisWorker extracts features and splits Artist - Title."""
        track = self.db.get_track(str(self.test_audio_path))
        self.assertIsNotNone(track)

        worker = AsyncAnalysisWorker([track], self.db)
        progress_events = []
        completed_events = []
        finished_events = []

        worker.progress.connect(lambda c, t, n: progress_events.append((c, t, n)))
        worker.track_completed.connect(lambda tr: completed_events.append(tr))
        worker.finished.connect(lambda s, trs: finished_events.append((s, trs)))

        # Run synchronously for test verification
        worker.run()

        self.assertEqual(len(finished_events), 1)
        success_count, updated_tracks = finished_events[0]
        self.assertEqual(success_count, 1)

        # Check clean separation of Artist and Title
        updated_tr = updated_tracks[0]
        self.assertEqual(updated_tr.get("artist"), "TestArtist")
        self.assertEqual(updated_tr.get("title"), "TestTitle")

        # Check SQLite DB persistence
        db_track = self.db.get_track(str(self.test_audio_path))
        self.assertEqual(db_track.get("artist"), "TestArtist")
        self.assertEqual(db_track.get("title"), "TestTitle")

    def test_point2_async_analysis_cancellation(self):
        """Point 2: Worker responds to cancellation."""
        tracks = [self.db.get_track(str(self.test_audio_path))] * 5
        worker = AsyncAnalysisWorker(tracks, self.db)
        worker.cancel()

        cancelled_events = []
        worker.cancelled.connect(lambda: cancelled_events.append(True))
        worker.run()
        self.assertEqual(len(cancelled_events), 1)

    def test_point3_and_4_reconciler_dialog_layout_and_i18n(self):
        """Points 3 & 4: ReconcilerDialog minimum dimensions, 4 columns, section size, Italian i18n."""
        track = self.db.get_track(str(self.test_audio_path))
        dlg = ReconcilerDialog(track)
        try:
            # Min dimensions >= 900x600 px
            self.assertGreaterEqual(dlg.minimumWidth(), 900)
            self.assertGreaterEqual(dlg.minimumHeight(), 600)
            self.assertTrue(dlg.isSizeGripEnabled())

            # Check 4 columns
            tbl = dlg.table_discrepancies
            self.assertEqual(tbl.columnCount(), 4)
            self.assertEqual(tbl.horizontalHeaderItem(0).text(), "Campo")
            self.assertEqual(tbl.horizontalHeaderItem(1).text(), "Valore Attuale")
            self.assertEqual(tbl.horizontalHeaderItem(2).text(), "Valore Rilevato (Online)")
            self.assertEqual(tbl.horizontalHeaderItem(3).text(), "Valore da Applicare")

            # Check column resize modes: 0 & 1 ResizeToContents, 2 & 3 Stretch
            header = tbl.horizontalHeader()
            self.assertEqual(header.sectionResizeMode(0), QHeaderView.ResizeMode.ResizeToContents)
            self.assertEqual(header.sectionResizeMode(1), QHeaderView.ResizeMode.ResizeToContents)
            self.assertEqual(header.sectionResizeMode(2), QHeaderView.ResizeMode.Stretch)
            self.assertEqual(header.sectionResizeMode(3), QHeaderView.ResizeMode.Stretch)

            # Check row height >= 32px
            self.assertGreaterEqual(tbl.verticalHeader().defaultSectionSize(), 32)

            # Check buttons localized
            self.assertEqual(dlg.btn_apply.text(), "Salva Modifiche nei File")
            self.assertEqual(dlg.btn_cancel.text(), "Annulla")
            self.assertIn("Avvia Ricerca Online", dlg.btn_search.text())
        finally:
            if dlg.search_worker and dlg.search_worker.isRunning():
                dlg.search_worker.quit()
                dlg.search_worker.wait()
            dlg.close()

    def test_point5_tag_editor_artist_title_split_and_persistence(self):
        """Point 5: AudioTagEditor cleanly separates keys and splits 'Artist - Title'."""
        tags_input = {
            "title": "CleanArtist - CleanTitle",
            "artist": "",
            "album": "CleanAlbum",
            "genre": "Tech House",
            "year": 2025,
            "bpm": 126.0,
            "initialkey": "8A",
        }

        # Write to physical file
        ok = AudioTagEditor.write_metadata(self.test_audio_path, tags_input)
        self.assertTrue(ok)

        # Read back from physical tags
        meta = AudioTagEditor.read_metadata(self.test_audio_path)
        self.assertEqual(meta.artist, "CleanArtist")
        self.assertEqual(meta.title, "CleanTitle")
        self.assertEqual(meta.album, "CleanAlbum")
        self.assertEqual(meta.genre, "Tech House")
        self.assertEqual(meta.year, 2025)
        self.assertEqual(meta.bpm, 126.0)
        self.assertEqual(meta.camelot_key, "8A")


if __name__ == "__main__":
    unittest.main()
