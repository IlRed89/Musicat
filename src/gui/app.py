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
                "ilred89.musicat.djcataloger.app.1.0"
            )
        except Exception:
            pass

    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    from ..core.boot_diagnostics import boot_log, get_qt_display_diagnostics

    boot_log("[QT:INIT] Initializing QApplication instance...", level="QT")
    app = QApplication(sys.argv)
    app.setApplicationName("Musicat")
    app.setOrganizationName("IlRed89")

    platform_name = app.platformName()
    boot_log(f"[QT:PLATFORM] Active Qt platform plugin: '{platform_name}'", level="QT")
    if sys.platform == "darwin":
        if platform_name == "cocoa":
            boot_log("[COCOA:OK] QCocoaIntegrationPlugin active. Native Apple Cocoa display pipeline engaged.", level="COCOA")
        else:
            boot_log(f"[COCOA:WARN] Unexpected platform plugin '{platform_name}' on macOS (expected 'cocoa').", level="WARNING")

    # Display & Screen Telemetry
    disp_diag = get_qt_display_diagnostics(app)
    boot_log(f"[QT:DISPLAY] Detected {disp_diag['screens_count']} active display screen(s):", level="QT")
    for scr in disp_diag.get("screens", []):
        boot_log(
            f"  Display #{scr['index']} ('{scr['name']}'): {scr['resolution']} | "
            f"Scale: {scr['device_pixel_ratio']}x | DPI: {scr['dpi']}",
            level="QT",
        )

    # Load persistent settings
    from ..core.settings import SettingsManager
    from ..core.i18n import I18n
    from .styles import get_theme_stylesheet

    settings = SettingsManager.get_instance()
    saved_theme = settings.get("ui", "theme", "light") or "light"
    boot_log(f"[QT:THEME] Applying '{saved_theme}' stylesheet.", level="QT")
    app.setStyleSheet(get_theme_stylesheet(saved_theme))

    # Set Application Icon
    from PySide6.QtGui import QIcon
    from ..core.path_resolver import PathResolver

    icon_path = PathResolver.get_icon_path()
    if icon_path and icon_path.exists():
        boot_log(f"[QT:ICON] Window icon loaded from: {icon_path}", level="QT")
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        boot_log("[QT:ICON] Default window icon not found on disk, using system fallback.", level="WARNING")

    # Initialize localization (Default: Italian)
    saved_lang = settings.get("ui", "language", "it") or "it"
    boot_log(f"[I18N:INIT] Initializing localization bus (language='{saved_lang}').", level="I18N")
    i18n = I18n.get_instance(saved_lang)
    i18n.set_language(saved_lang)

    boot_log("[DB:INIT] Connecting to SQLite database...", level="DB")
    db = Database()
    boot_log("[GUI:MAIN] Instantiating MainWindow embedded workspaces...", level="GUI")
    window = MainWindow(db=db)
    if icon_path and icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    boot_log("[GUI:MAIN] Showing main application window.", level="GUI")
    window.show()

    boot_log("[QT:LOOP] Entering QApplication event loop (app.exec).", level="QT")
    ret_code = app.exec()
    boot_log(f"[QT:EXIT] QApplication event loop terminated with exit code: {ret_code}.", level="QT")
    return ret_code


if __name__ == "__main__":
    sys.exit(run_app())
