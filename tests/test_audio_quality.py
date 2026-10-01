"""
Unit tests for Audio Quality, Clipping Detector, EBU R128 Loudnorm and ReplayGain.
"""

import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from src.core.db import Database
from src.core.filter_engine import FilterCriteria, LiveFilterEngine, LiveFilterQueryBuilder
from src.gui.table_model import TrackTableModel
from src.plugins.quality_analyzer import AudioQualityNormalizerPlugin
from src.plugins.quality_analyzer.analyzer import AcousticQualityAnalyzer, QualityReport
from src.plugins.quality_analyzer.normalizer import VolumeNormalizer, NormalizationResult


class TestAudioQualityAnalyzer(unittest.TestCase):
    """Tests acoustic metrics calculation (LUFS, True Peak, LRA, Distortion flags)."""

    def setUp(self):
        self.sr = 44100
        self.duration = 2.0  # seconds
        self.num_samples = int(self.sr * self.duration)
        self.t = np.linspace(0, self.duration, self.num_samples, endpoint=False)

    def test_normal_clean_signal(self):
        # 1 kHz sine wave at -10 dBFS amplitude (~0.316)
        signal = 0.316 * np.sin(2 * np.pi * 1000 * self.t)
        report = AcousticQualityAnalyzer.analyze_signal(signal, self.sr, target_lufs=-10.0)

        self.assertIsInstance(report, QualityReport)
        self.assertFalse(report.has_clipping)
        self.assertLessEqual(report.true_peak_dbtp, 0.0)
        self.assertIn(report.status, ["OK", "LOW_VOLUME"])
        self.assertGreater(report.duration_sec, 1.9)

    def test_clipping_signal_detection(self):
        # Severely clipped signal: amplitude 1.5 with hard clip at +/- 1.0 (flat tops)
        raw_signal = 1.5 * np.sin(2 * np.pi * 440 * self.t)
        clipped_signal = np.clip(raw_signal, -1.0, 1.0)

        report = AcousticQualityAnalyzer.analyze_signal(clipped_signal, self.sr, target_lufs=-10.0)
        self.assertTrue(report.has_clipping or report.flat_top_clipping_count > 0)
        self.assertEqual(report.status, "CLIPPING")

    def test_low_volume_signal(self):
        # Very quiet signal (amplitude 0.005 -> ~ -46 dBFS)
        quiet_signal = 0.005 * np.sin(2 * np.pi * 1000 * self.t)
        report = AcousticQualityAnalyzer.analyze_signal(quiet_signal, self.sr, target_lufs=-10.0)

        self.assertTrue(report.is_low_volume)
        self.assertLess(report.integrated_lufs, -18.0)
        self.assertEqual(report.status, "LOW_VOLUME")
        self.assertGreater(report.suggested_gain_db, 0.0)

    def test_analyze_file_pcm_wav(self):
        # Write a temporary physical 16-bit PCM WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sr)
                # 1 second 440Hz sine wave
                sine = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, self.sr, endpoint=False))
                int16_samples = (sine * 32767).astype(np.int16)
                wf.writeframes(int16_samples.tobytes())

            report = AcousticQualityAnalyzer.analyze_file(str(tmp_path), target_lufs=-10.0)
            self.assertEqual(str(tmp_path), report.filepath)
            self.assertGreater(report.duration_sec, 0.9)
            self.assertLess(report.true_peak_dbtp, 0.5)
            self.assertIsInstance(report.to_dict(), dict)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


class TestVolumeNormalizer(unittest.TestCase):
    """Tests ReplayGain metadata writing and physical normalization routines."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.wav_path = Path(self.temp_dir.name) / "test_gain.wav"

        # Generate 1 sec test audio file
        with wave.open(str(self.wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            sine = 0.25 * np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, 44100, endpoint=False))
            wf.writeframes((sine * 32767).astype(np.int16).tobytes())

        self.normalizer = VolumeNormalizer()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_apply_replaygain_metadata(self):
        res = self.normalizer.apply_replaygain(str(self.wav_path), target_lufs=-10.0)
        self.assertTrue(res.success)
        self.assertEqual(res.mode, "replaygain")
        self.assertEqual(res.target_lufs, -10.0)
        self.assertIsInstance(res.gain_applied_db, float)

    def test_apply_python_pcm_limiter_fallback(self):
        res = self.normalizer._apply_python_pcm_normalizer(
            str(self.wav_path),
            target_lufs=-10.0,
            save_as_fixed=True,
            create_backup=False,
        )
        self.assertTrue(res.success)
        self.assertTrue(Path(res.output_filepath).exists())
        self.assertIn("_fixed", res.output_filepath)


class TestFilterCriteriaAndEngine(unittest.TestCase):
    """Tests live filtering by audio quality states (Clipping, Low Volume, Brickwall, Conformance)."""

    def test_filter_criteria_quality_field(self):
        crit = FilterCriteria(quality_filter="clipping")
        self.assertFalse(crit.is_empty())
        self.assertEqual(crit.quality_filter, "clipping")

    def test_sql_builder_quality_filter(self):
        crit = FilterCriteria(quality_filter="clipping")
        sql, params = LiveFilterQueryBuilder.build_sql(crit)
        self.assertIn("audio_status = 'CLIPPING'", sql)

        crit_low = FilterCriteria(quality_filter="low_volume")
        sql_low, _ = LiveFilterQueryBuilder.build_sql(crit_low)
        self.assertIn("audio_status = 'LOW_VOLUME'", sql_low)

        crit_prob = FilterCriteria(quality_filter="problematic")
        sql_prob, _ = LiveFilterQueryBuilder.build_sql(crit_prob)
        self.assertIn("audio_status IN ('CLIPPING', 'LOW_VOLUME', 'BRICKWALL')", sql_prob)

    def test_in_memory_quality_filter(self):
        db_mock = MagicMock()
        engine = LiveFilterEngine(db_mock)
        test_tracks = [
            {"id": 1, "title": "Track 1", "audio_status": "CLIPPING", "true_peak": 1.2, "lufs": -8.0},
            {"id": 2, "title": "Track 2", "audio_status": "OK", "true_peak": -1.0, "lufs": -10.0},
            {"id": 3, "title": "Track 3", "audio_status": "LOW_VOLUME", "true_peak": -12.0, "lufs": -22.0},
            {"id": 4, "title": "Track 4", "audio_status": "BRICKWALL", "true_peak": -0.1, "lufs": -9.0, "lra": 2.1},
        ]
        engine.warm_cache(test_tracks)

        # 1. Filter clipping only
        res_clip = engine.filter_in_memory(FilterCriteria(quality_filter="clipping"))
        self.assertEqual(len(res_clip), 1)
        self.assertEqual(res_clip[0]["id"], 1)

        # 2. Filter low volume only
        res_low = engine.filter_in_memory(FilterCriteria(quality_filter="low_volume"))
        self.assertEqual(len(res_low), 1)
        self.assertEqual(res_low[0]["id"], 3)

        # 3. Filter problematic (clipping + low + brickwall)
        res_prob = engine.filter_in_memory(FilterCriteria(quality_filter="problematic"))
        self.assertEqual(len(res_prob), 3)

        # 4. Filter OK only
        res_ok = engine.filter_in_memory(FilterCriteria(quality_filter="ok"))
        self.assertEqual(len(res_ok), 1)
        self.assertEqual(res_ok[0]["id"], 2)


class TestAudioQualityNormalizerPlugin(unittest.TestCase):
    """Tests plugin registration, metadata, and configuration schemas."""

    def test_plugin_metadata_and_schema(self):
        plugin = AudioQualityNormalizerPlugin()
        self.assertEqual(plugin.plugin_id, "audio_quality_normalizer")
        self.assertEqual(plugin.version, "1.0.0")

        schema = plugin.get_config_schema()
        keys = [item["key"] for item in schema]
        self.assertIn("target_lufs", keys)
        self.assertIn("max_true_peak", keys)
        self.assertIn("correction_mode", keys)
        self.assertIn("ffmpeg_path", keys)

    def test_target_lufs_parsing(self):
        plugin = AudioQualityNormalizerPlugin()
        self.assertEqual(plugin.get_target_lufs("-10.0 LUFS (DJ Club)"), -10.0)
        self.assertEqual(plugin.get_target_lufs("-14.0 LUFS"), -14.0)
        self.assertEqual(plugin.get_max_true_peak("-1.0 dBTP"), -1.0)


class TestTrackTableModelQualityColumns(unittest.TestCase):
    """Tests TrackTableModel columns and color rendering for audio quality."""

    def test_columns_and_formatting(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor

        tracks = [
            {"id": 1, "title": "Track Clip", "lufs": -7.5, "true_peak": 1.5, "audio_status": "CLIPPING"},
            {"id": 2, "title": "Track Low", "lufs": -21.0, "true_peak": -8.0, "audio_status": "LOW_VOLUME"},
            {"id": 3, "title": "Track OK", "lufs": -10.0, "true_peak": -1.0, "audio_status": "OK"},
        ]
        model = TrackTableModel(tracks)

        # Verify columns exist
        col_keys = [k for _, k in model.COLUMNS]
        self.assertIn("lufs", col_keys)
        self.assertIn("true_peak", col_keys)
        self.assertIn("audio_status", col_keys)

        lufs_col = col_keys.index("lufs")
        tp_col = col_keys.index("true_peak")
        status_col = col_keys.index("audio_status")

        # Test display formatting
        idx_0_lufs = model.index(0, lufs_col)
        self.assertEqual(model.data(idx_0_lufs, Qt.ItemDataRole.DisplayRole), "-7.5 LUFS")

        idx_0_tp = model.index(0, tp_col)
        self.assertEqual(model.data(idx_0_tp, Qt.ItemDataRole.DisplayRole), "+1.5 dBTP")

        idx_0_status = model.index(0, status_col)
        self.assertEqual(model.data(idx_0_status, Qt.ItemDataRole.DisplayRole), "⚠️ CLIP")

        # Test color rendering
        fg_clip = model.data(idx_0_status, Qt.ItemDataRole.ForegroundRole)
        self.assertEqual(fg_clip.name(), "#ef4444")

        idx_1_status = model.index(1, status_col)
        fg_low = model.data(idx_1_status, Qt.ItemDataRole.ForegroundRole)
        self.assertEqual(fg_low.name(), "#eab308")

        idx_2_status = model.index(2, status_col)
        fg_ok = model.data(idx_2_status, Qt.ItemDataRole.ForegroundRole)
        self.assertEqual(fg_ok.name(), "#10b981")


if __name__ == "__main__":
    unittest.main()
