"""
Smart Organizer & Sorter Dialog for Musicat.
Configures dynamic directory hierarchy rules, generates Dry Run previews,
and dispatches audio files across physical storage.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..organizer.sorter import SmartOrganizer, SortPlanItem


class SorterDialog(QDialog):
    """Smart File Dispatcher dialog with interactive Dry Run preview."""

    operation_completed = Signal(dict)

    def __init__(self, selected_tracks: Optional[List[Dict[str, Any]]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.selected_tracks = selected_tracks or []
        self.current_plan: List[SortPlanItem] = []

        self.setWindowTitle("Musicat Smart Organizer & File Dispatcher")
        self.resize(900, 680)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Title / Description
        title_lbl = QLabel("<b>Smart Organizer & Physical File Dispatcher</b>")
        title_lbl.setStyleSheet("color: #00d2ff; font-size: 15px;")
        desc_lbl = QLabel(
            "Sort files into dynamic folder trees based on Year, Genre, BPM Ranges, or Camelot Keys. "
            "Always inspect the <b>Dry Run</b> preview before applying physical changes."
        )
        desc_lbl.setStyleSheet("color: #8c92a4;")
        main_layout.addWidget(title_lbl)
        main_layout.addWidget(desc_lbl)

        # Config Panel
        config_group = QGroupBox("Dispatcher Rules & Destinations")
        cfg_layout = QVBoxLayout(config_group)

        # Source Selection
        src_row = QHBoxLayout()
        self.radio_selected = QRadioButton(f"Selected tracks in library ({len(self.selected_tracks)} tracks)")
        self.radio_folder = QRadioButton("Source folder on disk:")
        self.radio_selected.setChecked(len(self.selected_tracks) > 0)
        self.radio_folder.setChecked(len(self.selected_tracks) == 0)

        self.txt_src_folder = QLineEdit()
        self.btn_browse_src = QPushButton("Browse...")
        self.btn_browse_src.clicked.connect(self._browse_src)

        src_row.addWidget(self.radio_selected)
        src_row.addWidget(self.radio_folder)
        src_row.addWidget(self.txt_src_folder)
        src_row.addWidget(self.btn_browse_src)
        cfg_layout.addLayout(src_row)

        # Destination Folder
        dst_row = QHBoxLayout()
        dst_lbl = QLabel("Destination Directory:")
        self.txt_dst_folder = QLineEdit()
        self.btn_browse_dst = QPushButton("Browse...")
        self.btn_browse_dst.clicked.connect(self._browse_dst)

        dst_row.addWidget(dst_lbl)
        dst_row.addWidget(self.txt_dst_folder)
        dst_row.addWidget(self.btn_browse_dst)
        cfg_layout.addLayout(dst_row)

        # Rule Preset & Template
        rule_row = QHBoxLayout()
        rule_lbl = QLabel("Organization Rule:")
        self.cmb_presets = QComboBox()
        self.cmb_presets.addItem("By Genre: {genre}/{artist} - {title}{ext}", "{genre}/{artist} - {title}{ext}")
        self.cmb_presets.addItem("By Year: {year}/{artist} - {title}{ext}", "{year}/{artist} - {title}{ext}")
        self.cmb_presets.addItem("By BPM Range: BPM {bpm_range}/{artist} - {title}{ext}", "BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.addItem("By Camelot Key: Key {camelot_key}/{artist} - {title}{ext}", "Key {camelot_key}/{artist} - {title}{ext}")
        self.cmb_presets.addItem("Genre + BPM Range: {genre}/BPM {bpm_range}/{artist} - {title}{ext}", "{genre}/BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.addItem("Genre + Year + BPM: {genre}/{year}/BPM {bpm_range}/{artist} - {title}{ext}", "{genre}/{year}/BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.addItem("Custom Hierarchy Template", "")

        self.txt_pattern = QLineEdit("{genre}/BPM {bpm_range}/{artist} - {title}{ext}")
        self.cmb_presets.currentIndexChanged.connect(self._on_preset_changed)

        rule_row.addWidget(rule_lbl)
        rule_row.addWidget(self.cmb_presets, 2)
        rule_row.addWidget(self.txt_pattern, 3)
        cfg_layout.addLayout(rule_row)

        # Options: BPM Step, Action (Copy/Move), Collision
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("BPM Range Step:"))
        self.spin_bpm_step = QSpinBox()
        self.spin_bpm_step.setRange(1, 20)
        self.spin_bpm_step.setValue(5)
        self.spin_bpm_step.setSuffix(" BPM")
        opt_row.addWidget(self.spin_bpm_step)

        opt_row.addWidget(QLabel("Operation:"))
        self.cmb_action = QComboBox()
        self.cmb_action.addItem("Copy Files (Safe)", "copy")
        self.cmb_action.addItem("Move Files (Physical Sorter)", "move")
        opt_row.addWidget(self.cmb_action)

        opt_row.addWidget(QLabel("Collision Handling:"))
        self.cmb_collision = QComboBox()
        self.cmb_collision.addItem("Auto-Rename: Song (1).mp3", "rename")
        self.cmb_collision.addItem("Overwrite Target", "overwrite")
        self.cmb_collision.addItem("Skip File", "skip")
        opt_row.addWidget(self.cmb_collision)

        opt_row.addStretch()

        self.btn_dry_run = QPushButton("🔍 Generate Dry Run Preview")
        self.btn_dry_run.setObjectName("AccentButton")
        self.btn_dry_run.clicked.connect(self._generate_dry_run)
        opt_row.addWidget(self.btn_dry_run)

        cfg_layout.addLayout(opt_row)
        main_layout.addWidget(config_group)

        # Preview Table
        preview_group = QGroupBox("Dry Run Preview Plan")
        prev_layout = QVBoxLayout(preview_group)

        self.table_preview = QTableWidget()
        self.table_preview.setColumnCount(5)
        self.table_preview.setHorizontalHeaderLabels(["Status", "Source File", "Target Relative Path", "Action", "Details"])
        self.table_preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_preview.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_preview.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        prev_layout.addWidget(self.table_preview)
        main_layout.addWidget(preview_group)

        # Execution Progress & Controls
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        bottom_row = QHBoxLayout()
        self.lbl_summary = QLabel("Preview not generated yet.")
        self.lbl_summary.setStyleSheet("color: #8c92a4;")

        self.btn_close = QPushButton("Close")
        self.btn_execute = QPushButton("⚡ Execute Physical Dispatch")
        self.btn_execute.setObjectName("PrimaryButton")
        self.btn_execute.setEnabled(False)

        self.btn_close.clicked.connect(self.reject)
        self.btn_execute.clicked.connect(self._execute_dispatch)

        bottom_row.addWidget(self.lbl_summary)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_close)
        bottom_row.addWidget(self.btn_execute)

        main_layout.addLayout(bottom_row)

    def _browse_src(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Inbound Source Folder")
        if folder:
            self.txt_src_folder.setText(folder)
            self.radio_folder.setChecked(True)

    def _browse_dst(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Target Destination Folder")
        if folder:
            self.txt_dst_folder.setText(folder)

    def _on_preset_changed(self, idx: int) -> None:
        pattern = self.cmb_presets.currentData()
        if pattern:
            self.txt_pattern.setText(pattern)

    def _generate_dry_run(self) -> None:
        dest_dir = self.txt_dst_folder.text().strip()
        if not dest_dir:
            QMessageBox.warning(self, "Missing Destination", "Please specify a destination directory.")
            return

        rule_pattern = self.txt_pattern.text().strip()
        if not rule_pattern:
            QMessageBox.warning(self, "Missing Pattern", "Please enter a valid directory pattern.")
            return

        # Determine source items
        items_to_sort: List[Any] = []
        if self.radio_selected.isChecked() and self.selected_tracks:
            items_to_sort = self.selected_tracks
        elif self.txt_src_folder.text().strip():
            src_dir = Path(self.txt_src_folder.text().strip())
            if not src_dir.exists():
                QMessageBox.warning(self, "Invalid Source", "Source folder does not exist.")
                return
            from ..tags.editor import SUPPORTED_EXTENSIONS
            import os
            for root, _, files in os.walk(str(src_dir)):
                for f in files:
                    if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS:
                        items_to_sort.append(os.path.join(root, f))
        else:
            QMessageBox.warning(self, "No Items", "No tracks selected and no source folder specified.")
            return

        if not items_to_sort:
            QMessageBox.information(self, "Empty", "No audio tracks found to organize.")
            return

        action = self.cmb_action.currentData()
        bpm_step = self.spin_bpm_step.value()
        collision = self.cmb_collision.currentData()

        self.current_plan = SmartOrganizer.build_plan(
            source_items=items_to_sort,
            dest_dir=dest_dir,
            rule_pattern=rule_pattern,
            action=action,
            bpm_step=bpm_step,
            collision_mode=collision,
        )

        # Populate Preview Table
        self.table_preview.setRowCount(len(self.current_plan))
        ok_count = 0
        collision_count = 0
        missing_count = 0

        for r, item in enumerate(self.current_plan):
            status_item = QTableWidgetItem(item.status)
            if item.status == "OK":
                status_item.setForeground(Qt.GlobalColor.green)
                ok_count += 1
            elif item.status == "COLLISION":
                status_item.setForeground(Qt.GlobalColor.yellow)
                collision_count += 1
            elif item.status == "MISSING_TAG":
                status_item.setForeground(Qt.GlobalColor.cyan)
                missing_count += 1
            else:
                status_item.setForeground(Qt.GlobalColor.red)

            src_item = QTableWidgetItem(Path(item.source_path).name)
            src_item.setToolTip(item.source_path)

            dst_item = QTableWidgetItem(item.relative_target)
            dst_item.setToolTip(item.target_path)

            act_item = QTableWidgetItem(item.action.upper())
            msg_item = QTableWidgetItem(item.message)

            self.table_preview.setItem(r, 0, status_item)
            self.table_preview.setItem(r, 1, src_item)
            self.table_preview.setItem(r, 2, dst_item)
            self.table_preview.setItem(r, 3, act_item)
            self.table_preview.setItem(r, 4, msg_item)

        self.lbl_summary.setText(
            f"<b>Plan Summary:</b> Total: {len(self.current_plan)} | OK: {ok_count} | Collisions: {collision_count} | Missing Tags: {missing_count}"
        )
        self.btn_execute.setEnabled(len(self.current_plan) > 0)

    def _execute_dispatch(self) -> None:
        if not self.current_plan:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Dispatch",
            f"Are you sure you want to {self.cmb_action.currentText()} {len(self.current_plan)} tracks to destination?\nThis will physically create folders and move/copy files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.current_plan))
        self.progress_bar.setValue(0)

        def progress_cb(current, total, item):
            self.progress_bar.setValue(current)

        result = SmartOrganizer.execute_plan(self.current_plan, progress_callback=progress_cb)
        self.progress_bar.setVisible(False)

        QMessageBox.information(
            self,
            "Dispatch Complete",
            f"Organized successfully!\nCopied/Moved: {result['success']}\nSkipped: {result['skipped']}\nFailed: {result['failed']}",
        )
        self.operation_completed.emit(result)
        self.accept()
