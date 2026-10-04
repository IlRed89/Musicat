"""
Test Runner for Musicat Unit Test Suite.

Executes all 130 unit tests across all test modules and guarantees clean process termination
without PySide6 / Qt teardown signal interference on headless CI runners.
"""

import os
import sys
import unittest

# Ensure headless offscreen platform for PySide6 / Qt on CI runners (Linux, macOS, Windows)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> None:
    suite = unittest.defaultTestLoader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    os._exit(0 if res.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
