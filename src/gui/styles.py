"""
Dark DJ Console Theme Stylesheet (QSS) for Musicat.
Optimized for low-light DJ booths, high contrast, and dense table data display.
"""

DARK_THEME_QSS = """
/* Global Window & Fonts */
QWidget {
    background-color: #121316;
    color: #e0e2ec;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: #00d2ff;
    selection-color: #0b0c10;
}

QMainWindow {
    background-color: #121316;
}

/* ToolBar & MenuBar */
QMenuBar {
    background-color: #181a20;
    border-bottom: 1px solid #282b36;
    padding: 2px;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #242731;
    color: #00d2ff;
}

QMenu {
    background-color: #1a1c24;
    border: 1px solid #2c303f;
    padding: 4px;
    border-radius: 6px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #00d2ff;
    color: #0b0c10;
}

QMenu::separator {
    height: 1px;
    background: #2a2d3a;
    margin: 4px 6px;
}

QToolBar {
    background-color: #181a20;
    border-bottom: 1px solid #282b36;
    padding: 4px 8px;
    spacing: 8px;
}

QToolButton {
    background-color: #20232b;
    border: 1px solid #2d313d;
    border-radius: 5px;
    padding: 5px 10px;
    font-weight: 500;
    color: #e0e2ec;
}

QToolButton:hover {
    background-color: #2b2f3b;
    border-color: #00d2ff;
    color: #00d2ff;
}

QToolButton:pressed {
    background-color: #15171d;
}

/* Buttons */
QPushButton {
    background-color: #21242d;
    border: 1px solid #313543;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 600;
    color: #e2e4ed;
}

QPushButton:hover {
    background-color: #2c313d;
    border-color: #00d2ff;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #181a21;
}

QPushButton:disabled {
    background-color: #18191f;
    border-color: #24252e;
    color: #5d6170;
}

QPushButton#PrimaryButton {
    background-color: #00a8cc;
    border: 1px solid #00d2ff;
    color: #050608;
    font-weight: bold;
}

QPushButton#PrimaryButton:hover {
    background-color: #00d2ff;
    color: #000000;
}

QPushButton#AccentButton {
    background-color: #7b2cbf;
    border: 1px solid #9d4edd;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#AccentButton:hover {
    background-color: #9d4edd;
}

/* Input Fields */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1a1c22;
    border: 1px solid #2c303d;
    border-radius: 5px;
    padding: 6px 10px;
    color: #ffffff;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #00d2ff;
    background-color: #1f222a;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1a1c24;
    border: 1px solid #2d3240;
    selection-background-color: #00d2ff;
    selection-color: #000;
}

/* Table View */
QTableView {
    background-color: #15161b;
    alternate-background-color: #191b22;
    border: 1px solid #262933;
    gridline-color: #222530;
    selection-background-color: #004d61;
    selection-color: #ffffff;
}

QTableView::item {
    padding: 4px 6px;
    border: none;
}

QTableView::item:selected {
    background-color: #005a73;
    color: #ffffff;
}

QTableView::item:hover {
    background-color: #20242f;
}

QHeaderView::section {
    background-color: #1c1e26;
    color: #9da3b5;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #262933;
    border-bottom: 2px solid #2a2e3b;
    font-weight: bold;
    font-size: 12px;
}

QHeaderView::section:hover {
    background-color: #242731;
    color: #00d2ff;
}

/* ScrollBars */
QScrollBar:vertical {
    background: #141519;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2f3342;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #00d2ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #141519;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #2f3342;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #00d2ff;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* GroupBox & Frames */
QGroupBox {
    border: 1px solid #292d3a;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #00d2ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #121316;
}

/* Status Bar */
QStatusBar {
    background-color: #17181e;
    border-top: 1px solid #252833;
    color: #8c92a4;
    padding: 2px 6px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #292c38;
    background-color: #16171d;
    border-radius: 4px;
}

QTabBar::tab {
    background: #1e2028;
    border: 1px solid #2b2e3b;
    padding: 7px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: #282c38;
    border-bottom-color: #00d2ff;
    color: #00d2ff;
    font-weight: bold;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #262935;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #00d2ff;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #00d2ff;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #00d2ff;
}

/* Badges / Labels */
QLabel#CamelotBadge {
    background-color: #3d1369;
    color: #c77dff;
    border: 1px solid #7b2cbf;
    border-radius: 4px;
    font-weight: bold;
    padding: 2px 6px;
}

QLabel#BpmBadge {
    background-color: #083344;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 4px;
    font-weight: bold;
    padding: 2px 6px;
}
"""

HIGH_CONTRAST_THEME_QSS = """
/* High-Contrast Club Booth Theme */
QWidget {
    background-color: #000000;
    color: #ffffff;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: #ffff00;
    selection-color: #000000;
}

QMainWindow, QDialog {
    background-color: #000000;
}

QMenuBar {
    background-color: #0a0a0a;
    border-bottom: 2px solid #00ffff;
}

QMenuBar::item:selected {
    background-color: #00ffff;
    color: #000000;
}

QTableView {
    background-color: #050505;
    color: #ffffff;
    gridline-color: #333333;
    selection-background-color: #ffff00;
    selection-color: #000000;
}

QHeaderView::section {
    background-color: #111111;
    color: #00ffff;
    font-weight: bold;
    border: 1px solid #333333;
    padding: 5px;
}

QPushButton {
    background-color: #111111;
    color: #00ffff;
    border: 2px solid #00ffff;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #00ffff;
    color: #000000;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #0a0a0a;
    color: #ffffff;
    border: 2px solid #ffffff;
    border-radius: 4px;
    padding: 4px 8px;
}
"""

LIGHT_THEME_QSS = """
/* Light Studio Theme */
QWidget {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

QMainWindow, QDialog {
    background-color: #f1f5f9;
}

QMenuBar {
    background-color: #ffffff;
    border-bottom: 1px solid #cbd5e1;
}

QMenuBar::item:selected {
    background-color: #e2e8f0;
    color: #0284c7;
}

QTableView {
    background-color: #ffffff;
    color: #0f172a;
    gridline-color: #e2e8f0;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #1e293b;
    font-weight: bold;
    border: 1px solid #cbd5e1;
    padding: 5px;
}

QPushButton {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #94a3b8;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #0284c7;
    color: #0284c7;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px 8px;
}
"""


def get_theme_stylesheet(theme_id: str) -> str:
    """Returns the appropriate QSS stylesheet for the given theme ID."""
    t = (theme_id or "").lower().strip()
    if "high" in t or "contrast" in t:
        return HIGH_CONTRAST_THEME_QSS
    elif "light" in t:
        return LIGHT_THEME_QSS
    return DARK_THEME_QSS

