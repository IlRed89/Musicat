"""
Unit tests for VLCAudioPlayer Engine and DJ Pitch Controls.
"""

import unittest
from src.player.vlc_engine import VLCAudioPlayer


class TestVLCAudioPlayer(unittest.TestCase):

    def setUp(self):
        self.player = VLCAudioPlayer()

    def test_volume_controls(self):
        self.player.set_volume(85)
        self.assertEqual(self.player.get_volume(), 85)

        # Clamping
        self.player.set_volume(150)
        self.assertEqual(self.player.get_volume(), 100)
        self.player.set_volume(-10)
        self.assertEqual(self.player.get_volume(), 0)

    def test_pitch_rate_controls(self):
        # 1.0 is standard
        self.player.set_pitch_rate(1.0)
        self.assertAlmostEqual(self.player.get_pitch_rate(), 1.0, places=2)

        # DJ +8% pitch bend (1.08x)
        self.player.set_pitch_rate(1.08)
        self.assertAlmostEqual(self.player.get_pitch_rate(), 1.08, places=2)

        # DJ -8% pitch bend (0.92x)
        self.player.set_pitch_rate(0.92)
        self.assertAlmostEqual(self.player.get_pitch_rate(), 0.92, places=2)

        # Clamping beyond extreme limit
        self.player.set_pitch_rate(1.50)
        self.assertEqual(self.player.get_pitch_rate(), 1.20)

    def test_loop_toggle(self):
        self.assertFalse(self.player.is_looping())
        self.player.set_loop(True)
        self.assertTrue(self.player.is_looping())

    def test_empty_load_handling(self):
        # Non-existent file should gracefully return False
        success = self.player.load("non_existent_path.mp3")
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
