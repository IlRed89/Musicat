"""
Comprehensive Unit Tests for:
1. Enhanced Multi-Source Scraping Fallback & Intelligent Genre Normalization
2. Interactive Column Reordering & Header State Persistence
3. Genre ComboBox Dynamic-Only Population & Arrow Styling
4. Superfluous Columns Removal from Default Table View
5. Player Loudness Meter Deactivation on Unanalyzed Tracks & Correggi Audio Modal
"""

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QTableView

from src.core.db import Database
from src.core.settings import SettingsManager
from src.gui.live_filters import GenreMultiSelectWidget
from src.gui.main_view import (
    DEFAULT_COLUMN_WIDTHS,
    DEFAULT_VISIBLE_COLUMN_IDS,
    MainWindow,
)
from src.gui.table_model import TrackTableModel
from src.gui.views.quality_view import LoudnessMeterBar, QualityDiagnosisDialog
from src.scrapers.reconciler import MetadataReconciler
from src.scrapers.web_enricher import WebEnricher


# Ensure QApplication instance exists for GUI tests
app = QApplication.instance() or QApplication([])


class TestGenreNormalizationAndCascadingFallback(unittest.TestCase):
    """Verifies that genre normalization avoids generic labels and picks specific subgenres."""

    def test_clean_and_normalize_genre_generic_rejection(self):
        # Generic labels must return None
        for g in ["Other", "unknown", "Soundtrack", "OST", "various", "Vario", "None", "N/A"]:
            self.assertIsNone(MetadataReconciler.clean_and_normalize_genre(g))

    def test_clean_and_normalize_genre_subgenre_preference(self):
        # In combined genre strings, specific electronic subgenre must take precedence over broad genre
        norm = MetadataReconciler.clean_and_normalize_genre("Electronic, Tech House")
        self.assertEqual(norm, "Tech House")

        norm2 = MetadataReconciler.clean_and_normalize_genre("Dance / Melodic Techno")
        self.assertEqual(norm2, "Melodic Techno")

        norm3 = MetadataReconciler.clean_and_normalize_genre("Deep House")
        self.assertEqual(norm3, "Deep House")

    def test_reconciler_select_recommended_genre_priority(self):
        # If Beatport provides specific subgenre and Discogs provides broad "Electronic"
        source_vals = {
            "Discogs": "Electronic",
            "Beatport": "Tech House",
            "MusicBrainz": "Dance",
        }
        rec_genre = MetadataReconciler._select_recommended_genre(source_vals)
        self.assertEqual(rec_genre, "Tech House")

    def test_reconciler_select_recommended_genre_vario_as_last_resort(self):
        # If all sources are generic or empty, fallback must be "Vario"
        source_vals = {
            "Discogs": "Other",
            "MusicBrainz": "Unknown",
            "Current File": "Soundtrack",
        }
        rec_genre = MetadataReconciler._select_recommended_genre(source_vals)
        self.assertEqual(rec_genre, "Vario")

    def test_reconciler_select_recommended_year_priority(self):
        # Discogs is gold standard for earliest release year
        source_vals = {
            "Discogs": 2018,
            "MusicBrainz": 2019,
            "Beatport": 2021,
        }
        rec_year = MetadataReconciler._select_recommended_year(source_vals)
        self.assertEqual(rec_year, 2018)

    def test_web_enricher_wikipedia_parsing(self):
        # WebEnricher lookup for famous electronic anthem
        res = WebEnricher.search_genre_and_year("Fisher", "Losing It")
        if res:
            self.assertEqual(res.get("source"), "Web/YouTube")
            self.assertIn(res.get("year"), (2018, 2019))
            self.assertIn("House", res.get("genre", ""))


class TestTableColumnsAndHeaderStatePersistence(unittest.TestCase):
    """Verifies column drag & drop, default visible columns, and state persistence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(str(self.db_path))

    def tearDown(self):
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_default_columns_exclude_superfluous_fields(self):
        # Default visible columns must contain the 12 essential DJ fields
        self.assertEqual(
            DEFAULT_VISIBLE_COLUMN_IDS,
            ["id", "has_cover", "title", "artist", "remixer", "bpm",
             "camelot_key", "musical_key", "genre", "year", "duration", "bitrate"]
        )

        # Superfluous fields must not be in default visible columns
        superfluous = ["energy_level", "lufs", "true_peak", "audio_status"]
        for col in superfluous:
            self.assertNotIn(col, DEFAULT_VISIBLE_COLUMN_IDS)

    def test_header_state_hex_serialization_and_restoration(self):
        tv = QTableView()
        model = TrackTableModel()
        tv.setModel(model)
        header = tv.horizontalHeader()
        header.setSectionsMovable(True)

        # Move column 2 (Title) to position 0
        header.moveSection(header.visualIndex(2), 0)
        self.assertEqual(header.visualIndex(2), 0)

        # Save state to hex
        raw_state = header.saveState()
        hex_str = bytes(raw_state.toHex().data()).decode("ascii")

        # New header restores state
        tv2 = QTableView()
        tv2.setModel(model)
        header2 = tv2.horizontalHeader()
        header2.setSectionsMovable(True)
        restored = header2.restoreState(QByteArray.fromHex(hex_str.encode("ascii")))
        self.assertTrue(restored)
        self.assertEqual(header2.visualIndex(2), 0)

    def test_genre_combobox_dynamic_only_population(self):
        # Insert 2 tracks with specific genres and 1 with empty genre
        self.db.insert_track({
            "filepath": "C:/Music/t1.mp3",
            "filename": "t1.mp3",
            "genre": "Afro House",
        })
        self.db.insert_track({
            "filepath": "C:/Music/t2.mp3",
            "filename": "t2.mp3",
            "genre": "Melodic Techno",
        })

        widget = GenreMultiSelectWidget(self.db)
        items = [widget.itemText(i) for i in range(widget.count())]

        # Item 0 must be 'Tutti i Generi'
        self.assertEqual(items[0], "🏷️ Tutti i Generi")
        # Middle items must only be the DB distinct genres
        self.assertIn("Afro House", items)
        self.assertIn("Melodic Techno", items)
        # Last item must be 'Vario'
        self.assertEqual(items[-1], "Vario")

        # Hardcoded genres that were not inserted must NOT be present
        self.assertNotIn("Psy-Trance", items)
        self.assertNotIn("Hard Techno", items)
        widget.close()


class TestPlayerLoudnessAndQualityDialog(unittest.TestCase):
    """Verifies unanalyzed loudness meter deactivation and light theme QualityDiagnosisDialog."""

    def test_loudness_meter_bar_clear_metrics(self):
        bar = LoudnessMeterBar()
        self.assertFalse(bar._has_metrics)
        self.assertIsNone(bar._lufs)
        self.assertIsNone(bar._true_peak)

        # Dummy readings (-70.0, -100.0) must be rejected and marked unanalyzed
        bar.set_metrics(-70.0, -100.0, "OK")
        self.assertFalse(bar._has_metrics)
        self.assertIsNone(bar._lufs)

        # Valid measurements must be accepted
        bar.set_metrics(-10.5, -0.8, "OK")
        self.assertTrue(bar._has_metrics)
        self.assertEqual(bar._lufs, -10.5)
        self.assertEqual(bar._true_peak, -0.8)

        # Calling clear_metrics must reset to deactivated
        bar.clear_metrics()
        self.assertFalse(bar._has_metrics)
        self.assertIsNone(bar._lufs)

    def test_quality_diagnosis_dialog_initialization(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_file = Path(tmp_dir) / "test_track.mp3"
            dummy_file.write_bytes(b"dummy mp3 data")

            dlg = QualityDiagnosisDialog(str(dummy_file))
            # Verify target sliders exist and have contextual tooltips
            self.assertIsNotNone(dlg.slider_lufs)
            self.assertIsNotNone(dlg.slider_tp)
            self.assertIn("LUFS", dlg.slider_lufs.toolTip())
            self.assertIn("dBTP", dlg.slider_tp.toolTip())

            # Verify dialog defaults
            self.assertEqual(dlg.slider_lufs.value(), -10)
            self.assertEqual(dlg.slider_tp.value(), -10)  # -1.0 dBTP
            dlg.close()


if __name__ == "__main__":
    unittest.main()
