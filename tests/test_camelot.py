"""
Unit Tests for Camelot Wheel & Harmonic Mixing Assistant.
"""

import unittest
from src.audio.camelot import (
    CamelotWheel,
    CAMELOT_KEYS_ORDERED,
    CAMELOT_TO_KEY,
    KEY_TO_CAMELOT,
)


class TestCamelotWheel(unittest.TestCase):
    """Tests harmonic mixing, Camelot wheel math, and BPM tolerance calculations."""

    def test_key_normalization(self):
        """Tests converting various key notations to canonical Camelot format."""
        self.assertEqual(CamelotWheel.normalize_key("8A"), "8A")
        self.assertEqual(CamelotWheel.normalize_key("8a"), "8A")
        self.assertEqual(CamelotWheel.normalize_key("12B"), "12B")
        self.assertEqual(CamelotWheel.normalize_key("Am"), "8A")
        self.assertEqual(CamelotWheel.normalize_key("A minor"), "8A")
        self.assertEqual(CamelotWheel.normalize_key("C"), "8B")
        self.assertEqual(CamelotWheel.normalize_key("C maj"), "8B")
        self.assertEqual(CamelotWheel.normalize_key("F#m"), "11A")
        self.assertEqual(CamelotWheel.normalize_key("Gb min"), "11A")
        self.assertEqual(CamelotWheel.normalize_key(""), "")
        self.assertEqual(CamelotWheel.normalize_key(None), "")

    def test_parse_camelot(self):
        """Tests parsing Camelot code into integer and letter."""
        self.assertEqual(CamelotWheel.parse_camelot("8A"), (8, "A"))
        self.assertEqual(CamelotWheel.parse_camelot("1B"), (1, "B"))
        self.assertEqual(CamelotWheel.parse_camelot("12A"), (12, "A"))
        self.assertIsNone(CamelotWheel.parse_camelot("InvalidKey"))

    def test_relative_key(self):
        """Tests relative Major/Minor scale transitions."""
        self.assertEqual(CamelotWheel.get_relative_key("8A"), "8B")
        self.assertEqual(CamelotWheel.get_relative_key("8B"), "8A")
        self.assertEqual(CamelotWheel.get_relative_key("1A"), "1B")
        self.assertEqual(CamelotWheel.get_relative_key("12B"), "12A")

    def test_adjacent_keys_and_wrapping(self):
        """Tests +1 and -1 hour transitions including 12 <-> 1 wrap-around."""
        # Standard middle wheel
        prev_k, next_k = CamelotWheel.get_adjacent_keys("8A")
        self.assertEqual(prev_k, "7A")
        self.assertEqual(next_k, "9A")

        # Wrap around 1 -> 12
        prev_1, next_1 = CamelotWheel.get_adjacent_keys("1B")
        self.assertEqual(prev_1, "12B")
        self.assertEqual(next_1, "2B")

        # Wrap around 12 -> 1
        prev_12, next_12 = CamelotWheel.get_adjacent_keys("12A")
        self.assertEqual(prev_12, "11A")
        self.assertEqual(next_12, "1A")

    def test_energy_boost_keys(self):
        """Tests +2 whole tone boost and +7 semitone lift."""
        boosts = CamelotWheel.get_energy_boost_keys("8A")
        self.assertEqual(boosts["plus_two_boost"], "10A")
        # 8 + 7 = 15 -> (15 - 1) % 12 + 1 = 3A
        self.assertEqual(boosts["semitone_lift"], "3A")

        # Edge wrapping
        boosts_11 = CamelotWheel.get_energy_boost_keys("11B")
        self.assertEqual(boosts_11["plus_two_boost"], "1B")

    def test_harmonic_matches_generation(self):
        """Tests complete set of compatible keys."""
        matches = CamelotWheel.get_harmonic_matches(
            "8A",
            include_exact=True,
            include_adjacent=True,
            include_relative=True,
            include_energy_boost=True,
            include_semitone=False,
        )
        self.assertIn("8A", matches)   # Exact
        self.assertIn("7A", matches)   # -1
        self.assertIn("9A", matches)   # +1
        self.assertIn("8B", matches)   # Relative
        self.assertIn("10A", matches)  # +2 Boost
        self.assertNotIn("3A", matches)  # Semitone was excluded

        # Include semitone
        matches_with_semi = CamelotWheel.get_harmonic_matches(
            "8A",
            include_semitone=True,
        )
        self.assertIn("3A", matches_with_semi)

    def test_relationship_descriptions(self):
        """Tests human readable relationship descriptions."""
        self.assertIn("Exact Match", CamelotWheel.get_relationship_description("8A", "8A"))
        self.assertIn("Clockwise", CamelotWheel.get_relationship_description("8A", "9A"))
        self.assertIn("Counter-Clockwise", CamelotWheel.get_relationship_description("8A", "7A"))
        self.assertIn("Relative Scale", CamelotWheel.get_relationship_description("8A", "8B"))
        self.assertIn("Energy Boost", CamelotWheel.get_relationship_description("8A", "10A"))
        self.assertIn("Clash", CamelotWheel.get_relationship_description("8A", "4B"))

    def test_bpm_tolerance_range(self):
        """Tests BPM target range calculation with percentage tolerance."""
        min_b, max_b = CamelotWheel.calculate_bpm_tolerance_range(126.0, 2.0)
        self.assertAlmostEqual(min_b, 123.5, places=1)
        self.assertAlmostEqual(max_b, 128.5, places=1)

        min_4, max_4 = CamelotWheel.calculate_bpm_tolerance_range(125.0, 4.0)
        self.assertAlmostEqual(min_4, 120.0, places=1)
        self.assertAlmostEqual(max_4, 130.0, places=1)

    def test_pitch_pct_calculation(self):
        """Tests pitch slider percentage needed to match tempos."""
        pct = CamelotWheel.calculate_pitch_pct(120.0, 126.0)
        self.assertAlmostEqual(pct, 5.0, places=1)

        pct_down = CamelotWheel.calculate_pitch_pct(128.0, 124.0)
        self.assertAlmostEqual(pct_down, -3.12, places=1)


if __name__ == "__main__":
    unittest.main()
