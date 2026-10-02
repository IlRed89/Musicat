"""
Dedicated Smart Crates Workbench & Visual Rule Builder for Musicat.

Features:
- Independent workbench for creating, configuring, and managing Smart Crates.
- Visual rule builder: Genre (OR logic), BPM range & tolerance, Camelot harmonic matching, Year, Audio Quality, Tags.
- Crate management: Create, rename, duplicate, reorder, delete, and modify rules.
- Real-time dynamic track preview table displaying matching library tracks.
- Direct DJ export: Extended M3U8 playlists compatible with Rekordbox, Serato, Traktor, Engine DJ.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.audio.camelot import CAMELOT_KEYS_ORDERED, CamelotWheel
from src.core.db import Database
from src.core.filter_engine import FilterCriteria, LiveFilterEngine
from src.core.i18n import I18n, _t
from src.core.logger import MusicatLogger
from src.gui.table_model import TrackTableModel


COMMON_PRESET_GENRES = [
    "Tech House",
    "House",
    "Deep House",
    "Techno",
    "Melodic Techno",
    "Afro House",
    "Progressive House",
    "Minimal / Deep Tech",
    "Drum & Bass",
    "Trance",
    "Nu Disco / Disco",
    "Electro",
]


class SmartCratesView(QWidget):
    """Independent Smart Crates Workbench screen."""

    play_track_requested = Signal(dict)
    crates_updated = Signal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.filter_engine = LiveFilterEngine(db)
        self.table_model = TrackTableModel()
        self.active_crate_id: Optional[int] = None
        self.active_crate_name: str = ""

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(120)
        self._debounce_timer.timeout.connect(self._preview_active_criteria)

        self._init_ui()
        self._load_crates_list()
        self._retranslate_ui()
        I18n.get_instance().language_changed.connect(self._retranslate_ui)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. Top Header Bar
        # -------------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.lbl_title = QLabel("🎛️ SMART CRATES WORKBENCH")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0d6efd;")
        self.lbl_subtitle = QLabel("Costruttore di casse intelligenti basate su regole logiche per DJ set")
        self.lbl_subtitle.setStyleSheet("font-size: 11px; color: #6c757d;")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)
        header.addLayout(title_box)

        header.addStretch()

        self.btn_top_new = QPushButton(_t("crates_btn_new", "+ Nuovo Crate"))
        self.btn_top_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_top_new.setStyleSheet("background-color: #0d6efd; color: #ffffff; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.btn_top_new.clicked.connect(self._on_create_new_crate)

        self.btn_top_save = QPushButton(_t("crates_btn_save", "💾 Salva Regole"))
        self.btn_top_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_top_save.setStyleSheet("background-color: #198754; color: #ffffff; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.btn_top_save.clicked.connect(self._on_save_active_crate)

        self.btn_top_export = QPushButton(_t("crates_btn_export", "📤 Esporta Playlist DJ"))
        self.btn_top_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_top_export.setStyleSheet("background-color: #0dcaf0; color: #000000; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.btn_top_export.clicked.connect(self._on_export_crate_playlist)

        header.addWidget(self.btn_top_new)
        header.addWidget(self.btn_top_save)
        header.addWidget(self.btn_top_export)

        main_layout.addLayout(header)

        # -------------------------------------------------------------
        # 2. Main Three-Pane Horizontal Splitter
        # -------------------------------------------------------------
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # --- LEFT PANE: CRATES LIST ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.lbl_crates_list = QLabel(_t("crates_list_header", "📁 I Tuoi Smart Crates"))
        self.lbl_crates_list.setStyleSheet("font-weight: bold; font-size: 12px;")
        left_layout.addWidget(self.lbl_crates_list)

        self.txt_search_crates = QLineEdit()
        self.txt_search_crates.setPlaceholderText(_t("crates_search_placeholder", "Cerca tra i Crates..."))
        self.txt_search_crates.setClearButtonEnabled(True)
        self.txt_search_crates.textChanged.connect(self._filter_crates_list)
        left_layout.addWidget(self.txt_search_crates)

        self.list_crates = QListWidget()
        self.list_crates.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_crates.currentRowChanged.connect(self._on_crate_selected)
        left_layout.addWidget(self.list_crates, 1)

        # Bottom List Controls
        btn_crate_actions = QHBoxLayout()
        btn_crate_actions.setSpacing(4)

        self.btn_crate_dup = QPushButton(_t("crates_btn_dup", "Duplica"))
        self.btn_crate_dup.clicked.connect(self._on_duplicate_crate)

        self.btn_crate_ren = QPushButton(_t("crates_btn_ren", "Rinomina"))
        self.btn_crate_ren.clicked.connect(self._on_rename_crate)

        self.btn_crate_del = QPushButton(_t("crates_btn_del", "Elimina"))
        self.btn_crate_del.setStyleSheet("color: #dc3545;")
        self.btn_crate_del.clicked.connect(self._on_delete_crate)

        btn_crate_actions.addWidget(self.btn_crate_dup)
        btn_crate_actions.addWidget(self.btn_crate_ren)
        btn_crate_actions.addWidget(self.btn_crate_del)
        left_layout.addLayout(btn_crate_actions)

        self.main_splitter.addWidget(left_widget)

        # --- CENTER PANE: VISUAL RULE BUILDER ---
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QFrame.Shape.NoFrame)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(6, 0, 6, 0)
        center_layout.setSpacing(10)

        # Crate Name Header
        name_box = QHBoxLayout()
        self.lbl_crate_name_title = QLabel(_t("crates_name_label", "Nome Crate:"))
        self.lbl_crate_name_title.setStyleSheet("font-weight: bold;")
        self.txt_crate_name = QLineEdit()
        self.txt_crate_name.setPlaceholderText("Es. Peak Time Tech House 126-128")
        name_box.addWidget(self.lbl_crate_name_title)
        name_box.addWidget(self.txt_crate_name, 1)
        center_layout.addLayout(name_box)

        # 1. Search Query Rule
        grp_search = QGroupBox(_t("crates_rule_search", "🔍 Ricerca Testuale & Parole Chiave"))
        f_search = QFormLayout(grp_search)
        self.txt_rule_query = QLineEdit()
        self.txt_rule_query.setPlaceholderText("Titolo, Artista, Remix, Album...")
        self.txt_rule_query.textChanged.connect(self._trigger_preview_update)
        f_search.addRow("Parole chiave:", self.txt_rule_query)
        center_layout.addWidget(grp_search)

        # 2. Genre Rule
        grp_genre = QGroupBox(_t("crates_rule_genre", "🏷️ Generi Musicali (Logica OR)"))
        v_genre = QVBoxLayout(grp_genre)
        self.txt_rule_genres = QLineEdit()
        self.txt_rule_genres.setPlaceholderText("Es. Tech House, House, Deep House (separati da virgola)")
        self.txt_rule_genres.textChanged.connect(self._trigger_preview_update)
        v_genre.addWidget(self.txt_rule_genres)

        # Quick Genre Tags Cloud
        self.genre_cloud_layout = QHBoxLayout()
        self.genre_cloud_layout.setSpacing(4)
        for g in COMMON_PRESET_GENRES[:6]:
            btn_g = QPushButton(f"+ {g}")
            btn_g.setStyleSheet("font-size: 10px; padding: 2px 6px;")
            btn_g.clicked.connect(lambda _, gen=g: self._add_genre_preset(gen))
            self.genre_cloud_layout.addWidget(btn_g)
        self.genre_cloud_layout.addStretch()
        v_genre.addLayout(self.genre_cloud_layout)
        center_layout.addWidget(grp_genre)

        # 3. BPM Range & Tolerance Rule
        grp_bpm = QGroupBox(_t("crates_rule_bpm", "⚡ BPM & Compatibilità Tempo"))
        f_bpm = QFormLayout(grp_bpm)

        target_row = QHBoxLayout()
        self.spin_target_bpm = QDoubleSpinBox()
        self.spin_target_bpm.setRange(0, 250)
        self.spin_target_bpm.setDecimals(1)
        self.spin_target_bpm.setSpecialValueText("Nessun Target")
        self.spin_target_bpm.valueChanged.connect(self._on_target_bpm_changed)

        self.cmb_tolerance = QComboBox()
        self.cmb_tolerance.addItem("±2% BPM", 2.0)
        self.cmb_tolerance.addItem("±4% BPM (Standard DJ)", 4.0)
        self.cmb_tolerance.addItem("±6% BPM", 6.0)
        self.cmb_tolerance.addItem("±8% BPM (Pitch Ampio)", 8.0)
        self.cmb_tolerance.setCurrentIndex(1)
        self.cmb_tolerance.currentIndexChanged.connect(self._on_target_bpm_changed)

        target_row.addWidget(self.spin_target_bpm)
        target_row.addWidget(self.cmb_tolerance)
        f_bpm.addRow("Target BPM:", target_row)

        range_row = QHBoxLayout()
        self.spin_min_bpm = QDoubleSpinBox()
        self.spin_min_bpm.setRange(0, 250)
        self.spin_min_bpm.setDecimals(1)
        self.spin_min_bpm.setSpecialValueText("Min Libero")
        self.spin_min_bpm.valueChanged.connect(self._trigger_preview_update)

        self.spin_max_bpm = QDoubleSpinBox()
        self.spin_max_bpm.setRange(0, 250)
        self.spin_max_bpm.setDecimals(1)
        self.spin_max_bpm.setSpecialValueText("Max Libero")
        self.spin_max_bpm.valueChanged.connect(self._trigger_preview_update)

        range_row.addWidget(self.spin_min_bpm)
        range_row.addWidget(self.spin_max_bpm)
        f_bpm.addRow("Range BPM (Min - Max):", range_row)
        center_layout.addWidget(grp_bpm)

        # 4. Harmonic Key (Camelot) Rule
        grp_key = QGroupBox(_t("crates_rule_key", "🎡 Chiave Armonica (Camelot Wheel)"))
        f_key = QFormLayout(grp_key)

        self.cmb_camelot = QComboBox()
        self.cmb_camelot.addItem("Tutte le Chiavi (Nessun filtro)", "")
        for k in CAMELOT_KEYS_ORDERED:
            self.cmb_camelot.addItem(f"{k} - {CamelotWheel.get_musical_name(k)}", k)
        self.cmb_camelot.currentIndexChanged.connect(self._trigger_preview_update)
        f_key.addRow("Chiave Camelot:", self.cmb_camelot)

        self.chk_harmonic_compatible = QCheckBox("Includi chiavi compatibili armonicamente (±1, Relativo, +2 Energy)")
        self.chk_harmonic_compatible.setChecked(True)
        self.chk_harmonic_compatible.toggled.connect(self._trigger_preview_update)
        f_key.addRow("", self.chk_harmonic_compatible)
        center_layout.addWidget(grp_key)

        # 5. Year & Decade Range
        grp_year = QGroupBox(_t("crates_rule_year", "📅 Anno di Uscita"))
        f_year = QFormLayout(grp_year)
        year_row = QHBoxLayout()
        self.spin_year_min = QSpinBox()
        self.spin_year_min.setRange(0, 2030)
        self.spin_year_min.setSpecialValueText("Qualsiasi")
        self.spin_year_min.valueChanged.connect(self._trigger_preview_update)

        self.spin_year_max = QSpinBox()
        self.spin_year_max.setRange(0, 2030)
        self.spin_year_max.setSpecialValueText("Qualsiasi")
        self.spin_year_max.valueChanged.connect(self._trigger_preview_update)

        year_row.addWidget(self.spin_year_min)
        year_row.addWidget(self.spin_year_max)
        f_year.addRow("Range Anno (Da - A):", year_row)
        center_layout.addWidget(grp_year)

        # 6. Audio Quality & Tags
        grp_quality = QGroupBox(_t("crates_rule_quality", "🔊 Qualità Audio & Tag DJ"))
        f_quality = QFormLayout(grp_quality)

        self.cmb_quality = QComboBox()
        self.cmb_quality.addItem("Tutto l'Audio", "")
        self.cmb_quality.addItem("✅ Solo Conforme (OK)", "ok")
        self.cmb_quality.addItem("⚠️ Escludi Clipping / Distorsione", "no_clipping")
        self.cmb_quality.addItem("⚡ Solo Tracce Problematiche", "problematic")
        self.cmb_quality.currentIndexChanged.connect(self._trigger_preview_update)
        f_quality.addRow("Filtro Qualità:", self.cmb_quality)

        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        self.btn_tag_intro = QPushButton("Intro")
        self.btn_tag_vocal = QPushButton("Vocal")
        self.btn_tag_inst = QPushButton("Instrumental")
        self.btn_tag_acapella = QPushButton("Acapella")
        self.btn_tag_club = QPushButton("Club")

        self.tag_buttons = [self.btn_tag_intro, self.btn_tag_vocal, self.btn_tag_inst, self.btn_tag_acapella, self.btn_tag_club]
        for btn in self.tag_buttons:
            btn.setCheckable(True)
            btn.toggled.connect(self._trigger_preview_update)
            tags_layout.addWidget(btn)
        tags_layout.addStretch()
        f_quality.addRow("Tag Richiesti:", tags_layout)
        center_layout.addWidget(grp_quality)

        center_layout.addStretch()
        center_scroll.setWidget(center_widget)
        self.main_splitter.addWidget(center_scroll)

        # --- RIGHT PANE: REAL-TIME TRACK PREVIEW TABLE ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        preview_header = QHBoxLayout()
        self.lbl_preview_title = QLabel(_t("crates_preview_title", "🎵 Anteprima Tracce Incluse"))
        self.lbl_preview_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #0d6efd;")
        self.lbl_preview_stats = QLabel("0 tracce")
        self.lbl_preview_stats.setStyleSheet("font-size: 11px; color: #6c757d; font-weight: 600;")
        preview_header.addWidget(self.lbl_preview_title)
        preview_header.addStretch()
        preview_header.addWidget(self.lbl_preview_stats)
        right_layout.addLayout(preview_header)

        self.table_preview = QTableView(right_widget)
        self.table_preview.setModel(self.table_model)
        self.table_preview.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_preview.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_preview.setSortingEnabled(True)
        self.table_preview.horizontalHeader().setStretchLastSection(True)
        self.table_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_preview.verticalHeader().setDefaultSectionSize(26)
        self.table_preview.doubleClicked.connect(self._on_table_row_double_clicked)
        right_layout.addWidget(self.table_preview, 1)

        # Export Action Bar under Table
        export_bar = QHBoxLayout()
        export_bar.setSpacing(8)

        self.btn_export_m3u8 = QPushButton(_t("crates_btn_export_m3u8", "📤 Esporta M3U8 (Rekordbox / Serato / Traktor)"))
        self.btn_export_m3u8.setStyleSheet("background-color: #0d6efd; color: #ffffff; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_export_m3u8.clicked.connect(self._on_export_crate_playlist)

        self.btn_reset_rules = QPushButton(_t("crates_btn_reset_rules", "✕ Ripristina Regole"))
        self.btn_reset_rules.clicked.connect(self._on_reset_active_rules)

        export_bar.addWidget(self.btn_export_m3u8)
        export_bar.addStretch()
        export_bar.addWidget(self.btn_reset_rules)
        right_layout.addLayout(export_bar)

        self.main_splitter.addWidget(right_widget)

        # Set Splitter Stretch Factors: Left 1, Center 2, Right 3
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setStretchFactor(2, 3)

        main_layout.addWidget(self.main_splitter, 1)

    # -------------------------------------------------------------
    # Logic: Load & Manage Crates List
    # -------------------------------------------------------------
    def refresh_crates(self) -> None:
        """Public refresh method to reload the crates list and update track counts."""
        self._load_crates_list()

    def _load_crates_list(self) -> None:
        """Populates the crates list on the left pane from the SQLite database."""
        self.list_crates.blockSignals(True)
        self.list_crates.clear()
        crates = self.filter_engine.get_smart_crates()

        for c in crates:
            crit = self.filter_engine.load_smart_crate_criteria(c["id"])
            count = len(self.filter_engine.query(crit)) if crit else 0
            item = QListWidgetItem(f"⚡ {c['name']} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, c)
            self.list_crates.addItem(item)

        self.list_crates.blockSignals(False)

        if self.list_crates.count() > 0:
            self.list_crates.setCurrentRow(0)
        else:
            self._on_reset_active_rules()

    def _filter_crates_list(self, query: str) -> None:
        q = query.strip().lower()
        for i in range(self.list_crates.count()):
            item = self.list_crates.item(i)
            match = q in item.text().lower()
            item.setHidden(not match)

    def _on_crate_selected(self, row: int) -> None:
        if row < 0 or row >= self.list_crates.count():
            return
        item = self.list_crates.item(row)
        c_data = item.data(Qt.ItemDataRole.UserRole)
        if not c_data:
            return

        self.active_crate_id = c_data["id"]
        self.active_crate_name = c_data["name"]
        self.txt_crate_name.setText(self.active_crate_name)

        crit = self.filter_engine.load_smart_crate_criteria(self.active_crate_id)
        if crit:
            self._apply_criteria_to_ui(crit)
        self._trigger_preview_update()

    def _apply_criteria_to_ui(self, crit: FilterCriteria) -> None:
        """Loads a FilterCriteria into the visual rule builder fields."""
        self.txt_rule_query.setText(crit.query_text)
        self.txt_rule_genres.setText(", ".join(crit.genres) if crit.genres else "")

        if crit.target_bpm:
            self.spin_target_bpm.setValue(crit.target_bpm)
        else:
            self.spin_target_bpm.setValue(0)

        tol = crit.bpm_tolerance_pct or 4.0
        idx = self.cmb_tolerance.findData(tol)
        if idx >= 0:
            self.cmb_tolerance.setCurrentIndex(idx)

        self.spin_min_bpm.setValue(crit.bpm_min or 0)
        self.spin_max_bpm.setValue(crit.bpm_max or 0)

        k = crit.camelot_key or ""
        idx_k = self.cmb_camelot.findData(k)
        self.cmb_camelot.setCurrentIndex(idx_k if idx_k >= 0 else 0)
        self.chk_harmonic_compatible.setChecked(crit.harmonic_matches_only)

        self.spin_year_min.setValue(crit.year_min or 0)
        self.spin_year_max.setValue(crit.year_max or 0)

        q = crit.quality_filter or ""
        idx_q = self.cmb_quality.findData(q)
        self.cmb_quality.setCurrentIndex(idx_q if idx_q >= 0 else 0)

        tags_set = set(crit.tags)
        self.btn_tag_intro.setChecked("Intro" in tags_set)
        self.btn_tag_vocal.setChecked("Vocal" in tags_set)
        self.btn_tag_inst.setChecked("Instrumental" in tags_set)
        self.btn_tag_acapella.setChecked("Acapella" in tags_set)
        self.btn_tag_club.setChecked("Club" in tags_set)

    def _get_current_builder_criteria(self) -> FilterCriteria:
        """Constructs a FilterCriteria object from current builder widget states."""
        query_text = self.txt_rule_query.text().strip()
        genres_raw = self.txt_rule_genres.text().strip()
        genres = [g.strip() for g in genres_raw.split(",") if g.strip()]

        target_b = self.spin_target_bpm.value()
        tol = float(self.cmb_tolerance.currentData() or 4.0)

        min_b = self.spin_min_bpm.value()
        max_b = self.spin_max_bpm.value()

        key = self.cmb_camelot.currentData() or ""
        harmonic = self.chk_harmonic_compatible.isChecked()

        y_min = self.spin_year_min.value()
        y_max = self.spin_year_max.value()

        q_filter = self.cmb_quality.currentData() or None

        tags: List[str] = []
        if self.btn_tag_intro.isChecked():
            tags.append("Intro")
        if self.btn_tag_vocal.isChecked():
            tags.append("Vocal")
        if self.btn_tag_inst.isChecked():
            tags.append("Instrumental")
        if self.btn_tag_acapella.isChecked():
            tags.append("Acapella")
        if self.btn_tag_club.isChecked():
            tags.append("Club")

        return FilterCriteria(
            query_text=query_text,
            genres=genres,
            target_bpm=target_b if target_b > 0 else None,
            bpm_tolerance_pct=tol if target_b > 0 else None,
            bpm_min=min_b if min_b > 0 else None,
            bpm_max=max_b if max_b > 0 else None,
            camelot_key=key if key else None,
            harmonic_matches_only=harmonic,
            year_min=y_min if y_min > 0 else None,
            year_max=y_max if y_max > 0 else None,
            quality_filter=q_filter,
            tags=tags,
        )

    def _trigger_preview_update(self) -> None:
        self._debounce_timer.start()

    def _on_target_bpm_changed(self) -> None:
        tb = self.spin_target_bpm.value()
        if tb > 0:
            tol = float(self.cmb_tolerance.currentData() or 4.0)
            b_min, b_max = CamelotWheel.calculate_bpm_tolerance_range(tb, tol)
            self.spin_min_bpm.blockSignals(True)
            self.spin_max_bpm.blockSignals(True)
            self.spin_min_bpm.setValue(b_min)
            self.spin_max_bpm.setValue(b_max)
            self.spin_min_bpm.blockSignals(False)
            self.spin_max_bpm.blockSignals(False)
        self._trigger_preview_update()

    def _add_genre_preset(self, genre: str) -> None:
        current = self.txt_rule_genres.text().strip()
        parts = [p.strip() for p in current.split(",") if p.strip()]
        if genre not in parts:
            parts.append(genre)
            self.txt_rule_genres.setText(", ".join(parts))

    def _preview_active_criteria(self) -> None:
        """Evaluates active rules against the library and updates the preview table."""
        try:
            crit = self._get_current_builder_criteria()
            tracks = self.filter_engine.query(crit)
            self.table_model.set_tracks(tracks)

            total_dur = sum(t.get("duration") or 0.0 for t in tracks)
            hours = int(total_dur // 3600)
            mins = int((total_dur % 3600) // 60)
            self.lbl_preview_stats.setText(f"{len(tracks):,} tracce ({hours}h {mins}m)")
        except Exception:
            pass

    # -------------------------------------------------------------
    # Crate CRUD Operations
    # -------------------------------------------------------------
    def _on_create_new_crate(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            _t("crates_new_title", "Nuovo Smart Crate"),
            _t("crates_new_prompt", "Inserisci il nome del nuovo Smart Crate:"),
        )
        if ok and name.strip():
            c_name = name.strip()
            crit = FilterCriteria()
            crate_id = self.filter_engine.save_smart_crate(c_name, crit)
            self.active_crate_id = crate_id
            self.active_crate_name = c_name
            self._load_crates_list()
            # Select new crate
            for i in range(self.list_crates.count()):
                data = self.list_crates.item(i).data(Qt.ItemDataRole.UserRole)
                if data and data.get("id") == crate_id:
                    self.list_crates.setCurrentRow(i)
                    break
            self.crates_updated.emit()

    def _on_save_active_crate(self) -> None:
        c_name = self.txt_crate_name.text().strip()
        if not c_name:
            QMessageBox.warning(self, "Attenzione", "Inserisci un nome valido per lo Smart Crate prima di salvare.")
            return

        crit = self._get_current_builder_criteria()
        crate_id = self.filter_engine.save_smart_crate(c_name, crit)
        self.active_crate_id = crate_id
        self.active_crate_name = c_name
        self._load_crates_list()
        self.crates_updated.emit()
        QMessageBox.information(self, "Crate Salvato", f"Regole dello Smart Crate '{c_name}' salvate con successo!")

    def _on_rename_crate(self) -> None:
        if not self.active_crate_id:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Rinomina Crate",
            "Nuovo nome per lo Smart Crate:",
            text=self.active_crate_name,
        )
        if ok and new_name.strip():
            renamed = self.filter_engine.rename_smart_crate(self.active_crate_id, new_name.strip())
            if renamed:
                self.active_crate_name = new_name.strip()
                self.txt_crate_name.setText(self.active_crate_name)
                self._load_crates_list()
                self.crates_updated.emit()

    def _on_duplicate_crate(self) -> None:
        if not self.active_crate_id:
            return
        dup_name = f"{self.active_crate_name} (Copia)"
        new_id = self.filter_engine.duplicate_smart_crate(self.active_crate_id, dup_name)
        if new_id:
            self._load_crates_list()
            self.crates_updated.emit()
            QMessageBox.information(self, "Duplicato", f"Smart Crate duplicato come '{dup_name}'.")

    def _on_delete_crate(self) -> None:
        if not self.active_crate_id:
            return
        reply = QMessageBox.question(
            self,
            "Conferma Eliminazione",
            f"Sei sicuro di voler eliminare lo Smart Crate '{self.active_crate_name}'?\n(I file musicali sul disco non verranno toccati)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.filter_engine.delete_smart_crate(self.active_crate_id)
            self.active_crate_id = None
            self.active_crate_name = ""
            self._load_crates_list()
            self.crates_updated.emit()

    def _on_reset_active_rules(self) -> None:
        self.txt_crate_name.clear()
        self.txt_rule_query.clear()
        self.txt_rule_genres.clear()
        self.spin_target_bpm.setValue(0)
        self.spin_min_bpm.setValue(0)
        self.spin_max_bpm.setValue(0)
        self.cmb_camelot.setCurrentIndex(0)
        self.chk_harmonic_compatible.setChecked(True)
        self.spin_year_min.setValue(0)
        self.spin_year_max.setValue(0)
        self.cmb_quality.setCurrentIndex(0)
        for btn in self.tag_buttons:
            btn.setChecked(False)
        self._trigger_preview_update()

    # -------------------------------------------------------------
    # DJ Playlist Export
    # -------------------------------------------------------------
    def _on_export_crate_playlist(self) -> None:
        tracks = self.table_model._tracks
        if not tracks:
            QMessageBox.warning(self, "Nessuna Traccia", "Nessun brano corrisponde ai criteri del crate selezionato.")
            return

        c_name = self.txt_crate_name.text().strip() or "Smart_Crate"
        safe_name = "".join(c for c in c_name if c.isalnum() or c in ("-", "_", " ")).strip()
        default_filename = f"{safe_name}_{len(tracks)}_tracks.m3u8"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta Playlist Smart Crate",
            default_filename,
            "Extended M3U8 Playlist (*.m3u8 *.m3u)",
        )
        if file_path:
            try:
                out_path = LiveFilterEngine.export_m3u(tracks, file_path)
                QMessageBox.information(
                    self,
                    "Esportazione Completata",
                    f"Esportate con successo {len(tracks):,} tracce in:\n{out_path}\n\n"
                    "Formato esteso M3U8 compatibile nativamente con Rekordbox, Serato DJ, Traktor Pro ed Engine DJ.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Errore Esportazione", f"Impossibile esportare la playlist:\n{e}")

    def _on_table_row_double_clicked(self, index) -> None:
        track = self.table_model.get_track(index.row())
        if track:
            self.play_track_requested.emit(track)

    def _retranslate_ui(self) -> None:
        """Updates text elements based on active locale."""
        self.lbl_title.setText(_t("crates_workbench_title", "🎛️ SMART CRATES WORKBENCH"))
        self.lbl_subtitle.setText(_t("crates_workbench_sub", "Costruttore di casse intelligenti basate su regole logiche per DJ set"))
        self.btn_top_new.setText(_t("crates_btn_new", "+ Nuovo Crate"))
        self.btn_top_save.setText(_t("crates_btn_save", "💾 Salva Regole"))
        self.btn_top_export.setText(_t("crates_btn_export", "📤 Esporta Playlist DJ"))
        self.lbl_crates_list.setText(_t("crates_list_header", "📁 I Tuoi Smart Crates"))
        self.txt_search_crates.setPlaceholderText(_t("crates_search_placeholder", "Cerca tra i Crates..."))
        self.btn_crate_dup.setText(_t("crates_btn_dup", "Duplica"))
        self.btn_crate_ren.setText(_t("crates_btn_ren", "Rinomina"))
        self.btn_crate_del.setText(_t("crates_btn_del", "Elimina"))
        self.lbl_preview_title.setText(_t("crates_preview_title", "🎵 Anteprima Tracce Incluse"))
        self.btn_export_m3u8.setText(_t("crates_btn_export_m3u8", "📤 Esporta M3U8 (Rekordbox / Serato / Traktor)"))
        self.btn_reset_rules.setText(_t("crates_btn_reset_rules", "✕ Ripristina Regole"))
