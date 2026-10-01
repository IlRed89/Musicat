"""
Pattern Conversion Dialog for Musicat.
Provides Mp3tag-grade conversions:
- Filename -> Tag
- Tag -> Filename
- Tag -> Tag manipulation
Includes live interactive preview for safe batch execution.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..tags.editor import AudioTagEditor
from ..tags.patterns import PatternEngine, sanitize_filename


class PatternDialog(QDialog):
    """Filename <-> Tag and Tag -> Tag converter with live preview."""

    conversion_applied = Signal(list)  # list of updated track dicts

    def __init__(self, selected_tracks: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tracks = selected_tracks

        self.setWindowTitle(f"Musicat Pattern Converter - {len(self.tracks)} track(s)")
        self.resize(850, 600)

        self._init_ui()
        self._update_fn_to_tag_preview()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        tabs = QTabWidget()

        # Tab 1: Filename -> Tag
        tab_fn_to_tag = QWidget()
        l1 = QVBoxLayout(tab_fn_to_tag)
        l1.addWidget(QLabel("<b>Extract Metadata from Filename:</b>"))

        preset_row1 = QHBoxLayout()
        self.cmb_fn_presets = QComboBox()
        self.cmb_fn_presets.addItem("Artist - Title: %artist% - %title%", "%artist% - %title%")
        self.cmb_fn_presets.addItem("Track - Artist - Title: %track% - %artist% - %title%", "%track% - %artist% - %title%")
        self.cmb_fn_presets.addItem("Artist - Title (BPM BPM): %artist% - %title% (%bpm% BPM)", "%artist% - %title% (%bpm% BPM)")
        self.cmb_fn_presets.addItem("Year - Genre/Track - Title: %year% - %genre%/%track% - %title%", "%year% - %genre%/%track% - %title%")
        self.cmb_fn_presets.addItem("Artist - Title [Camelot]: %artist% - %title% [%camelot%]", "%artist% - %title% [%camelot%]")

        self.txt_fn_pattern = QLineEdit("%artist% - %title%")
        self.cmb_fn_presets.currentIndexChanged.connect(lambda: self.txt_fn_pattern.setText(self.cmb_fn_presets.currentData()))
        self.txt_fn_pattern.textChanged.connect(self._update_fn_to_tag_preview)

        preset_row1.addWidget(QLabel("Preset:"))
        preset_row1.addWidget(self.cmb_fn_presets, 2)
        preset_row1.addWidget(self.txt_fn_pattern, 3)
        l1.addLayout(preset_row1)

        self.table_fn_preview = QTableWidget()
        self.table_fn_preview.setColumnCount(4)
        self.table_fn_preview.setHorizontalHeaderLabels(["Filename", "Extracted Artist", "Extracted Title", "Other Extracted Tags"])
        self.table_fn_preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_fn_preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_fn_preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_fn_preview.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        l1.addWidget(self.table_fn_preview)

        tabs.addTab(tab_fn_to_tag, "Filename ➔ Tag")

        # Tab 2: Tag -> Filename
        tab_tag_to_fn = QWidget()
        l2 = QVBoxLayout(tab_tag_to_fn)
        l2.addWidget(QLabel("<b>Rename Files using Database Tags:</b>"))

        preset_row2 = QHBoxLayout()
        self.cmb_tag_presets = QComboBox()
        self.cmb_tag_presets.addItem("Artist - Title: %artist% - %title%", "%artist% - %title%")
        self.cmb_tag_presets.addItem("Artist - Title (%bpm% BPM): %artist% - %title% (%bpm% BPM)", "%artist% - %title% (%bpm% BPM)")
        self.cmb_tag_presets.addItem("[%camelot%] %artist% - %title%: [%camelot%] %artist% - %title%", "[%camelot%] %artist% - %title%")
        self.cmb_tag_presets.addItem("%track% - %artist% - %title%: %track% - %artist% - %title%", "%track% - %artist% - %title%")

        self.txt_tag_pattern = QLineEdit("%artist% - %title%")
        self.cmb_tag_presets.currentIndexChanged.connect(lambda: self.txt_tag_pattern.setText(self.cmb_tag_presets.currentData()))
        self.txt_tag_pattern.textChanged.connect(self._update_tag_to_fn_preview)

        preset_row2.addWidget(QLabel("Preset:"))
        preset_row2.addWidget(self.cmb_tag_presets, 2)
        preset_row2.addWidget(self.txt_tag_pattern, 3)
        l2.addLayout(preset_row2)

        self.table_tag_preview = QTableWidget()
        self.table_tag_preview.setColumnCount(3)
        self.table_tag_preview.setHorizontalHeaderLabels(["Current Filename", "New Proposed Filename", "Status"])
        self.table_tag_preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_tag_preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_tag_preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        l2.addWidget(self.table_tag_preview)

        tabs.addTab(tab_tag_to_fn, "Tag ➔ Filename")

        # Tab 3: Tag -> Tag
        tab_tag_to_tag = QWidget()
        l3 = QVBoxLayout(tab_tag_to_tag)
        l3.addWidget(QLabel("<b>Copy or Manipulate Tag Fields:</b>"))

        t_row = QHBoxLayout()
        self.cmb_tag_action = QComboBox()
        self.cmb_tag_action.addItem("Copy Field", "copy")
        self.cmb_tag_action.addItem("Swap Fields", "swap")

        self.cmb_src_field = QComboBox()
        for fld in ("comment", "initial_key", "remixer", "label", "genre", "album"):
            self.cmb_src_field.addItem(fld)

        self.cmb_dst_field = QComboBox()
        for fld in ("camelot_key", "musical_key", "remixer", "genre", "comment", "album_artist"):
            self.cmb_dst_field.addItem(fld)

        t_row.addWidget(QLabel("Action:"))
        t_row.addWidget(self.cmb_tag_action)
        t_row.addWidget(QLabel("Source:"))
        t_row.addWidget(self.cmb_src_field)
        t_row.addWidget(QLabel("➔ Target:"))
        t_row.addWidget(self.cmb_dst_field)
        t_row.addStretch()

        l3.addLayout(t_row)
        l3.addStretch()

        tabs.addTab(tab_tag_to_tag, "Tag ➔ Tag")

        main_layout.addWidget(tabs)
        self.tabs = tabs

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_apply = QPushButton("Apply Conversion to Files")
        self.btn_apply.setObjectName("PrimaryButton")

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._on_apply)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_apply)
        main_layout.addLayout(btn_box)

    def _update_fn_to_tag_preview(self) -> None:
        pattern = self.txt_fn_pattern.text().strip()
        self.table_fn_preview.setRowCount(len(self.tracks))

        for r, tr in enumerate(self.tracks):
            fn = tr.get("filename", "")
            parsed = PatternEngine.parse_filename_to_tags(fn, pattern)

            self.table_fn_preview.setItem(r, 0, QTableWidgetItem(fn))
            if parsed:
                self.table_fn_preview.setItem(r, 1, QTableWidgetItem(str(parsed.get("artist") or "")))
                self.table_fn_preview.setItem(r, 2, QTableWidgetItem(str(parsed.get("title") or "")))
                other = ", ".join([f"{k}={v}" for k, v in parsed.items() if k not in ("artist", "title") and v])
                self.table_fn_preview.setItem(r, 3, QTableWidgetItem(other))
            else:
                item_err = QTableWidgetItem("No match for pattern")
                item_err.setForeground(Qt.GlobalColor.red)
                self.table_fn_preview.setItem(r, 1, item_err)
                self.table_fn_preview.setItem(r, 2, QTableWidgetItem(""))
                self.table_fn_preview.setItem(r, 3, QTableWidgetItem(""))

    def _update_tag_to_fn_preview(self) -> None:
        pattern = self.txt_tag_pattern.text().strip()
        self.table_tag_preview.setRowCount(len(self.tracks))

        for r, tr in enumerate(self.tracks):
            old_fn = tr.get("filename", "")
            ext = Path(old_fn).suffix
            new_fn = PatternEngine.format_tags_to_filename(tr, pattern, extension=ext)

            self.table_tag_preview.setItem(r, 0, QTableWidgetItem(old_fn))
            self.table_tag_preview.setItem(r, 1, QTableWidgetItem(new_fn))
            status_item = QTableWidgetItem("Ready" if new_fn else "Empty pattern")
            if new_fn:
                status_item.setForeground(Qt.GlobalColor.green)
            self.table_tag_preview.setItem(r, 2, status_item)

    def _on_apply(self) -> None:
        tab_idx = self.tabs.currentIndex()
        updated_tracks: List[Dict[str, Any]] = []

        if tab_idx == 0:  # Filename -> Tag
            pattern = self.txt_fn_pattern.text().strip()
            for tr in self.tracks:
                parsed = PatternEngine.parse_filename_to_tags(tr.get("filename", ""), pattern)
                if parsed:
                    fp = tr.get("filepath", "")
                    AudioTagEditor.write_metadata(fp, parsed)
                    m = dict(tr)
                    m.update(parsed)
                    updated_tracks.append(m)

        elif tab_idx == 1:  # Tag -> Filename
            pattern = self.txt_tag_pattern.text().strip()
            for tr in self.tracks:
                fp = tr.get("filepath", "")
                old_path = Path(fp)
                new_name = PatternEngine.format_tags_to_filename(tr, pattern, extension=old_path.suffix)
                if new_name and new_name != old_path.name:
                    new_path = old_path.parent / new_name
                    try:
                        old_path.rename(new_path)
                        m = dict(tr)
                        m["filepath"] = str(new_path.resolve())
                        m["filename"] = new_name
                        updated_tracks.append(m)
                    except Exception:
                        pass

        elif tab_idx == 2:  # Tag -> Tag
            action = self.cmb_tag_action.currentData()
            src_f = self.cmb_src_field.currentText()
            dst_f = self.cmb_dst_field.currentText()
            for tr in self.tracks:
                m = PatternEngine.apply_tag_to_tag(tr, rule_type=action, source_field=src_f, dest_field=dst_f)
                fp = tr.get("filepath", "")
                AudioTagEditor.write_metadata(fp, {dst_f: m.get(dst_f)})
                updated_tracks.append(m)

        QMessageBox.information(self, "Conversion", f"Applied successfully to {len(updated_tracks)} track(s)!")
        self.conversion_applied.emit(updated_tracks)
        self.accept()
