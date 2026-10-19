"""
Unit and Integration Tests for DSP Audio Engine, UI Autofit, and Similar Track Discovery.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import unittest
import numpy as np

from src.audio.dsp_engine import (
    DspProcessResult,
    PedalboardDspProcessor,
    LibavfilterDspEngine,
    JucePluginBridge,
    AudioEnhancementOrchestrator,
    HAS_PEDALBOARD,
)
from src.scrapers.similarity_engine import (
    SimilarTrackRecommendation,
    SimilarityResult,
)


class TestDspAndUiEnhancements(unittest.TestCase):

    def test_pedalboard_availability_and_chains(self):
        """Verifies Pedalboard processor availability and preset board generation."""
        self.assertTrue(PedalboardDspProcessor.is_available())

        presets = ["club_master", "vocal_clarity", "warm_analog", "dj_punch", "declip_clean"]
        for p in presets:
            board = PedalboardDspProcessor.build_board(p)
            self.assertIsNotNone(board, f"Failed to build board for preset {p}")
            self.assertGreaterEqual(len(board), 3, f"Preset {p} chain has too few effects: {len(board)}")

    def test_pedalboard_audio_processing(self):
        """Tests processing of in-memory numpy float audio through Pedalboard."""
        sample_rate = 44100
        t = np.linspace(0, 0.5, int(sample_rate * 0.5), endpoint=False, dtype=np.float32)
        tone_left = 0.5 * np.sin(2 * np.pi * 440 * t)
        tone_right = 0.5 * np.sin(2 * np.pi * 880 * t)
        stereo_audio = np.stack([tone_left, tone_right], axis=0)

        processed = PedalboardDspProcessor.process_audio(stereo_audio, sample_rate, preset="club_master")
        self.assertIsNotNone(processed)
        self.assertEqual(processed.shape, stereo_audio.shape)
        self.assertFalse(np.isnan(processed).any())
        self.assertLessEqual(np.max(np.abs(processed)), 1.0)

    def test_libavfilter_preset_filtergraphs(self):
        """Verifies that LibavfilterDspEngine constructs correct filter chains for all presets."""
        presets = ["club_master", "vocal_clarity", "warm_analog", "dj_punch", "declip_clean"]
        for p in presets:
            fg = LibavfilterDspEngine.build_filtergraph(
                target_lufs=-10.0,
                preset=p,
                enable_declip=True,
            )
            self.assertIn("loudnorm=", fg)
            self.assertIn("alimiter=", fg)
            if p == "club_master":
                self.assertIn("equalizer=f=60", fg)
                self.assertIn("TP=-0.5", fg)
            elif p == "vocal_clarity":
                self.assertIn("highpass=f=80", fg)
                self.assertIn("equalizer=f=3800", fg)
            elif p == "warm_analog":
                self.assertIn("lowpass=f=18500", fg)
            elif p == "dj_punch":
                self.assertIn("equalizer=f=85", fg)
                self.assertIn("TP=-0.8", fg)
            elif p == "declip_clean":
                self.assertIn("adeclip=", fg)
                self.assertIn("afftdn=", fg)

    def test_juce_vst3_bridge_graceful_handling(self):
        """Verifies JUCE VST3 plugin loader safely handles missing or invalid plugin files."""
        paths = JucePluginBridge.get_vst3_search_paths()
        self.assertIsInstance(paths, list)

        res = JucePluginBridge.load_juce_vst3("C:/NonExistentPluginPath/DummyPlugin.vst3")
        self.assertIsNone(res)

    def test_similar_track_recommendation_properties(self):
        """Tests compatibility properties on SimilarTrackRecommendation."""
        rec = SimilarTrackRecommendation(
            title="Midnight City",
            artist="M83",
            bpm=105.0,
            camelot_key="11B",
            similarity_pct=88.5,
            source="Cosine.club",
            in_library=True,
            local_filepath="C:/Music/m83.mp3",
        )
        self.assertEqual(rec.similarity_pct, 88.5)
        self.assertEqual(rec.affinity_score, 88.5)
        self.assertEqual(rec.score, 88.5)
        self.assertEqual(rec.affinity, 88.5)

        d = rec.to_dict()
        self.assertEqual(d["title"], "Midnight City")
        self.assertEqual(d["affinity_score"], 88.5)
        self.assertEqual(d["similarity_pct"], 88.5)

    def test_similar_dialog_and_view_signals(self):
        """Verifies that SimilarTracksDialog and SimilarTracksView expose required signals and aliases."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)

        from src.gui.views.similar_dialog import SimilarTracksDialog
        from src.gui.views.similar_view import SimilarTracksView
        from src.core.db import Database

        db = Database(":memory:")

        # Test dialog signals
        dlg = SimilarTracksDialog({"title": "Test", "artist": "Artist"}, db=db, auto_start=False)
        self.assertTrue(hasattr(dlg, "play_requested"))
        self.assertTrue(hasattr(dlg, "play_track_requested"))

        # Test view signals and aliases
        view = SimilarTracksView(db=db)
        self.assertTrue(hasattr(view, "play_requested"))
        self.assertTrue(hasattr(view, "play_track_requested"))
        self.assertTrue(hasattr(view, "set_target_track"))
        self.assertTrue(hasattr(view, "set_reference_track"))
        self.assertEqual(view.set_target_track, view.set_reference_track)


if __name__ == "__main__":
    unittest.main()
