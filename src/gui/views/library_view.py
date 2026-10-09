"""
Library View Components: Breadcrumb Bar, Folder Navigation & Native Explorer Helpers for Musicat.

Provides:
- Interactive BreadcrumbBar displaying directory hierarchy with clickable path tokens.
- Native file manager interaction (Windows Explorer / macOS Finder / Linux xdg-open).
- Direct folder filter dispatch.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.path_resolver import PathResolver


class BreadcrumbBar(QFrame):
    """Interactive horizontal breadcrumbs displaying clickable directory path segments."""

    folder_selected = Signal(str)  # Emits directory path when segment clicked
    directory_selected = Signal(str)  # Emits directory path when segment clicked
    show_in_folder_requested = Signal(str)  # Emits full file path to reveal in OS file manager

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_filepath: str = ""
        self.setFixedHeight(28)
        self._is_light: bool = True

        self._init_ui()
        from src.core.settings import SettingsManager
        theme = SettingsManager.get_instance().get("ui", "theme", "light")
        self.update_theme(theme)

    def update_theme(self, theme_id: str = "light") -> None:
        """Adapts breadcrumb bar colors seamlessly to current Light or Dark theme."""
        self._is_light = "dark" not in (theme_id or "").lower()
        if self._is_light:
            self.setStyleSheet("""
                BreadcrumbBar {
                    background-color: #f8f9fa;
                    border-top: 1px solid #dee2e6;
                    border-bottom: 1px solid #dee2e6;
                    padding: 0 4px;
                }
                QLabel {
                    color: #495057;
                    font-size: 11px;
                }
            """)
        else:
            self.setStyleSheet("""
                BreadcrumbBar {
                    background-color: #12141c;
                    border-top: 1px solid #1f2330;
                    padding: 0 4px;
                }
                QLabel {
                    color: #94a3b8;
                    font-size: 11px;
                }
            """)
        self.set_path(self.current_filepath)

    def _init_ui(self) -> None:
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(6, 2, 6, 2)
        self.main_layout.setSpacing(4)

        icon_lbl = QLabel("📁")
        icon_lbl.setStyleSheet("font-size: 12px;")
        self.main_layout.addWidget(icon_lbl)

        # Container for dynamic breadcrumb buttons
        self.crumbs_widget = QWidget()
        self.crumbs_layout = QHBoxLayout(self.crumbs_widget)
        self.crumbs_layout.setContentsMargins(0, 0, 0, 0)
        self.crumbs_layout.setSpacing(2)

        self.main_layout.addWidget(self.crumbs_widget)
        self.main_layout.addStretch()

        self.set_path("")

    def set_path(self, filepath: str) -> None:
        """Parses filepath and generates clickable path tokens."""
        self.current_filepath = filepath

        # Clear existing crumb widgets
        while self.crumbs_layout.count():
            item = self.crumbs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not filepath:
            lbl_empty = QLabel("Nessun brano selezionato")
            empty_color = "#6c757d" if self._is_light else "#64748b"
            lbl_empty.setStyleSheet(f"color: {empty_color}; font-size: 11px; font-style: italic;")
            self.crumbs_layout.addWidget(lbl_empty)
            return

        p = Path(filepath)

        parts = list(p.parts)
        accum_path = Path(parts[0])

        for idx, part in enumerate(parts):
            if idx > 0:
                accum_path = accum_path / part

            # Separator chevron
            if idx > 0:
                sep = QLabel("❯")
                sep_color = "#adb5bd" if self._is_light else "#475569"
                sep.setStyleSheet(f"color: {sep_color}; font-size: 9px; padding: 0 2px;")
                self.crumbs_layout.addWidget(sep)

            btn_crumb = QPushButton(part)
            btn_crumb.setFixedHeight(20)

            is_last = (idx == len(parts) - 1)
            target_path_str = str(accum_path)

            if is_last:
                # File itself: prominent highlight
                highlight_col = "#0d6efd" if self._is_light else "#00d2ff"
                btn_crumb.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        color: {highlight_col};
                        font-weight: bold;
                        font-size: 11px;
                        padding: 0 2px;
                    }}
                    QPushButton:hover {{ text-decoration: underline; }}
                """)
            else:
                # Directory segment
                seg_col = "#495057" if self._is_light else "#94a3b8"
                hover_col = "#0d6efd" if self._is_light else "#ffffff"
                btn_crumb.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        color: {seg_col};
                        font-size: 11px;
                        padding: 0 2px;
                    }}
                    QPushButton:hover {{ color: {hover_col}; text-decoration: underline; }}
                """)

            btn_crumb.clicked.connect(lambda _, path_str=target_path_str: self._on_crumb_clicked(path_str))
            self.crumbs_layout.addWidget(btn_crumb)

    def _on_crumb_clicked(self, path_str: str) -> None:
        """Handles click on breadcrumb segment."""
        p = Path(path_str)
        if p.is_dir():
            self.folder_selected.emit(path_str)
            self.directory_selected.emit(path_str)
            PathResolver.show_in_file_manager(path_str)
        else:
            self.show_in_folder_requested.emit(path_str)
            PathResolver.show_in_file_manager(path_str)

    def _on_reveal_clicked(self) -> None:
        """Reveals current file in Explorer/Finder."""
        if self.current_filepath:
            PathResolver.show_in_file_manager(self.current_filepath)
