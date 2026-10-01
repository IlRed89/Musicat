"""
Unit tests for AudioTagEditor.
"""

import tempfile
import unittest
from pathlib import Path
import wave
import struct

from src.tags.editor import AudioTagEditor, AudioMetadata


class TestAudioTagEditor(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.wav_path = Path(self.temp_dir.name) / "test_track.wav"

        # Generate a minimal valid PCM WAV file (1 sec of silence at 44100 Hz mono 16-bit)
        with wave.open(str(self.wav_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(struct.pack("<44100h", *([0] * 44100)))

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_read_write_wav_tags(self):
        tags_to_write = {
            "title": "Subzero (Club Mix)",
            "artist": "Ben Klock",
            "album": "Berghain 04",
            "genre": "Techno",
            "bpm": 132.5,
            "camelot_key": "4A",
            "musical_key": "Fm",
            "year": 2009,
            "remixer": "Marcel Dettmann",
            "label": "Ostgut Ton",
            "comment": "DJ Peak Time Weapon",
        }

        # Write tags to file
        success = AudioTagEditor.write_metadata(self.wav_path, tags_to_write)
        self.assertTrue(success)

        # Read back tags
        meta = AudioTagEditor.read_metadata(self.wav_path)
        self.assertEqual(meta.title, "Subzero (Club Mix)")
        self.assertEqual(meta.artist, "Ben Klock")
        self.assertEqual(meta.album, "Berghain 04")
        self.assertEqual(meta.genre, "Techno")
        self.assertEqual(meta.bpm, 132.5)
        self.assertEqual(meta.camelot_key, "4A")
        self.assertEqual(meta.musical_key, "Fm")
        self.assertEqual(meta.year, 2009)
        self.assertEqual(meta.remixer, "Marcel Dettmann")
        self.assertEqual(meta.label, "Ostgut Ton")
        self.assertEqual(meta.comment, "DJ Peak Time Weapon")

    def test_artwork_embedding(self):
        # 1x1 GIF / JPEG fake bytes
        dummy_art = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9"
        res = AudioTagEditor.set_artwork(self.wav_path, dummy_art, mime_type="image/jpeg")
        self.assertTrue(res)

        # Retrieve artwork
        cover = AudioTagEditor.get_artwork(self.wav_path)
        self.assertIsNotNone(cover)
        self.assertEqual(cover.data, dummy_art)

        # Remove artwork
        rm_res = AudioTagEditor.remove_artwork(self.wav_path)
        self.assertTrue(rm_res)


if __name__ == "__main__":
    unittest.main()
