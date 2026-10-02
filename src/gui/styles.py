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

QToolBar, QFrame#topNavBar {
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
/* Light Studio & DJ Modern Theme */
/* Palette: Backgrounds #FFFFFF / #F8F9FA, Text #212529, Borders/Dividers #DEE2E6, Selections #0D6EFD */
QWidget {
    background-color: #f8f9fa;
    color: #212529;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: #0d6efd;
    selection-color: #ffffff;
}

QMainWindow, QDialog {
    background-color: #f8f9fa;
}

/* ToolBar & MenuBar */
QMenuBar {
    background-color: #ffffff;
    border-bottom: 1px solid #dee2e6;
    padding: 2px;
    color: #212529;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 10px;
    border-radius: 4px;
    color: #212529;
}

QMenuBar::item:selected {
    background-color: #e9ecef;
    color: #0d6efd;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #dee2e6;
    padding: 4px;
    border-radius: 6px;
    color: #212529;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
    color: #212529;
}

QMenu::item:selected {
    background-color: #0d6efd;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #dee2e6;
    margin: 4px 6px;
}

QToolBar, QFrame#topNavBar {
    background-color: #ffffff;
    border-bottom: 1px solid #dee2e6;
    padding: 4px 8px;
    spacing: 8px;
}

QToolButton {
    background-color: #ffffff;
    border: 1px solid #ced4da;
    border-radius: 5px;
    padding: 5px 10px;
    font-weight: 500;
    color: #212529;
}

QToolButton:hover {
    background-color: #e9ecef;
    border-color: #0d6efd;
    color: #0d6efd;
}

QToolButton:pressed {
    background-color: #dee2e6;
}

/* Buttons */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #ced4da;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 600;
    color: #212529;
}

QPushButton:hover {
    background-color: #f1f3f5;
    border-color: #0d6efd;
    color: #0d6efd;
}

QPushButton:pressed {
    background-color: #e9ecef;
}

QPushButton:disabled {
    background-color: #f8f9fa;
    border-color: #e9ecef;
    color: #adb5bd;
}

QPushButton#PrimaryButton {
    background-color: #0d6efd;
    border: 1px solid #0d6efd;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#PrimaryButton:hover {
    background-color: #0b5ed7;
    border-color: #0a58ca;
    color: #ffffff;
}

QPushButton#AccentButton {
    background-color: #6610f2;
    border: 1px solid #6610f2;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#AccentButton:hover {
    background-color: #520dc2;
}

/* Input Fields */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #ced4da;
    border-radius: 5px;
    padding: 6px 10px;
    color: #212529;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #0d6efd;
    background-color: #ffffff;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #ced4da;
    selection-background-color: #0d6efd;
    selection-color: #ffffff;
    color: #212529;
}

/* Table View */
QTableView {
    background-color: #ffffff;
    alternate-background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    gridline-color: #dee2e6;
    selection-background-color: #0d6efd;
    selection-color: #ffffff;
    color: #212529;
}

QTableView::item {
    padding: 4px 6px;
    border: none;
}

QTableView::item:selected {
    background-color: #0d6efd;
    color: #ffffff;
}

QTableView::item:hover {
    background-color: #e9ecef;
}

QHeaderView::section {
    background-color: #f1f3f5;
    color: #212529;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #dee2e6;
    border-bottom: 2px solid #ced4da;
    font-weight: bold;
    font-size: 12px;
}

QHeaderView::section:hover {
    background-color: #e9ecef;
    color: #0d6efd;
}

/* TreeView & TreeWidget */
QTreeView, QTreeWidget, QListWidget {
    background-color: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 5px;
    color: #212529;
}

QTreeView::item, QTreeWidget::item, QListWidget::item {
    padding: 4px 6px;
    color: #212529;
}

QTreeView::item:hover, QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: #f1f3f5;
}

QTreeView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #0d6efd;
    color: #ffffff;
    font-weight: bold;
}

/* ScrollBars */
QScrollBar:vertical {
    background: #f8f9fa;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #ced4da;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #0d6efd;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #f8f9fa;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #ced4da;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #0d6efd;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* GroupBox & Frames */
QGroupBox {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #0d6efd;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #ffffff;
}

/* Status Bar */
QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #dee2e6;
    color: #495057;
    padding: 2px 6px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #dee2e6;
    background-color: #ffffff;
    border-radius: 4px;
}

QTabBar::tab {
    background: #f1f3f5;
    border: 1px solid #dee2e6;
    padding: 7px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #495057;
}

QTabBar::tab:selected {
    background: #ffffff;
    border-bottom-color: #0d6efd;
    color: #0d6efd;
    font-weight: bold;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #dee2e6;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #0d6efd;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #0d6efd;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #0d6efd;
}

/* Splitter */
QSplitter::handle {
    background-color: #dee2e6;
}

/* CheckBox */
QCheckBox {
    color: #212529;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #ced4da;
    border-radius: 3px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #0d6efd;
    border-color: #0d6efd;
}

/* Badges / Labels */
QLabel#CamelotBadge {
    background-color: #f3e8ff;
    color: #7c3aed;
    border: 1px solid #c4b5fd;
    border-radius: 4px;
    font-weight: bold;
    padding: 2px 6px;
}

QLabel#BpmBadge {
    background-color: #e0f2fe;
    color: #0284c7;
    border: 1px solid #7dd3fc;
    border-radius: 4px;
    font-weight: bold;
    padding: 2px 6px;
}
"""


def get_theme_stylesheet(theme_id: str) -> str:
    """Returns the appropriate QSS stylesheet for the given theme ID. Defaults to Light theme."""
    t = (theme_id or "").lower().strip()
    if "high" in t or "contrast" in t:
        return HIGH_CONTRAST_THEME_QSS
    elif "dark" in t:
        return DARK_THEME_QSS
    return LIGHT_THEME_QSS

