"""
Unit tests for Musicat Smart Organizer.
"""

import unittest
from pathlib import Path
from src.organizer.sorter import SmartOrganizer


class TestSmartOrganizer(unittest.TestCase):

    def test_bpm_range_buckets(self):
        self.assertEqual(SmartOrganizer.get_bpm_range(124.0, step=5), "120-124 BPM")
        self.assertEqual(SmartOrganizer.get_bpm_range(125.0, step=5), "125-129 BPM")
        self.assertEqual(SmartOrganizer.get_bpm_range(128.2, step=5), "125-129 BPM")
        self.assertEqual(SmartOrganizer.get_bpm_range(130.0, step=5), "130-134 BPM")
        self.assertEqual(SmartOrganizer.get_bpm_range(None), "Unknown BPM")

    def test_resolve_target_path(self):
        tags = {
            "artist": "Tale of Us",
            "title": "Astral",
            "genre": "Melodic Techno",
            "year": 2022,
            "bpm": 124.0,
            "camelot_key": "8A",
        }
        dest_dir = "C:/Music/Organized"
        rule = "{genre}/BPM {bpm_range}/{camelot_key} - {artist} - {title}{ext}"

        abs_path, rel_path, missing = SmartOrganizer.resolve_target_path(
            tags=tags,
            dest_dir=dest_dir,
            rule_pattern=rule,
            ext=".mp3",
            bpm_step=5,
        )

        self.assertEqual(len(missing), 0)
        self.assertIn("Melodic Techno", rel_path)
        self.assertIn("BPM 120-124 BPM", rel_path)
        self.assertIn("8A - Tale of Us - Astral.mp3", rel_path)


if __name__ == "__main__":
    unittest.main()
