"""
Musicat GUI Application Launcher.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .styles import DARK_THEME_QSS
from .main_view import MainWindow
from ..core.db import Database


def run_app() -> int:
    """Initializes and runs the Musicat Qt application."""
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Musicat")
    app.setOrganizationName("IlRed89")
    app.setStyleSheet(DARK_THEME_QSS)

    db = Database()
    window = MainWindow(db=db)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
