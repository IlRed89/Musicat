"""
Unit tests for Musicat Pattern Engine.
"""

import unittest
from src.tags.patterns import PatternEngine, sanitize_filename


class TestPatternEngine(unittest.TestCase):

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("Artist / Title: Mix?"), "Artist _ Title_ Mix_")
        self.assertEqual(sanitize_filename("Valid Name 128"), "Valid Name 128")
        self.assertEqual(sanitize_filename(""), "Untitled")

    def test_parse_filename_simple(self):
        filename = "Deadmau5 - Strobe.mp3"
        pattern = "%artist% - %title%"
        res = PatternEngine.parse_filename_to_tags(filename, pattern)
        self.assertIsNotNone(res)
        self.assertEqual(res["artist"], "Deadmau5")
        self.assertEqual(res["title"], "Strobe")

    def test_parse_filename_with_bpm(self):
        filename = "Eric Prydz - Opus (126 BPM).mp3"
        pattern = "%artist% - %title% (%bpm% BPM)"
        res = PatternEngine.parse_filename_to_tags(filename, pattern)
        self.assertIsNotNone(res)
        self.assertEqual(res["artist"], "Eric Prydz")
        self.assertEqual(res["title"], "Opus")
        self.assertEqual(res["bpm"], 126.0)

    def test_parse_filename_with_camelot(self):
        filename = "[8A] Fisher - Losing It.flac"
        pattern = "[%camelot%] %artist% - %title%"
        res = PatternEngine.parse_filename_to_tags(filename, pattern)
        self.assertIsNotNone(res)
        self.assertEqual(res["camelot_key"], "8A")
        self.assertEqual(res["artist"], "Fisher")
        self.assertEqual(res["title"], "Losing It")

    def test_format_tags_to_filename(self):
        tags = {
            "artist": "Carl Cox",
            "title": "I Want You",
            "bpm": 128.0,
            "camelot_key": "11A",
        }
        pattern = "[%camelot%] %artist% - %title% (%bpm% BPM)"
        out = PatternEngine.format_tags_to_filename(tags, pattern, extension="mp3")
        self.assertEqual(out, "[11A] Carl Cox - I Want You (128 BPM).mp3")

    def test_tag_to_tag_copy(self):
        record = {"comment": "8A", "camelot_key": ""}
        updated = PatternEngine.apply_tag_to_tag(record, "copy", "comment", "camelot_key")
        self.assertEqual(updated["camelot_key"], "8A")


if __name__ == "__main__":
    unittest.main()
