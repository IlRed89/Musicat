"""
Unit tests for Musicat Acoustic Analyzer and Camelot Wheel Engine.
"""

import unittest
import numpy as np
from src.audio.analyzer import (
    AcousticAnalyzer,
    key_to_camelot,
    camelot_to_key,
    get_harmonic_matches,
)


class TestAcousticAnalyzer(unittest.TestCase):

    def test_camelot_conversions(self):
        # Major and minor conversions
        self.assertEqual(key_to_camelot("Am"), "8A")
        self.assertEqual(key_to_camelot("C"), "8B")
        self.assertEqual(key_to_camelot("F#m"), "11A")
        self.assertEqual(key_to_camelot("Dbm"), "12A")
        self.assertEqual(key_to_camelot("C#m"), "12A")
        self.assertEqual(key_to_camelot("E"), "12B")

        # Reverse conversion
        self.assertIn(camelot_to_key("8A"), ["Am", "A min"])
        self.assertIn(camelot_to_key("8B"), ["C", "C maj"])
        self.assertIn(camelot_to_key("11A"), ["F#m", "F# min"])

    def test_harmonic_matches(self):
        matches = get_harmonic_matches("8A")
        # Same key, relative major (8B), energy -1 (7A), energy +1 (9A), energy boost +2 (10A)
        self.assertIn("8A", matches)
        self.assertIn("8B", matches)
        self.assertIn("7A", matches)
        self.assertIn("9A", matches)
        self.assertIn("10A", matches)

    def test_bpm_estimation_synthetic(self):
        # Generate synthetic 128 BPM beat train
        sr = 22050
        duration = 5.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        signal = np.zeros_like(t)

        # 128 BPM -> beat period = 60 / 128 = 0.46875s
        beat_interval = 60.0 / 128.0
        beat_frames = [int(i * beat_interval * sr) for i in range(int(duration / beat_interval))]

        for bf in beat_frames:
            if bf < len(signal) - 1000:
                # Add synthetic kick transient (exponential decay sine)
                click = np.sin(2 * np.pi * 60 * np.linspace(0, 0.05, 1000)) * np.exp(-np.linspace(0, 10, 1000))
                signal[bf : bf + 1000] += click

        bpm = AcousticAnalyzer.estimate_bpm(signal, sr)
        self.assertTrue(125.0 <= bpm <= 131.0, f"Detected BPM {bpm} not close to 128.0")


if __name__ == "__main__":
    unittest.main()
