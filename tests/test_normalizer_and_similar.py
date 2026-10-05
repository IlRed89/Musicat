"""
Comprehensive Test Suite for:
1. Physical Normalization MP3 Export (loudnorm -> .mp3 @ 320k with tags & artwork preserved)
2. Auto-Indexing via LibraryScanner.scan_file()
3. TrackTableModel Non-Blank Fallback Rendering
4. DJ Library Toolbar [🔄 Aggiorna] Button & Signal Integration
5. DualWaveformWidget (Before vs After) & Active Radio Option Highlighting
6. SimilarTracksView Recommendation Engine Integration
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.core.db import Database
from src.core.scanner import LibraryScanner
from src.gui.live_filters import LiveFilterBar
from src.gui.table_model import TrackTableModel
from src.gui.views.quality_view import DualWaveformWidget, QualityDiagnosisDialog
from src.gui.views.similar_view import SimilarTracksView
from src.plugins.quality_analyzer.normalizer import VolumeNormalizer
from src.scrapers.similarity_engine import SimilarTrackRecommendation, SimilarityResult
from src.tags.editor import AudioTagEditor


app = QApplication.instance() or QApplication([])


class TestPhysicalNormalizerMp3Export(unittest.TestCase):
    """Verifies that physical normalization outputs high-quality MP3 files and copies ID3 tags/artwork."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.normalizer = VolumeNormalizer()

        # Generate a dummy 1-second sine wave WAV
        sr = 44100
        t = np.linspace(0, 1.0, sr, endpoint=False)
        sig = (np.sin(2 * np.pi * 440.0 * t) * 0.8 * 32767).astype(np.int16)
        self.wav_path = Path(self.tmp_dir) / "Artist Name - Test Song.wav"
        wavfile.write(str(self.wav_path), sr, sig)

        # Set some tags on the source file
        AudioTagEditor.write_metadata(
            str(self.wav_path),
            {
                "title": "Test Song",
                "artist": "Artist Name",
                "genre": "Melodic Techno",
                "year": 2026,
                "bpm": 126.0,
            },
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ffmpeg_executable_found(self):
        ffmpeg_bin = self.normalizer._find_ffmpeg_executable()
        self.assertIsNotNone(ffmpeg_bin, "FFmpeg executable must be located in bin/ or system PATH")
        self.assertTrue(Path(ffmpeg_bin).exists() or shutil.which(ffmpeg_bin))

    def test_apply_physical_loudnorm_produces_mp3(self):
        res = self.normalizer.apply_physical_loudnorm(
            filepath=str(self.wav_path),
            target_lufs=-10.0,
            max_true_peak=-1.0,
            target_lra=7.0,
            save_as_fixed=True,
            create_backup=False,
        )

        self.assertTrue(res.success, f"Normalization failed: {res.error_message}")
        out_path = Path(res.output_filepath)
        self.assertTrue(out_path.exists(), "Exported file must exist physically")
        self.assertEqual(out_path.suffix.lower(), ".mp3", "Exported file must have .mp3 extension")
        self.assertTrue(out_path.name.endswith("_normalized.mp3"))

        # Verify tags were copied to destination MP3
        meta = AudioTagEditor.read_metadata(str(out_path))
        self.assertEqual(meta.title, "Test Song")
        self.assertEqual(meta.artist, "Artist Name")
        self.assertEqual(meta.genre, "Melodic Techno")


class TestLibraryScannerSingleFileAndTableModel(unittest.TestCase):
    """Verifies single-track instant SQLite indexing and non-empty table rendering fallbacks."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test.db"
        self.db = Database(str(self.db_path))
        self.scanner = LibraryScanner(self.db)

        # Create a test audio file
        sr = 44100
        t = np.linspace(0, 0.5, sr // 2, endpoint=False)
        sig = (np.sin(2 * np.pi * 440.0 * t) * 0.5 * 32767).astype(np.int16)
        self.test_mp3 = Path(self.tmp_dir) / "Unknown Artist - Mystery Track.mp3"
        wavfile.write(str(self.test_mp3), sr, sig)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_scan_file_inserts_and_updates_db(self):
        track_dict = self.scanner.scan_file(str(self.test_mp3))
        self.assertIsNotNone(track_dict)
        self.assertEqual(Path(track_dict["filepath"]).resolve(), self.test_mp3.resolve())

        # Check DB retrieval
        row = self.db.get_track_by_path(str(self.test_mp3.resolve()))
        self.assertIsNotNone(row)
        self.assertEqual(row["filename"], self.test_mp3.name)

    def test_table_model_fallback_prevents_blank_rows(self):
        model = TrackTableModel()
        # Row with missing title/artist metadata
        empty_track = {
            "id": 99,
            "filepath": "C:/Music/Calvin Harris - Summer.mp3",
            "filename": "Calvin Harris - Summer.mp3",
            "title": "",
            "artist": "",
            "bpm": None,
            "camelot_key": None,
            "duration": None,
            "bitrate": None,
            "audio_status": "NORMAL",
        }
        model.set_tracks([empty_track])

        # Title column (col 2) should fall back to filename stem or parsed title
        idx_title = model.index(0, 2)
        title_val = model.data(idx_title, Qt.ItemDataRole.DisplayRole)
        self.assertIn("Summer", str(title_val))

        # Artist column (col 3) should fall back to stem split
        idx_artist = model.index(0, 3)
        artist_val = model.data(idx_artist, Qt.ItemDataRole.DisplayRole)
        self.assertEqual(artist_val, "Calvin Harris")

        # BPM column (col 5) should fall back to '--'
        idx_bpm = model.index(0, 5)
        bpm_val = model.data(idx_bpm, Qt.ItemDataRole.DisplayRole)
        self.assertEqual(bpm_val, "--")

        # Time column (col 12) should fall back to '--:--'
        idx_time = model.index(0, 12)
        time_val = model.data(idx_time, Qt.ItemDataRole.DisplayRole)
        self.assertEqual(time_val, "--:--")


class TestToolbarRefreshButtonAndDualWaveform(unittest.TestCase):
    """Verifies the Refresh button and the Dual Waveform widget."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db = Database(str(Path(self.tmp_dir) / "test.db"))

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_toolbar_refresh_button_and_signal(self):
        bar = LiveFilterBar(self.db)
        self.assertTrue(hasattr(bar, "btn_refresh"))
        self.assertIn("Aggiorna", bar.btn_refresh.text())

        signal_emitted = []
        bar.refresh_requested.connect(lambda: signal_emitted.append(True))
        bar.btn_refresh.click()
        self.assertTrue(len(signal_emitted) == 1, "refresh_requested signal must be emitted on click")

    def test_dual_waveform_widget_processing(self):
        peaks = np.linspace(0.1, 1.0, 100)
        widget = DualWaveformWidget()
        widget.set_data(peaks, orig_lufs=-7.0, orig_tp=1.5, target_lufs=-10.0, max_tp=-1.0)

        self.assertTrue(widget._has_data, "Waveform data must be set")
        self.assertEqual(len(widget._peaks), 100)
        self.assertEqual(widget._orig_tp, 1.5)

        # Update target and check target targets
        widget.update_targets(target_lufs=-12.0, max_tp=-2.0)
        self.assertEqual(widget._target_lufs, -12.0)
        self.assertEqual(widget._max_tp, -2.0)


class TestSimilarTracksEngineIntegration(unittest.TestCase):
    """Verifies SimilarTracksView integration with Recommendation Engine attributes."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db = Database(str(Path(self.tmp_dir) / "test.db"))

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_similar_tracks_view_population_without_errors(self):
        view = SimilarTracksView(self.db)

        seed_track = {
            "id": 1,
            "filepath": "C:/Music/test.mp3",
            "filename": "test.mp3",
            "title": "Losing It",
            "artist": "FISHER",
            "bpm": 125.0,
            "camelot_key": "8A",
            "genre": "Tech House",
        }

        rec1 = SimilarTrackRecommendation(
            title="San Frandisco",
            artist="Dom Dolla",
            similarity_pct=92.5,
            affinity_reasons=["BPM Compatibile (125)", "Chiave Armonica (8A)"],
            bpm=125.0,
            camelot_key="8A",
            genre="Tech House",
            in_library=True,
            local_filepath="C:/Music/Dom Dolla - San Frandisco.mp3",
        )

        rec2 = SimilarTrackRecommendation(
            title="Moving Blind",
            artist="Sonny Fodera",
            similarity_pct=88.0,
            affinity_reasons=["Affinità Sonora Chosic"],
            bpm=124.0,
            camelot_key="9A",
            genre="Tech House",
            in_library=False,
            source="chosic",
        )

        result = SimilarityResult(
            reference_track=seed_track,
            local_similar_tracks=[rec1],
            discovery_tracks=[rec2],
        )

        # Call completion handler without throwing AttributeError
        view._on_search_completed(result)

        self.assertEqual(view.table_local.rowCount(), 1)
        self.assertEqual(view.table_online.rowCount(), 1)

        # Check values in table_local
        self.assertEqual(view.table_local.item(0, 2).text(), "San Frandisco")
        self.assertEqual(view.table_local.item(0, 3).text(), "Dom Dolla")
        self.assertEqual(view.table_local.item(0, 4).text(), "125.0")

        # Check values in table_online
        self.assertEqual(view.table_online.item(0, 2).text(), "Moving Blind")
        self.assertEqual(view.table_online.item(0, 3).text(), "Sonny Fodera")


if __name__ == "__main__":
    unittest.main()


