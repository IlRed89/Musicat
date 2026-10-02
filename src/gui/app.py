"""
Musicat GUI Application Launcher.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .main_view import MainWindow
from ..core.db import Database


def run_app() -> int:
    """Initializes and runs the Musicat Qt application."""
    # Windows Taskbar AppUserModelID for explicit grouping and icon attachment
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "ilred89.musicat.djcataloger.1.0"
            )
        except Exception:
            pass

    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Musicat")
    app.setOrganizationName("IlRed89")

    # Load persistent settings
    from ..core.settings import SettingsManager
    from ..core.i18n import I18n
    from .styles import get_theme_stylesheet

    settings = SettingsManager.get_instance()
    saved_theme = settings.get("ui", "theme", "light") or "light"
    app.setStyleSheet(get_theme_stylesheet(saved_theme))

    # Set Application Icon
    from PySide6.QtGui import QIcon
    from ..core.path_resolver import PathResolver

    icon_path = PathResolver.get_icon_path()
    if icon_path and icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Initialize localization (Default: Italian)
    saved_lang = settings.get("ui", "language", "it") or "it"
    i18n = I18n.get_instance(saved_lang)
    i18n.set_language(saved_lang)

    db = Database()
    window = MainWindow(db=db)
    if icon_path and icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
