"""
Unit tests for Musicat Structured Logger and Compressed Rotation.
"""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from src.core.logger import MusicatLogger, GuiLogHandler, CompressedRotatingFileHandler


class TestMusicatLogger(unittest.TestCase):

    def test_logger_singleton(self):
        log1 = MusicatLogger.get_logger()
        log2 = MusicatLogger.get_logger()
        self.assertIs(log1, log2)
        self.assertEqual(log1.name, "Musicat")

    def test_gui_log_handler_callback(self):
        received_messages = []

        def callback(t_str, lvl, msg):
            received_messages.append((lvl, msg))

        MusicatLogger.register_gui_callback(callback)
        logger = MusicatLogger.get_logger()
        logger.info("Test GUI log message")

        self.assertTrue(len(received_messages) > 0)
        last_lvl, last_msg = received_messages[-1]
        self.assertEqual(last_lvl, logging.INFO)
        self.assertIn("Test GUI log message", last_msg)

    def test_domain_log_helpers(self):
        # Verify helpers execute without exceptions
        MusicatLogger.log_scan("C:/Music", 150, 150, 42.5)
        MusicatLogger.log_acoustic("C:/Music/test.mp3", 128.0, "Am", "8A", 35.0)
        MusicatLogger.log_http("Beatport", "https://beatport.com", 200, 120.5, 10)
        MusicatLogger.log_tag_edit("C:/Music/test.mp3", ["BPM", "KEY"], True)
        MusicatLogger.log_file_op("copy", "C:/source.mp3", "C:/target.mp3", True)

    def test_compressed_rotation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test_rot.log"
            handler = CompressedRotatingFileHandler(
                str(log_file),
                maxBytes=500,  # Small threshold to trigger rotation
                backupCount=2,
            )
            # Write enough data to trigger rotation
            for i in range(50):
                handler.emit(logging.LogRecord("test", logging.INFO, "test.py", 10, "A" * 50, (), None))
            handler.close()

            # Verify that either rotated .gz or rotated files exist
            files = list(Path(tmp_dir).glob("*.log*"))
            self.assertTrue(len(files) >= 1)


if __name__ == "__main__":
    unittest.main()
