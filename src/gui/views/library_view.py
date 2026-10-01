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
    show_in_folder_requested = Signal(str)  # Emits full file path to reveal in OS file manager

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_filepath: str = ""
        self.setFixedHeight(28)
        self.setStyleSheet("""
            BreadcrumbBar {
                background-color: #12141c;
                border-top: 1px solid #1f2330;
                padding: 0 4px;
            }
            QLabel {
                color: #64748b;
                font-size: 11px;
            }
        """)

        self._init_ui()

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

        # Action: Reveal in OS File Manager
        self.btn_reveal = QPushButton("Mostra nella cartella")
        self.btn_reveal.setFixedHeight(20)
        self.btn_reveal.setStyleSheet("""
            QPushButton {
                background-color: #1a2234;
                border: 1px solid #0284c7;
                color: #38bdf8;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.btn_reveal.setToolTip("Evidenzia il file nel file manager nativo (Windows Explorer / macOS Finder)")
        self.btn_reveal.clicked.connect(self._on_reveal_clicked)
        self.btn_reveal.setVisible(False)
        self.main_layout.addWidget(self.btn_reveal)

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
            lbl_empty.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
            self.crumbs_layout.addWidget(lbl_empty)
            self.btn_reveal.setVisible(False)
            return

        p = Path(filepath)
        self.btn_reveal.setVisible(True)

        parts = list(p.parts)
        accum_path = Path(parts[0])

        for idx, part in enumerate(parts):
            if idx > 0:
                accum_path = accum_path / part

            # Separator chevron
            if idx > 0:
                sep = QLabel("❯")
                sep.setStyleSheet("color: #475569; font-size: 9px; padding: 0 2px;")
                self.crumbs_layout.addWidget(sep)

            btn_crumb = QPushButton(part)
            btn_crumb.setFixedHeight(20)

            is_last = (idx == len(parts) - 1)
            target_path_str = str(accum_path)

            if is_last:
                # File itself: prominent highlight
                btn_crumb.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        color: #00d2ff;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 0 2px;
                    }
                    QPushButton:hover { text-decoration: underline; }
                """)
            else:
                # Directory segment
                btn_crumb.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        color: #94a3b8;
                        font-size: 11px;
                        padding: 0 2px;
                    }
                    QPushButton:hover { color: #ffffff; text-decoration: underline; }
                """)

            btn_crumb.clicked.connect(lambda _, path_str=target_path_str: self._on_crumb_clicked(path_str))
            self.crumbs_layout.addWidget(btn_crumb)

    def _on_crumb_clicked(self, path_str: str) -> None:
        """Handles click on breadcrumb segment."""
        p = Path(path_str)
        if p.is_dir():
            self.folder_selected.emit(path_str)
            PathResolver.show_in_file_manager(path_str)
        else:
            self.show_in_folder_requested.emit(path_str)
            PathResolver.show_in_file_manager(path_str)

    def _on_reveal_clicked(self) -> None:
        """Reveals current file in Explorer/Finder."""
        if self.current_filepath:
            PathResolver.show_in_file_manager(self.current_filepath)
