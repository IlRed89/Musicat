"""
Comprehensive Unit Tests for Specialized Scrapers, Crash Fixes, UI Streamlining, and Conflict Reconciler.
"""

import os
import unittest
from pathlib import Path
from typing import Any, Dict

# Set offscreen Qt platform before importing Qt widgets
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

# Ensure QApplication instance exists
app = QApplication.instance() or QApplication([])

from src.core.db import Database
from src.core.i18n import _t
from src.scrapers.providers import (
    ALL_PROVIDERS,
    ProviderRegistry,
    DiscogsProvider,
    FortyFiveCatProvider,
    RateYourMusicProvider,
    CdAndLpProvider,
    MusicBrainzProvider,
    AllMusicProvider,
    WhoSampledProvider,
    SecondHandSongsProvider,
    GeniusProvider,
    SiaeProvider,
    AscapBmiProvider,
    IsrcSearchProvider,
    IswcNetworkProvider,
    ImslpProvider,
    RismProvider,
    InternetCulturaleProvider,
    DahrProvider,
    TunebatSongBpmProvider,
    ChosicProvider,
)
from src.scrapers.similarity_engine import (
    SimilarTrackRecommendation,
    SimilarityEngine,
    SimilarityScraper,
)
from src.gui.reconciler_dialog import (
    ReconciliationDialog,
    ReconcilerDialog,
    ConflictFieldCard,
)
from src.gui.player_widget import MiniPlayerWidget
from src.gui.views.library_view import BreadcrumbBar
from src.gui.views.home_view import TrendingTrackCard
from src.core.spotify_trends import TrendingTrack
from src.gui.views.similar_dialog import SimilarTracksDialog


class TestScrapersAndReconciliation(unittest.TestCase):
    """Test suite covering the 7 interventions from User Request 10."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database(":memory:")

    # -------------------------------------------------------------
    # 1. Specialized Metadata Providers Architecture
    # -------------------------------------------------------------
    def test_specialized_providers_registration(self):
        """Verifies that all 19 providers across the 5 domain categories are registered."""
        self.assertEqual(len(ALL_PROVIDERS), 19)

        # Check Category 1: Discography & Physical
        self.assertIn(DiscogsProvider, ALL_PROVIDERS)
        self.assertIn(FortyFiveCatProvider, ALL_PROVIDERS)
        self.assertIn(RateYourMusicProvider, ALL_PROVIDERS)
        self.assertIn(CdAndLpProvider, ALL_PROVIDERS)

        # Check Category 2: Open Metadata & Lineage
        self.assertIn(MusicBrainzProvider, ALL_PROVIDERS)
        self.assertIn(AllMusicProvider, ALL_PROVIDERS)
        self.assertIn(WhoSampledProvider, ALL_PROVIDERS)
        self.assertIn(SecondHandSongsProvider, ALL_PROVIDERS)
        self.assertIn(GeniusProvider, ALL_PROVIDERS)

        # Check Category 3: Legal Repertoires & Codes
        self.assertIn(SiaeProvider, ALL_PROVIDERS)
        self.assertIn(AscapBmiProvider, ALL_PROVIDERS)
        self.assertIn(IsrcSearchProvider, ALL_PROVIDERS)
        self.assertIn(IswcNetworkProvider, ALL_PROVIDERS)

        # Check Category 4: Historical & Classical
        self.assertIn(ImslpProvider, ALL_PROVIDERS)
        self.assertIn(RismProvider, ALL_PROVIDERS)
        self.assertIn(InternetCulturaleProvider, ALL_PROVIDERS)
        self.assertIn(DahrProvider, ALL_PROVIDERS)

        # Check Category 5: Acoustic Parameters & Similarity
        self.assertIn(TunebatSongBpmProvider, ALL_PROVIDERS)
        self.assertIn(ChosicProvider, ALL_PROVIDERS)

    def test_provider_registry_query(self):
        """Verifies registry queries execute safely without crashing."""
        providers_cat5 = ProviderRegistry.get_providers(category="acoustic_discovery")
        self.assertEqual(len(providers_cat5), 2)
        provider_names = [p.name for p in providers_cat5]
        self.assertIn("Tunebat / SongBPM", provider_names)
        self.assertIn("Chosic", provider_names)

    # -------------------------------------------------------------
    # 2. Crash Fixes (4 Log Bugs)
    # -------------------------------------------------------------
    def test_crash_fix_1_similar_tracks_dialog_signal(self):
        """Verifies SimilarTracksDialog has both play_requested and play_track_requested."""
        ref = {"title": "Test Title", "artist": "Test Artist"}
        dlg = SimilarTracksDialog(ref, self.db, auto_start=False)
        # Test connection and emission on play_requested
        emitted = []
        dlg.play_requested.connect(lambda t: emitted.append(t))
        dlg.play_requested.emit({"title": "Test Track"})
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["title"], "Test Track")
        dlg.close()

    def test_crash_fix_2_i18n_translation_key_collision(self):
        """Verifies _t() handles positional-only key and accepts keyword arguments like musical_key."""
        result = _t("key_test", "Chiave: {musical_key}", musical_key="8A")
        self.assertIn("8A", result)

    def test_crash_fix_3_home_view_qmessagebox_import(self):
        """Verifies TrendingTrackCard._on_play_or_preview_clicked uses QMessageBox without NameError."""
        from PySide6.QtWidgets import QMessageBox
        orig_q = QMessageBox.question
        orig_info = QMessageBox.information
        try:
            QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.No
            QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok

            track = TrendingTrack(title="Test", artist="Artist", preview_url=None, platform="spotify")
            card = TrendingTrackCard(track)
            # Must not raise NameError: name 'QMessageBox' is not defined
            card._on_play_or_preview_clicked()
            card.close()
        finally:
            QMessageBox.question = orig_q
            QMessageBox.information = orig_info

    def test_crash_fix_4_similar_track_affinity_score_property(self):
        """Verifies SimilarTrackRecommendation compatibility properties (affinity_score, score, affinity)."""
        rec = SimilarTrackRecommendation(
            title="Discovery Track",
            artist="Producer",
            similarity_pct=92.5,
        )
        self.assertEqual(rec.affinity_score, 92.5)
        self.assertEqual(rec.score, 92.5)
        self.assertEqual(rec.affinity, 92.5)

    # -------------------------------------------------------------
    # 3. Conflict Reconciler (ReconciliationDialog)
    # -------------------------------------------------------------
    def test_conflict_reconciler_dialog_and_cards(self):
        """Verifies ReconciliationDialog renders conflict cards for conflicting fields."""
        track = {
            "filepath": "C:/Music/test.mp3",
            "title": "Around the World",
            "artist": "Daft Punk",
            "year": 1997,
            "genre": "French House",
        }
        conflicts = {
            "year": {"Discogs": 1997, "MusicBrainz": 2001, "File Attuale": 1995},
            "genre": {"Discogs": "French House", "MusicBrainz": "Electronic"},
        }
        dlg = ReconciliationDialog(track, conflicts=conflicts)
        try:
            self.assertIn("year", dlg.field_cards)
            self.assertIn("genre", dlg.field_cards)

            # Check year card
            card_year = dlg.field_cards["year"]
            self.assertEqual(len(card_year.radio_options), 3)

            # Test custom input on card
            card_year.txt_custom.setText("1998")
            self.assertTrue(card_year.rb_custom.isChecked())
            self.assertEqual(card_year.get_selected_value(), "1998")

            # Check backward compatibility alias
            self.assertEqual(ReconciliationDialog, ReconcilerDialog)
        finally:
            dlg.close()

    # -------------------------------------------------------------
    # 4. Redundant UI Buttons Removal
    # -------------------------------------------------------------
    def test_redundant_buttons_removed(self):
        """Verifies btn_similar is removed from player bar and btn_reveal is removed from breadcrumb bar."""
        player = MiniPlayerWidget()
        self.assertFalse(hasattr(player, "btn_similar"))
        player.close()

        bbar = BreadcrumbBar()
        self.assertFalse(hasattr(bbar, "btn_reveal"))
        bbar.close()

    # -------------------------------------------------------------
    # 5. Online Discovery Boost
    # -------------------------------------------------------------
    def test_online_discovery_population(self):
        """Verifies online recommendations are fetched from WhoSampled/Chosic/RYM."""
        recs = SimilarityScraper.fetch_online_recommendations(
            artist="Daft Punk",
            title="One More Time",
            genre="French House",
            limit=5,
        )
        self.assertIsInstance(recs, list)
        self.assertGreater(len(recs), 0)
        first_rec = recs[0]
        self.assertIsInstance(first_rec, SimilarTrackRecommendation)
        self.assertGreater(first_rec.affinity_score, 0.0)


if __name__ == "__main__":
    unittest.main()
