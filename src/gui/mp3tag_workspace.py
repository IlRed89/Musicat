"""
Dedicated Mp3tag-Style Tagging Workspace for Musicat.

Features:
- Split-View Layout (Tag Editing Panel on Left + Inline-Editable Data Grid on Right).
- Multi-selection metadata editing with '< keep >' value preservation.
- Embedded HD Cover Art management with Drag-and-Drop and cover type tagging.
- Fast inline cell editing across all metadata columns.
- Complete Mp3tag Converters:
  1. Filename -> Tag (%artist% - %title% (%bpm% BPM))
  2. Tag -> Filename (mass physical file renaming)
  3. Tag -> Tag (field duplication, swap, or merge)
  4. Text File / CSV -> Tag (bulk metadata import from CSV)
- Action Groups (Macros):
  - Case normalization (Title Case, UPPERCASE, lowercase, Sentence case)
  - Text replacement / Regex (stripping '[FREE DOWNLOAD]', promo tags)
  - 2-digit track number formatting ('01', '02', '03')
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QByteArray, QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QFont, QIcon, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.db import Database
from src.tags.editor import AudioTagEditor, CoverArt
from src.tags.patterns import PatternEngine, sanitize_filename


class CoverDropWidget(QFrame):
    """Artwork container with drag-and-drop image import and preview."""

    cover_dropped = Signal(bytes)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(180, 180)
        self.setMaximumSize(240, 240)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1d26;
                border: 2px dashed #363c54;
                border-radius: 8px;
            }
            QFrame:hover {
                border-color: #00d2ff;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)

        self.lbl_image = QLabel("Trascina qui l'immagine\no clicca per caricare")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_image.setWordWrap(True)
        self.layout.addWidget(self.lbl_image)

        self._pixmap: Optional[QPixmap] = None

    def set_cover_bytes(self, data: Optional[bytes]) -> None:
        """Renders cover art bytes into preview label."""
        if not data:
            self.lbl_image.clear()
            self.lbl_image.setText("Nessuna Copertina\nTrascina qui immagine")
            self._pixmap = None
            return

        pix = QPixmap()
        if pix.loadFromData(data):
            self._pixmap = pix
            self.lbl_image.setPixmap(
                pix.scaled(
                    self.width() - 8,
                    self.height() - 8,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.lbl_image.setText("Formato Immagine\nNon Valido")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        mime: QMimeData = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                lp = url.toLocalFile()
                if lp and Path(lp).suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    try:
                        with open(lp, "rb") as f:
                            data = f.read()
                        self.set_cover_bytes(data)
                        self.cover_dropped.emit(data)
                        event.acceptProposedAction()
                        return
                    except Exception:
                        pass
        elif mime.hasImage():
            img: QImage = mime.imageData()
            ba = QByteArray()
            img.save(ba, "PNG")
            data = bytes(ba)
            self.set_cover_bytes(data)
            self.cover_dropped.emit(data)
            event.acceptProposedAction()


class TrackNumberingWizardDialog(QDialog):
    """Interactive Track Numbering Wizard with live preview."""

    def __init__(self, tracks: List[Dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Procedura Guidata Numerazione Tracce")
        self.resize(750, 520)
        self.setMinimumSize(640, 420)
        self.tracks = tracks
        self._new_track_numbers: List[str] = []
        self._init_ui()
        self._update_preview()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        grp_opts = QGroupBox("Parametri di Rinumerazione")
        grid = QGridLayout(grp_opts)
        grid.setSpacing(8)

        grid.addWidget(QLabel("Numero traccia iniziale:"), 0, 0)
        self.spn_start = QSpinBox()
        self.spn_start.setRange(1, 9999)
        self.spn_start.setValue(1)
        self.spn_start.valueChanged.connect(self._update_preview)
        grid.addWidget(self.spn_start, 0, 1)

        self.chk_leading_zero = QCheckBox("Aggiungi zero iniziale (01, 02, ...)")
        self.chk_leading_zero.setChecked(True)
        self.chk_leading_zero.toggled.connect(self._update_preview)
        grid.addWidget(self.chk_leading_zero, 0, 2)

        self.chk_total_denominator = QCheckBox("Includi totale tracce come denominatore (es. 01/12)")
        self.chk_total_denominator.setChecked(False)
        self.chk_total_denominator.toggled.connect(self._update_preview)
        grid.addWidget(self.chk_total_denominator, 1, 0, 1, 3)

        self.chk_reset_folder = QCheckBox("Azzera contatore per ciascuna sottocartella")
        self.chk_reset_folder.setChecked(False)
        self.chk_reset_folder.toggled.connect(self._update_preview)
        grid.addWidget(self.chk_reset_folder, 2, 0, 1, 3)

        self.chk_reset_album = QCheckBox("Azzera contatore al cambio di album")
        self.chk_reset_album.setChecked(False)
        self.chk_reset_album.toggled.connect(self._update_preview)
        grid.addWidget(self.chk_reset_album, 3, 0, 1, 3)

        layout.addWidget(grp_opts)

        layout.addWidget(QLabel("<b>Anteprima Assegnazione Tracce:</b>"))

        self.tbl_preview = QTableWidget()
        self.tbl_preview.setColumnCount(5)
        self.tbl_preview.setHorizontalHeaderLabels([
            "Nome File", "Cartella", "Album", "Traccia Attuale", "Nuova Traccia"
        ])
        self.tbl_preview.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_preview.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tbl_preview, 1)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_apply = QPushButton("✓ Applica Numerazione")
        self.btn_apply.setStyleSheet("background-color: #0077b6; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_apply.clicked.connect(self.accept)
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

    def _update_preview(self) -> None:
        start_num = self.spn_start.value()
        leading_zero = self.chk_leading_zero.isChecked()
        has_denom = self.chk_total_denominator.isChecked()
        reset_folder = self.chk_reset_folder.isChecked()
        reset_album = self.chk_reset_album.isChecked()

        groups: List[Tuple[str, str]] = []
        for tr in self.tracks:
            f = str(tr.get("directory") or Path(tr.get("filepath", "")).parent or "")
            a = str(tr.get("album") or "").lower().strip()
            groups.append((f if reset_folder else "", a if reset_album else ""))

        group_totals: Dict[Tuple[str, str], int] = {}
        for g in groups:
            group_totals[g] = group_totals.get(g, 0) + 1

        self._new_track_numbers = []
        group_counters: Dict[Tuple[str, str], int] = {}

        for g in groups:
            cur_idx = group_counters.get(g, start_num)
            group_counters[g] = cur_idx + 1

            pad_fmt = f"{cur_idx:02d}" if leading_zero else str(cur_idx)
            if has_denom:
                tot = group_totals[g]
                tot_fmt = f"{tot:02d}" if leading_zero else str(tot)
                val_str = f"{pad_fmt}/{tot_fmt}"
            else:
                val_str = pad_fmt

            self._new_track_numbers.append(val_str)

        self.tbl_preview.setRowCount(len(self.tracks))
        for r, tr in enumerate(self.tracks):
            fn = tr.get("filename") or Path(tr.get("filepath", "")).name
            folder = Path(tr.get("filepath", "")).parent.name
            album = str(tr.get("album") or "")
            old_tr = str(tr.get("track_num") or "")
            new_tr = self._new_track_numbers[r]

            self.tbl_preview.setItem(r, 0, QTableWidgetItem(fn))
            self.tbl_preview.setItem(r, 1, QTableWidgetItem(folder))
            self.tbl_preview.setItem(r, 2, QTableWidgetItem(album))
            self.tbl_preview.setItem(r, 3, QTableWidgetItem(old_tr))
            item_new = QTableWidgetItem(new_tr)
            item_new.setForeground(QColor("#00e5ff"))
            self.tbl_preview.setItem(r, 4, item_new)

    def get_track_numbers(self) -> List[str]:
        return self._new_track_numbers


class FilenameToTagDialog(QDialog):
    """Filename -> Tag pattern extraction dialog with interactive live preview."""

    PRESETS = [
        "%artist% - %title%",
        "%track% - %title%",
        "%track% - %artist% - %title%",
        "%artist% - %album% - %track% - %title%",
        "%artist% - %title% (%bpm% BPM)",
        "%artist% - %title% (%year%)",
        "%artist% - %title% - %genre%",
        "%album% / %track% - %title%",
    ]

    TOKENS = [
        ("%artist%", "Artista"),
        ("%title%", "Titolo"),
        ("%album%", "Album"),
        ("%track%", "Traccia"),
        ("%year%", "Anno"),
        ("%bpm%", "BPM"),
        ("%genre%", "Genere"),
        ("%remixer%", "Remixer"),
        ("%comment%", "Commento"),
    ]

    def __init__(self, tracks: List[Dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Convertitore Nome file ➔ Tag (Mp3tag)")
        self.resize(800, 560)
        self.setMinimumSize(680, 440)
        self.tracks = tracks

        self._init_ui()
        self._update_preview()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        top_box = QVBoxLayout()
        top_box.addWidget(QLabel("<b>Maschera di formato (Pattern):</b>"))

        h_input = QHBoxLayout()
        self.txt_pattern = QLineEdit()
        self.txt_pattern.setText("%artist% - %title%")
        self.txt_pattern.textChanged.connect(self._update_preview)
        h_input.addWidget(self.txt_pattern, 1)

        self.cmb_presets = QComboBox()
        self.cmb_presets.addItem("Preset predefiniti...", "")
        for p in self.PRESETS:
            self.cmb_presets.addItem(p, p)
        self.cmb_presets.currentIndexChanged.connect(self._on_preset_selected)
        h_input.addWidget(self.cmb_presets)
        top_box.addLayout(h_input)

        h_tokens = QHBoxLayout()
        h_tokens.addWidget(QLabel("Inserisci token:"))
        for tok, tip in self.TOKENS:
            btn = QPushButton(tok)
            btn.setToolTip(f"Inserisci {tok} ({tip})")
            btn.setStyleSheet("padding: 2px 6px; font-size: 11px;")
            btn.clicked.connect(lambda _, t=tok: self._insert_token(t))
            h_tokens.addWidget(btn)
        h_tokens.addStretch()
        top_box.addLayout(h_tokens)

        layout.addLayout(top_box)

        layout.addWidget(QLabel("<b>Anteprima Estrazione Live:</b>"))
        self.tbl_preview = QTableWidget()
        self.tbl_preview.setColumnCount(7)
        self.tbl_preview.setHorizontalHeaderLabels([
            "Nome File", "Artista", "Titolo", "Album", "Traccia", "BPM", "Anno"
        ])
        self.tbl_preview.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_preview.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tbl_preview, 1)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_apply = QPushButton("✓ Applica Tag ai File")
        self.btn_apply.setStyleSheet("background-color: #0077b6; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_apply.clicked.connect(self.accept)
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

    def _insert_token(self, token: str) -> None:
        self.txt_pattern.insert(token)
        self.txt_pattern.setFocus()

    def _on_preset_selected(self, idx: int) -> None:
        val = self.cmb_presets.itemData(idx)
        if val:
            self.txt_pattern.setText(val)

    def get_pattern(self) -> str:
        return self.txt_pattern.text().strip()

    def _update_preview(self) -> None:
        pattern = self.txt_pattern.text().strip()
        self.tbl_preview.setRowCount(len(self.tracks))
        for r, tr in enumerate(self.tracks):
            fn = tr.get("filename") or Path(tr.get("filepath", "")).name
            self.tbl_preview.setItem(r, 0, QTableWidgetItem(fn))

            extracted = PatternEngine.parse_filename_to_tags(fn, pattern) if pattern else None
            fields = [
                ("artist", 1),
                ("title", 2),
                ("album", 3),
                ("track_num", 4),
                ("bpm", 5),
                ("year", 6),
            ]
            for f_key, col in fields:
                val = str(extracted.get(f_key, "")) if extracted else ""
                item = QTableWidgetItem(val)
                if val:
                    item.setForeground(QColor("#00e5ff"))
                self.tbl_preview.setItem(r, col, item)


class TagToFilenameDialog(QDialog):
    """Tag -> Filename physical file renaming dialog with interactive live preview."""

    PRESETS = [
        "%artist% - %title%",
        "$num(%track%,2) - %title%",
        "$num(%track%,2) - %artist% - %title%",
        "%artist% - %album% - $num(%track%,2) - %title%",
        "%artist% - %title% (%bpm% BPM)",
        "%artist% - %title% (%year%)",
        "%year% - %album% - $num(%track%,2) - %title%",
    ]

    TOKENS = [
        ("%artist%", "Artista"),
        ("%title%", "Titolo"),
        ("%album%", "Album"),
        ("%track%", "Traccia"),
        ("$num(%track%,2)", "Traccia a 2 cifre"),
        ("%year%", "Anno"),
        ("%bpm%", "BPM"),
        ("%genre%", "Genere"),
    ]

    def __init__(self, tracks: List[Dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Convertitore Tag ➔ Nome file (Rinomina File)")
        self.resize(820, 560)
        self.setMinimumSize(680, 440)
        self.tracks = tracks
        self._proposed_names: List[str] = []

        self._init_ui()
        self._update_preview()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        top_box = QVBoxLayout()
        top_box.addWidget(QLabel("<b>Maschera di rinomina (Pattern):</b>"))

        h_input = QHBoxLayout()
        self.txt_pattern = QLineEdit()
        self.txt_pattern.setText("%artist% - %title%")
        self.txt_pattern.textChanged.connect(self._update_preview)
        h_input.addWidget(self.txt_pattern, 1)

        self.cmb_presets = QComboBox()
        self.cmb_presets.addItem("Preset predefiniti...", "")
        for p in self.PRESETS:
            self.cmb_presets.addItem(p, p)
        self.cmb_presets.currentIndexChanged.connect(self._on_preset_selected)
        h_input.addWidget(self.cmb_presets)
        top_box.addLayout(h_input)

        h_tokens = QHBoxLayout()
        h_tokens.addWidget(QLabel("Inserisci token:"))
        for tok, tip in self.TOKENS:
            btn = QPushButton(tok)
            btn.setToolTip(f"Inserisci {tok} ({tip})")
            btn.setStyleSheet("padding: 2px 6px; font-size: 11px;")
            btn.clicked.connect(lambda _, t=tok: self._insert_token(t))
            h_tokens.addWidget(btn)
        h_tokens.addStretch()
        top_box.addLayout(h_tokens)

        layout.addLayout(top_box)

        layout.addWidget(QLabel("<b>Anteprima Rinomina File:</b>"))
        self.tbl_preview = QTableWidget()
        self.tbl_preview.setColumnCount(3)
        self.tbl_preview.setHorizontalHeaderLabels([
            "Nome File Attuale", "Nuovo Nome File Proposto", "Stato Rinomina"
        ])
        self.tbl_preview.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_preview.horizontalHeader().setStretchLastSection(True)
        self.tbl_preview.setColumnWidth(0, 300)
        self.tbl_preview.setColumnWidth(1, 340)
        layout.addWidget(self.tbl_preview, 1)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_apply = QPushButton("✓ Rinomina File su Disco")
        self.btn_apply.setStyleSheet("background-color: #0077b6; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_apply.clicked.connect(self.accept)
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

    def _insert_token(self, token: str) -> None:
        self.txt_pattern.insert(token)
        self.txt_pattern.setFocus()

    def _on_preset_selected(self, idx: int) -> None:
        val = self.cmb_presets.itemData(idx)
        if val:
            self.txt_pattern.setText(val)

    def get_pattern(self) -> str:
        return self.txt_pattern.text().strip()

    def get_proposed_names(self) -> List[str]:
        return self._proposed_names

    def _update_preview(self) -> None:
        pattern = self.txt_pattern.text().strip()
        self._proposed_names = []
        self.tbl_preview.setRowCount(len(self.tracks))

        for r, tr in enumerate(self.tracks):
            old_fp = Path(tr.get("filepath", ""))
            ext = old_fp.suffix
            old_fn = tr.get("filename") or old_fp.name

            if pattern:
                new_stem = PatternEngine.format_tags_to_filename(tr, pattern)
                clean_stem = sanitize_filename(new_stem)
                new_fn = clean_stem + ext
            else:
                new_fn = old_fn

            self._proposed_names.append(new_fn)

            self.tbl_preview.setItem(r, 0, QTableWidgetItem(old_fn))

            item_new = QTableWidgetItem(new_fn)
            if new_fn != old_fn:
                item_new.setForeground(QColor("#00e5ff"))
            self.tbl_preview.setItem(r, 1, item_new)

            status_str = "Invariato" if new_fn == old_fn else "Pronto a rinominare"
            item_status = QTableWidgetItem(status_str)
            if new_fn != old_fn:
                item_status.setForeground(QColor("#4ade80"))
            self.tbl_preview.setItem(r, 2, item_status)


class BulkPatternTagDialog(QDialog):
    """
    Advanced Mp3tag-style Bulk Pattern Tagging dialog.
    Allows extracting and setting tags across multiple tracks using custom mask patterns
    (e.g., '[%title%] - [%artist%]', '[%artist%] - [%title%]', '[%track%]. [%title%]').
    Supports placeholders: [%title%], [%artist%], [%album%], [%year%], [%genre%], [%track%].
    Includes a live Before/After comparison table with colored diff highlighting
    before writing metadata to disk via Mutagen.
    """

    PRESETS = [
        "[%artist%] - [%title%]",
        "[%title%] - [%artist%]",
        "[%track%]. [%title%]",
        "[%track%] - [%title%]",
        "[%track%] - [%artist%] - [%title%]",
        "[%artist%] - [%album%] - [%track%] - [%title%]",
        "[%artist%] - [%title%] ([%year%])",
        "[%artist%] - [%title%] - [%genre%]",
    ]

    TOKENS = [
        ("[%title%]", "Titolo"),
        ("[%artist%]", "Artista"),
        ("[%album%]", "Album"),
        ("[%year%]", "Anno"),
        ("[%genre%]", "Genere"),
        ("[%track%]", "Traccia"),
    ]

    def __init__(self, tracks: List[Dict[str, Any]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tag da Maschera / Pattern (Mp3tag Style)")
        self.resize(920, 600)
        self.setMinimumSize(740, 460)
        self.tracks = tracks
        self._computed_changes: Dict[str, Dict[str, Any]] = {}

        self._init_ui()
        self._update_preview()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        top_box = QVBoxLayout()
        top_box.setSpacing(6)
        top_box.addWidget(QLabel("<b>Maschera di formato (Pattern):</b>"))

        h_input = QHBoxLayout()
        self.txt_pattern = QLineEdit()
        self.txt_pattern.setText("[%artist%] - [%title%]")
        self.txt_pattern.setPlaceholderText("Es. [%artist%] - [%title%] oppure [%track%]. [%title%]")
        self.txt_pattern.textChanged.connect(self._update_preview)
        h_input.addWidget(self.txt_pattern, 1)

        self.cmb_presets = QComboBox()
        self.cmb_presets.addItem("Preset predefiniti...", "")
        for p in self.PRESETS:
            self.cmb_presets.addItem(p, p)
        self.cmb_presets.currentIndexChanged.connect(self._on_preset_selected)
        h_input.addWidget(self.cmb_presets)
        top_box.addLayout(h_input)

        h_tokens = QHBoxLayout()
        h_tokens.setSpacing(6)
        h_tokens.addWidget(QLabel("Segnaposto rapidi:"))
        for tok, tip in self.TOKENS:
            btn = QPushButton(tok)
            btn.setToolTip(f"Inserisci {tok} ({tip})")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #212529;
                    color: #00d2ff;
                    border: 1px solid #363c54;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #00d2ff;
                    color: #000000;
                }
            """)
            btn.clicked.connect(lambda _, t=tok: self._insert_token(t))
            h_tokens.addWidget(btn)
        h_tokens.addStretch()
        top_box.addLayout(h_tokens)

        layout.addLayout(top_box)

        layout.addWidget(QLabel("<b>Anteprima Live: Prima ➔ Dopo (Preview):</b>"))
        self.tbl_preview = QTableWidget()
        self.tbl_preview.setColumnCount(8)
        self.tbl_preview.setHorizontalHeaderLabels([
            "Nome File",
            "Titolo (Attuale ➔ Nuovo)",
            "Artista (Attuale ➔ Nuovo)",
            "Album (Attuale ➔ Nuovo)",
            "Traccia (Attuale ➔ Nuova)",
            "Anno (Attuale ➔ Nuovo)",
            "Genere (Attuale ➔ Nuovo)",
            "Stato",
        ])
        self.tbl_preview.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_preview.horizontalHeader().setStretchLastSection(True)
        self.tbl_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self.tbl_preview, 1)

        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.lbl_summary)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_apply = QPushButton("💾 Salva Metadati su Disco (Mutagen)")
        self.btn_apply.setStyleSheet("background-color: #0077b6; color: white; font-weight: bold; padding: 7px 18px; border-radius: 4px;")
        self.btn_apply.clicked.connect(self.accept)
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

    def _insert_token(self, token: str) -> None:
        self.txt_pattern.insert(token)
        self.txt_pattern.setFocus()

    def _on_preset_selected(self, idx: int) -> None:
        val = self.cmb_presets.itemData(idx)
        if val:
            self.txt_pattern.setText(val)

    def get_pattern(self) -> str:
        return self.txt_pattern.text().strip()

    def get_changes(self) -> Dict[str, Dict[str, Any]]:
        return self._computed_changes

    def _update_preview(self) -> None:
        pattern = self.txt_pattern.text().strip()
        self._computed_changes.clear()
        self.tbl_preview.setRowCount(len(self.tracks))

        matched_count = 0
        changed_count = 0

        target_fields = [
            ("title", 1),
            ("artist", 2),
            ("album", 3),
            ("track_num", 4),
            ("year", 5),
            ("genre", 6),
        ]

        for r, tr in enumerate(self.tracks):
            fp = tr.get("filepath", "")
            fn = tr.get("filename") or Path(fp).name
            self.tbl_preview.setItem(r, 0, QTableWidgetItem(fn))

            extracted = None
            if pattern:
                extracted = PatternEngine.parse_filename_to_tags(fn, pattern)
                if extracted is None and "[%" in pattern:
                    norm_pattern = re.sub(r"\[%([a-zA-Z0-9_\s]+)%\]", r"%\1%", pattern)
                    extracted = PatternEngine.parse_filename_to_tags(fn, norm_pattern)
            row_changes: Dict[str, Any] = {}

            if extracted is not None:
                matched_count += 1
                for f_key, col_idx in target_fields:
                    curr_val = tr.get(f_key)
                    curr_str = str(curr_val) if curr_val is not None else ""

                    if f_key in extracted and extracted[f_key] is not None:
                        new_val = extracted[f_key]
                        new_str = str(new_val)

                        if new_str != curr_str:
                            display_text = f"{curr_str or '—'} ➔ {new_str}"
                            item = QTableWidgetItem(display_text)
                            item.setForeground(QColor("#00e5ff"))
                            item.setFont(QFont("", -1, QFont.Weight.Bold))
                            self.tbl_preview.setItem(r, col_idx, item)
                            row_changes[f_key] = new_val
                        else:
                            item = QTableWidgetItem(curr_str)
                            item.setForeground(QColor("#6c757d"))
                            self.tbl_preview.setItem(r, col_idx, item)
                    else:
                        item = QTableWidgetItem(curr_str)
                        item.setForeground(QColor("#6c757d"))
                        self.tbl_preview.setItem(r, col_idx, item)

                if row_changes:
                    changed_count += 1
                    self._computed_changes[fp] = row_changes
                    item_st = QTableWidgetItem(f"✓ {len(row_changes)} campo/i modificato/i")
                    item_st.setForeground(QColor("#10b981"))
                    item_st.setFont(QFont("", -1, QFont.Weight.Bold))
                    self.tbl_preview.setItem(r, 7, item_st)
                else:
                    item_st = QTableWidgetItem("✓ Identico (Nessuna modifica)")
                    item_st.setForeground(QColor("#6c757d"))
                    self.tbl_preview.setItem(r, 7, item_st)

            else:
                for f_key, col_idx in target_fields:
                    curr_val = tr.get(f_key)
                    curr_str = str(curr_val) if curr_val is not None else ""
                    item = QTableWidgetItem(curr_str)
                    item.setForeground(QColor("#6c757d"))
                    self.tbl_preview.setItem(r, col_idx, item)

                item_st = QTableWidgetItem("— Nessun match")
                item_st.setForeground(QColor("#f59e0b"))
                self.tbl_preview.setItem(r, 7, item_st)

        self.lbl_summary.setText(
            f"Tracce selezionate: <b>{len(self.tracks)}</b> | "
            f"Corrispondenze pattern: <b>{matched_count}</b> | "
            f"Tracce con modifiche pronte al salvataggio: <b style='color: #10b981;'>{changed_count}</b>"
        )


class Mp3tagWorkspaceWindow(QMainWindow):
    """Full-featured Mp3tag-grade Tagging Workbench for Musicat."""

    tags_updated = Signal()
    workspace_saved = tags_updated
    close_requested = Signal()

    KEEP_VALUE = "< keep >"

    COLUMNS = [
        ("filename", "Nome File"),
        ("title", "Titolo"),
        ("artist", "Artista"),
        ("album", "Album"),
        ("track_num", "Traccia"),
        ("year", "Anno"),
        ("genre", "Genere"),
        ("bpm", "BPM"),
        ("camelot_key", "Key"),
        ("label", "Etichetta"),
        ("remixer", "Remixer"),
        ("comment", "Commento"),
        ("directory", "Cartella"),
    ]

    def __init__(
        self,
        arg1: Union[Database, List[Dict[str, Any]]],
        arg2: Optional[Union[Database, List[Dict[str, Any]]]] = None,
        parent: Optional[QWidget] = None,
        tracks: Optional[List[Dict[str, Any]]] = None,
        db: Optional[Database] = None,
    ) -> None:
        super().__init__(parent)
        active_db = db
        active_tracks = tracks

        if isinstance(arg1, Database):
            active_db = active_db or arg1
            if isinstance(arg2, list):
                active_tracks = active_tracks or arg2
        elif isinstance(arg1, list):
            active_tracks = active_tracks or arg1
            if isinstance(arg2, Database):
                active_db = active_db or arg2

        self.db = active_db or Database()
        self.tracks = [dict(t) for t in (active_tracks or [])]
        self.dirty_files: Set[str] = set()

        self.pending_cover_bytes: Optional[bytes] = None
        self.pending_cover_remove: bool = False

        self.setWindowTitle("Musicat — Dedicated Mp3tag Tagging Workspace")
        self.resize(1280, 780)
        self.setMinimumSize(960, 600)

        self._init_menu_and_toolbar()
        self._init_ui()
        self._populate_grid()

    def _init_menu_and_toolbar(self) -> None:
        """Sets up Mp3tag-style Menus and Toolbars."""
        menubar = self.menuBar()

        # 1. File Menu
        menu_file = menubar.addMenu("&File")
        act_save = menu_file.addAction("💾 Salva Modifiche")
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._on_save_all)

        menu_file.addSeparator()
        act_close = menu_file.addAction("Chiudi Workspace")
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(self._on_close_workspace)

        # 2. Convert Menu (Mp3tag Core)
        menu_conv = menubar.addMenu("&Convertitore")
        act_bulk_pattern = menu_conv.addAction("🏷️ Tag da Pattern (Maschera)...")
        act_bulk_pattern.setShortcuts([QKeySequence("Ctrl+Shift+P"), QKeySequence("Alt+F")])
        act_bulk_pattern.triggered.connect(self._on_bulk_pattern_tagging)

        act_fn_tag = menu_conv.addAction("📝 Nome file ➔ Tag...")
        act_fn_tag.setShortcut(QKeySequence("Alt+1"))
        act_fn_tag.triggered.connect(self._on_conv_filename_to_tag)

        act_tag_fn = menu_conv.addAction("🏷️ Tag ➔ Nome file...")
        act_tag_fn.setShortcut(QKeySequence("Alt+2"))
        act_tag_fn.triggered.connect(self._on_conv_tag_to_filename)

        act_tag_tag = menu_conv.addAction("🔄 Tag ➔ Tag...")
        act_tag_tag.setShortcut(QKeySequence("Alt+5"))
        act_tag_tag.triggered.connect(self._on_conv_tag_to_tag)

        act_csv_tag = menu_conv.addAction("📄 File di testo / CSV ➔ Tag...")
        act_csv_tag.setShortcut(QKeySequence("Alt+4"))
        act_csv_tag.triggered.connect(self._on_conv_csv_to_tag)

        # 3. Actions / Macros Menu
        menu_actions = menubar.addMenu("&Azioni (Macro)")
        act_wizard = menu_actions.addAction("🔢 Procedura Guidata Numerazione Tracce...")
        act_wizard.triggered.connect(self._on_wizard_track_numbering)

        menu_actions.addSeparator()
        act_case_title = menu_actions.addAction("🔤 Normalizza Titoli: Formato Titolo (Title Case)")
        act_case_title.triggered.connect(lambda: self._apply_case_action("title"))

        act_case_upper = menu_actions.addAction("🔠 Tutto in MAIUSCOLO (UPPERCASE)")
        act_case_upper.triggered.connect(lambda: self._apply_case_action("upper"))

        act_case_lower = menu_actions.addAction("🔡 Tutto in minuscolo (lowercase)")
        act_case_lower.triggered.connect(lambda: self._apply_case_action("lower"))

        menu_actions.addSeparator()
        act_strip_promo = menu_actions.addAction("🧹 Rimuovi suffissi promo ([FREE DOWNLOAD], [Extended Mix], ecc.)")
        act_strip_promo.triggered.connect(self._apply_strip_promo_tags)

        act_pad_tracks = menu_actions.addAction("🔢 Formatta Numeri Traccia a 2 Cifre (01, 02, ...)")
        act_pad_tracks.triggered.connect(self._apply_pad_track_numbers)

        act_regex = menu_actions.addAction("⚡ Sostituzione Testo / Regex...")
        act_regex.triggered.connect(self._on_regex_replace)

        # Quick Toolbar
        toolbar = QToolBar("Mp3tag Toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(act_save)
        toolbar.addSeparator()
        toolbar.addAction(act_bulk_pattern)
        toolbar.addAction(act_fn_tag)
        toolbar.addAction(act_tag_fn)
        toolbar.addAction(act_tag_tag)
        toolbar.addAction(act_csv_tag)
        toolbar.addSeparator()
        toolbar.addAction(act_wizard)
        toolbar.addSeparator()
        toolbar.addAction(act_strip_promo)
        toolbar.addAction(act_pad_tracks)
        self.addToolBar(toolbar)

    def _on_close_workspace(self) -> None:
        """Emits close_requested and closes window if displayed standalone."""
        self.close_requested.emit()
        if self.isWindow():
            self.close()

    def load_tracks(self, tracks: Optional[List[Dict[str, Any]]] = None) -> None:
        """Updates workspace with tracks and refreshes grid display."""
        if tracks is not None:
            self.tracks = [dict(t) for t in tracks]
        self.dirty_files.clear()
        self.pending_cover_bytes = None
        self.pending_cover_remove = False
        self._populate_grid()

    def _init_ui(self) -> None:
        """Builds Split-View interface: Left Tag Panel, Right Track Grid."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # 1. Left Tag Panel
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        form = QFormLayout(scroll_content)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self.txt_title = QLineEdit()
        self.txt_artist = QLineEdit()
        self.txt_album = QLineEdit()
        self.txt_album_artist = QLineEdit()
        self.txt_track = QLineEdit()
        self.txt_year = QLineEdit()
        self.txt_genre = QLineEdit()
        self.txt_comment = QLineEdit()
        self.txt_label = QLineEdit()
        self.txt_remixer = QLineEdit()
        self.txt_bpm = QLineEdit()
        self.txt_key = QLineEdit()

        form.addRow("Titolo:", self.txt_title)
        form.addRow("Artista:", self.txt_artist)
        form.addRow("Album:", self.txt_album)
        form.addRow("Artista Album:", self.txt_album_artist)
        form.addRow("Traccia:", self.txt_track)
        form.addRow("Anno:", self.txt_year)
        form.addRow("Genere:", self.txt_genre)
        form.addRow("Commento:", self.txt_comment)
        form.addRow("Etichetta (Label):", self.txt_label)
        form.addRow("Remixer:", self.txt_remixer)
        form.addRow("BPM:", self.txt_bpm)
        form.addRow("Chiave (Key):", self.txt_key)

        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        # Artwork Panel
        grp_cover = QGroupBox("🖼️ Gestione Copertina")
        cov_layout = QVBoxLayout(grp_cover)
        cov_layout.setSpacing(6)

        self.drop_cover = CoverDropWidget()
        self.drop_cover.cover_dropped.connect(self._on_cover_dropped)
        cov_layout.addWidget(self.drop_cover, alignment=Qt.AlignmentFlag.AlignCenter)

        self.cmb_cover_type = QComboBox()
        self.cmb_cover_type.addItems(["Front Cover", "Back Cover", "Media (CD / Vinyl Label)"])
        cov_layout.addWidget(self.cmb_cover_type)

        btn_box = QHBoxLayout()
        btn_load_cover = QPushButton("Sfoglia...")
        btn_load_cover.clicked.connect(self._on_browse_cover)
        btn_remove_cover = QPushButton("Rimuovi")
        btn_remove_cover.clicked.connect(self._on_remove_cover)
        btn_box.addWidget(btn_load_cover)
        btn_box.addWidget(btn_remove_cover)
        cov_layout.addLayout(btn_box)

        left_layout.addWidget(grp_cover)

        btn_apply_panel = QPushButton("💾 Salva Modifiche Pannello")
        btn_apply_panel.setStyleSheet("background-color: #0077b6; font-weight: bold; padding: 8px;")
        btn_apply_panel.clicked.connect(self._on_apply_left_panel)
        left_layout.addWidget(btn_apply_panel)

        grp_quick = QGroupBox("⚡ Azioni Rapide")
        quick_layout = QVBoxLayout(grp_quick)
        quick_layout.setSpacing(5)

        btn_renum = QPushButton("🔢 Rinumera Tracce...")
        btn_renum.setToolTip("Procedura Guidata Numerazione Tracce")
        btn_renum.clicked.connect(self._on_wizard_track_numbering)
        quick_layout.addWidget(btn_renum)

        btn_bulk_pattern = QPushButton("🏷️ Tag da Pattern (Ctrl+Shift+P)...")
        btn_bulk_pattern.setToolTip("Editor Massivo Tag da Maschera / Pattern (Ctrl+Shift+P / Alt+F)")
        btn_bulk_pattern.setStyleSheet("background-color: #0d6efd; color: #ffffff; font-weight: bold; padding: 6px; border-radius: 4px;")
        btn_bulk_pattern.clicked.connect(self._on_bulk_pattern_tagging)
        quick_layout.addWidget(btn_bulk_pattern)

        left_layout.addWidget(grp_quick)

        left_widget.setMinimumWidth(280)
        left_widget.setMaximumWidth(380)
        splitter.addWidget(left_widget)

        # 2. Right Track Grid
        self.grid = QTableWidget()
        self.grid.setColumnCount(len(self.COLUMNS))
        self.grid.setHorizontalHeaderLabels([name for _, name in self.COLUMNS])
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.grid.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.grid.verticalHeader().setDefaultSectionSize(26)
        self.grid.horizontalHeader().setStretchLastSection(True)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.grid.itemSelectionChanged.connect(self._on_grid_selection_changed)
        self.grid.cellChanged.connect(self._on_cell_changed)

        splitter.addWidget(self.grid)
        splitter.setStretchFactor(1, 4)

    def _populate_grid(self) -> None:
        """Fills the grid with track data."""
        self.grid.blockSignals(True)
        self.grid.setRowCount(len(self.tracks))

        for row, tr in enumerate(self.tracks):
            for col, (field, _) in enumerate(self.COLUMNS):
                val = tr.get(field, "")
                if val is None:
                    val = ""
                item = QTableWidgetItem(str(val))
                # Filename and directory editable only through converter
                if field in ("filename", "directory"):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(row, col, item)

        self.grid.blockSignals(False)
        if self.tracks:
            self.grid.selectRow(0)

    # -------------------------------------------------------------
    # Selection and Left Panel Sync
    # -------------------------------------------------------------
    def _get_selected_tracks_data(self) -> List[Tuple[int, Dict[str, Any]]]:
        """Returns list of (row_idx, track_dict) for selected rows."""
        selected_rows = sorted(list(set(item.row() for item in self.grid.selectedItems())))
        return [(r, self.tracks[r]) for r in selected_rows if r < len(self.tracks)]

    def _on_grid_selection_changed(self) -> None:
        """Populates left panel with single track or '< keep >' for multi-selection."""
        selected = self._get_selected_tracks_data()
        if not selected:
            self._clear_left_panel()
            return

        if len(selected) == 1:
            _, tr = selected[0]
            self.txt_title.setText(str(tr.get("title") or ""))
            self.txt_artist.setText(str(tr.get("artist") or ""))
            self.txt_album.setText(str(tr.get("album") or ""))
            self.txt_album_artist.setText(str(tr.get("album_artist") or ""))
            self.txt_track.setText(str(tr.get("track_num") or ""))
            self.txt_year.setText(str(tr.get("year") or ""))
            self.txt_genre.setText(str(tr.get("genre") or ""))
            self.txt_comment.setText(str(tr.get("comment") or ""))
            self.txt_label.setText(str(tr.get("label") or ""))
            self.txt_remixer.setText(str(tr.get("remixer") or ""))
            self.txt_bpm.setText(f"{tr.get('bpm', ''):.1f}" if tr.get("bpm") else "")
            self.txt_key.setText(str(tr.get("camelot_key") or tr.get("musical_key") or ""))

            # Load artwork
            fp = tr.get("filepath", "")
            if fp:
                try:
                    cover = AudioTagEditor.extract_cover(fp)
                    self.drop_cover.set_cover_bytes(cover.data if cover else None)
                except Exception:
                    self.drop_cover.set_cover_bytes(None)
        else:
            # Multi-selection: evaluate fields with < keep >
            fields = [
                ("title", self.txt_title),
                ("artist", self.txt_artist),
                ("album", self.txt_album),
                ("album_artist", self.txt_album_artist),
                ("track_num", self.txt_track),
                ("year", self.txt_year),
                ("genre", self.txt_genre),
                ("comment", self.txt_comment),
                ("label", self.txt_label),
                ("remixer", self.txt_remixer),
                ("bpm", self.txt_bpm),
                ("camelot_key", self.txt_key),
            ]

            for field_key, widget in fields:
                distinct_vals = set(str(tr.get(field_key) or "") for _, tr in selected)
                if len(distinct_vals) == 1:
                    widget.setText(list(distinct_vals)[0])
                else:
                    widget.setText(self.KEEP_VALUE)

            self.drop_cover.set_cover_bytes(None)

    def _clear_left_panel(self) -> None:
        """Empties all left form widgets."""
        for w in [
            self.txt_title, self.txt_artist, self.txt_album, self.txt_album_artist,
            self.txt_track, self.txt_year, self.txt_genre, self.txt_comment,
            self.txt_label, self.txt_remixer, self.txt_bpm, self.txt_key
        ]:
            w.clear()
        self.drop_cover.set_cover_bytes(None)

    def _on_cell_changed(self, row: int, col: int) -> None:
        """Handles fast inline grid cell editing."""
        if row >= len(self.tracks):
            return

        field_key, _ = self.COLUMNS[col]
        new_val = self.grid.item(row, col).text().strip()

        # Update in-memory track dict
        old_val = str(self.tracks[row].get(field_key) or "")
        if new_val != old_val:
            if field_key in ("year", "track_num"):
                try:
                    self.tracks[row][field_key] = int(new_val) if new_val else None
                except ValueError:
                    self.tracks[row][field_key] = None
            elif field_key == "bpm":
                try:
                    self.tracks[row][field_key] = float(new_val) if new_val else None
                except ValueError:
                    self.tracks[row][field_key] = None
            else:
                self.tracks[row][field_key] = new_val

            self.dirty_files.add(self.tracks[row]["filepath"])
            self.grid.item(row, col).setForeground(QColor("#00e5ff"))

    def _on_apply_left_panel(self) -> None:
        """Applies values from left panel across selected rows."""
        selected = self._get_selected_tracks_data()
        if not selected:
            return

        panel_values = {
            "title": self.txt_title.text().strip(),
            "artist": self.txt_artist.text().strip(),
            "album": self.txt_album.text().strip(),
            "album_artist": self.txt_album_artist.text().strip(),
            "track_num": self.txt_track.text().strip(),
            "year": self.txt_year.text().strip(),
            "genre": self.txt_genre.text().strip(),
            "comment": self.txt_comment.text().strip(),
            "label": self.txt_label.text().strip(),
            "remixer": self.txt_remixer.text().strip(),
            "bpm": self.txt_bpm.text().strip(),
            "camelot_key": self.txt_key.text().strip(),
        }

        self.grid.blockSignals(True)
        for row_idx, tr in selected:
            fp = tr["filepath"]
            self.dirty_files.add(fp)

            for col_idx, (field, _) in enumerate(self.COLUMNS):
                if field in panel_values:
                    val = panel_values[field]
                    if val != self.KEEP_VALUE:
                        # Set in track dictionary
                        if field in ("year", "track_num"):
                            try:
                                tr[field] = int(val) if val else None
                            except ValueError:
                                tr[field] = None
                        elif field == "bpm":
                            try:
                                tr[field] = float(val) if val else None
                            except ValueError:
                                tr[field] = None
                        else:
                            tr[field] = val

                        # Update grid item
                        item = self.grid.item(row_idx, col_idx)
                        if item:
                            item.setText(val)
                            item.setForeground(QColor("#00e5ff"))

        self.grid.blockSignals(False)

        # Handle Cover Art update
        if self.pending_cover_bytes or self.pending_cover_remove:
            for _, tr in selected:
                fp = tr["filepath"]
                try:
                    if self.pending_cover_remove:
                        AudioTagEditor.remove_cover(fp)
                    elif self.pending_cover_bytes:
                        AudioTagEditor.set_cover(fp, self.pending_cover_bytes)
                except Exception:
                    pass

        self._on_save_all()

    def _on_cover_dropped(self, data: bytes) -> None:
        self.pending_cover_bytes = data
        self.pending_cover_remove = False

    def _on_browse_cover(self) -> None:
        fp, _ = QFileDialog.getOpenFileName(self, "Seleziona Copertina", "", "Immagini (*.jpg *.jpeg *.png *.webp)")
        if fp:
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                self.drop_cover.set_cover_bytes(data)
                self.pending_cover_bytes = data
                self.pending_cover_remove = False
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile leggere l'immagine:\n{e}")

    def _on_remove_cover(self) -> None:
        self.drop_cover.set_cover_bytes(None)
        self.pending_cover_bytes = None
        self.pending_cover_remove = True

    # -------------------------------------------------------------
    # Mp3tag Converters (Filename->Tag, Tag->Filename, Tag->Tag, CSV->Tag, Numbering Wizard)
    # -------------------------------------------------------------
    def _on_wizard_track_numbering(self) -> None:
        """Track Numbering Wizard with interactive live preview."""
        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        if not selected:
            QMessageBox.information(self, "Nessuna traccia", "Nessuna traccia caricata da rinumerare.")
            return

        tracks_subset = [tr for _, tr in selected]
        dlg = TrackNumberingWizardDialog(tracks_subset, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_numbers = dlg.get_track_numbers()
        self.grid.blockSignals(True)
        for idx, (row_idx, tr) in enumerate(selected):
            if idx < len(new_numbers):
                new_num = new_numbers[idx]
                tr["track_num"] = new_num
                self.dirty_files.add(tr["filepath"])
                for col_idx, (col_id, _) in enumerate(self.COLUMNS):
                    if col_id == "track_num":
                        item = self.grid.item(row_idx, col_idx)
                        if item:
                            item.setText(str(new_num))
                            item.setForeground(QColor("#00e5ff"))

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()
        QMessageBox.information(self, "Completato", f"Rinumerate {len(selected)} tracce.")

    def _on_bulk_pattern_tagging(self) -> None:
        """Mp3tag Bulk Pattern Tagging with live preview and direct Mutagen disk write."""
        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        if not selected:
            QMessageBox.information(self, "Nessuna traccia", "Nessuna traccia caricata nel workspace.")
            return

        tracks_subset = [tr for _, tr in selected]
        dlg = BulkPatternTagDialog(tracks_subset, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        changes_by_fp = dlg.get_changes()
        if not changes_by_fp:
            QMessageBox.information(self, "Nessuna modifica", "Nessun metadato modificato rispetto ai file correnti.")
            return

        self.grid.blockSignals(True)
        saved_count = 0

        for row_idx, tr in selected:
            fp = tr.get("filepath", "")
            if fp in changes_by_fp:
                updates = changes_by_fp[fp]
                for k, v in updates.items():
                    tr[k] = v

                # 1. Direct Mutagen write to disk
                try:
                    AudioTagEditor.write_metadata(fp, updates)
                except Exception as exc:
                    MusicatLogger.warning("BULK_PATTERN", f"Errore scrittura tag per {fp}: {exc}")

                # 2. Synchronize with SQLite database
                try:
                    self.db.update_track_tags(fp, updates)
                    saved_count += 1
                except Exception as exc:
                    MusicatLogger.warning("BULK_PATTERN", f"Errore update DB per {fp}: {exc}")

                # 3. Update workspace grid cells
                for col_idx, (col_id, _) in enumerate(self.COLUMNS):
                    if col_id in updates:
                        item = self.grid.item(row_idx, col_idx)
                        if item:
                            item.setText(str(updates[col_id] if updates[col_id] is not None else ""))
                            item.setForeground(QColor("#10b981"))

                # Clear from dirty_files since already saved to disk
                self.dirty_files.discard(fp)

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()
        self.tags_updated.emit()
        self.statusBar().showMessage(f"💾 Salvati su disco con successo {saved_count} file.", 5000)
        QMessageBox.information(
            self,
            "Operazione Completata",
            f"Salvati su disco e aggiornati nel database con successo i metadati di {saved_count} file."
        )

    def _on_conv_filename_to_tag(self, pattern: Optional[str] = None) -> None:
        """Mp3tag Converter 1: Filename -> Tag with interactive live preview."""
        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        if not selected:
            QMessageBox.information(self, "Nessuna traccia", "Nessuna traccia caricata nel workspace.")
            return

        if pattern is None:
            tracks_subset = [tr for _, tr in selected]
            dlg = FilenameToTagDialog(tracks_subset, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            pattern = dlg.get_pattern()

        if not pattern:
            return

        self.grid.blockSignals(True)
        count = 0
        for row_idx, tr in selected:
            fn = tr.get("filename", "")
            extracted = PatternEngine.parse_filename_to_tags(fn, pattern)
            if extracted:
                for k, v in extracted.items():
                    tr[k] = v
                    self.dirty_files.add(tr["filepath"])
                    # Update grid
                    for col_idx, (c_field, _) in enumerate(self.COLUMNS):
                        if c_field == k:
                            item = self.grid.item(row_idx, col_idx)
                            if item:
                                item.setText(str(v or ""))
                                item.setForeground(QColor("#00e5ff"))
                count += 1

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()
        QMessageBox.information(self, "Completato", f"Metadati estratti da {count} nomi di file.")

    def _on_conv_tag_to_filename(self, pattern: Optional[str] = None) -> None:
        """Mp3tag Converter 2: Tag -> Filename with live preview and physical renaming."""
        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        if not selected:
            QMessageBox.information(self, "Nessuna traccia", "Nessuna traccia caricata nel workspace.")
            return

        if pattern is None:
            tracks_subset = [tr for _, tr in selected]
            dlg = TagToFilenameDialog(tracks_subset, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            pattern = dlg.get_pattern()

        if not pattern:
            return

        renamed = 0
        for row_idx, tr in selected:
            old_fp = Path(tr["filepath"])
            ext = old_fp.suffix
            new_stem = PatternEngine.format_tags_to_filename(tr, pattern)
            clean_name = sanitize_filename(new_stem) + ext
            new_fp = old_fp.parent / clean_name

            if old_fp != new_fp and not new_fp.exists():
                try:
                    old_fp.rename(new_fp)
                    tr["filepath"] = str(new_fp)
                    tr["filename"] = clean_name
                    # Update DB immediately
                    self.db.update_track_tags(str(old_fp), {"filepath": str(new_fp), "filename": clean_name})
                    # Update grid
                    self.grid.item(row_idx, 0).setText(clean_name)
                    renamed += 1
                except Exception:
                    pass

        QMessageBox.information(self, "Completato", f"Rinominati fisicamente {renamed} file su disco.")

    def _on_conv_tag_to_tag(self) -> None:
        """Mp3tag Converter 3: Tag -> Tag manipulation."""
        fields = ["artist", "title", "album", "genre", "comment", "label", "remixer", "camelot_key"]
        src_field, ok1 = QInputDialog.getItem(self, "Tag ➔ Tag", "Campo Sorgente:", fields, 0, False)
        if not ok1:
            return
        dst_field, ok2 = QInputDialog.getItem(self, "Tag ➔ Tag", f"Copia '{src_field}' nel Campo Destinazione:", fields, 1, False)
        if not ok2 or src_field == dst_field:
            return

        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        self.grid.blockSignals(True)
        for row_idx, tr in selected:
            val = tr.get(src_field)
            tr[dst_field] = val
            self.dirty_files.add(tr["filepath"])

            for col_idx, (col_id, _) in enumerate(self.COLUMNS):
                if col_id == dst_field:
                    item = self.grid.item(row_idx, col_idx)
                    if item:
                        item.setText(str(val or ""))
                        item.setForeground(QColor("#00e5ff"))

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()

    def _on_conv_csv_to_tag(self) -> None:
        """Mp3tag Converter 4: Text file / CSV -> Tag."""
        csv_path, _ = QFileDialog.getOpenFileName(self, "Seleziona File CSV / Testo", "", "CSV / Testo (*.csv *.tsv *.txt)")
        if not csv_path:
            return

        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        try:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                QMessageBox.warning(self, "CSV Vuoto", "Nessun dato trovato nel file CSV.")
                return

            self.grid.blockSignals(True)
            matched = 0
            for idx, (row_idx, tr) in enumerate(selected):
                if idx >= len(rows):
                    break
                csv_row = rows[idx]
                for k, v in csv_row.items():
                    k_clean = k.lower().strip()
                    if k_clean in tr:
                        tr[k_clean] = v
                        self.dirty_files.add(tr["filepath"])
                        for col_idx, (col_id, _) in enumerate(self.COLUMNS):
                            if col_id == k_clean:
                                item = self.grid.item(row_idx, col_idx)
                                if item:
                                    item.setText(str(v or ""))
                                    item.setForeground(QColor("#00e5ff"))
                matched += 1

            self.grid.blockSignals(False)
            self._on_grid_selection_changed()
            QMessageBox.information(self, "Completato", f"Importati metadati da CSV per {matched} brani.")

        except Exception as e:
            QMessageBox.critical(self, "Errore CSV", f"Impossibile leggere il file CSV:\n{e}")

    # -------------------------------------------------------------
    # Action Groups / Macros
    # -------------------------------------------------------------
    def _apply_case_action(self, mode: str) -> None:
        """Applies Title Case, UPPERCASE, or lowercase to selected tracks."""
        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        self.grid.blockSignals(True)
        text_fields = ["title", "artist", "album", "genre", "remixer"]

        for row_idx, tr in selected:
            self.dirty_files.add(tr["filepath"])
            for field in text_fields:
                old_val = str(tr.get(field) or "")
                if old_val:
                    if mode == "title":
                        new_val = old_val.title()
                    elif mode == "upper":
                        new_val = old_val.upper()
                    elif mode == "lower":
                        new_val = old_val.lower()
                    else:
                        new_val = old_val

                    tr[field] = new_val
                    for col_idx, (c_id, _) in enumerate(self.COLUMNS):
                        if c_id == field:
                            item = self.grid.item(row_idx, col_idx)
                            if item:
                                item.setText(new_val)
                                item.setForeground(QColor("#00e5ff"))

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()

    def _apply_strip_promo_tags(self) -> None:
        """Removes common DJ promotional tags from titles."""
        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        patterns = [
            r"\[FREE DOWNLOAD\]",
            r"\[FREE DL\]",
            r"\[OUT NOW\]",
            r"\(FREE DOWNLOAD\)",
            r"\[HYPEDDIT\]",
            r"\(Official Audio\)",
            r"\(Official Music Video\)",
            r"\[Exclusive\]",
        ]

        self.grid.blockSignals(True)
        cleaned = 0

        for row_idx, tr in selected:
            title = str(tr.get("title") or "")
            new_title = title
            for pat in patterns:
                new_title = re.sub(pat, "", new_title, flags=re.IGNORECASE)

            new_title = re.sub(r"\s+", " ", new_title).strip()
            if new_title != title:
                tr["title"] = new_title
                self.dirty_files.add(tr["filepath"])
                for col_idx, (c_id, _) in enumerate(self.COLUMNS):
                    if c_id == "title":
                        item = self.grid.item(row_idx, col_idx)
                        if item:
                            item.setText(new_title)
                            item.setForeground(QColor("#00e5ff"))
                cleaned += 1

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()
        QMessageBox.information(self, "Completato", f"Puliti {cleaned} titoli da tag promozionali.")

    def _apply_pad_track_numbers(self) -> None:
        """Formats track numbers to 2 digits (01, 02, etc.)."""
        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        self.grid.blockSignals(True)
        for row_idx, tr in selected:
            tn = tr.get("track_num")
            if tn is not None:
                try:
                    val = int(tn)
                    pad_str = f"{val:02d}"
                    tr["track_num"] = pad_str
                    self.dirty_files.add(tr["filepath"])
                    for col_idx, (c_id, _) in enumerate(self.COLUMNS):
                        if c_id == "track_num":
                            item = self.grid.item(row_idx, col_idx)
                            if item:
                                item.setText(pad_str)
                                item.setForeground(QColor("#00e5ff"))
                except ValueError:
                    pass

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()

    def _on_regex_replace(self) -> None:
        """Custom regex search and replace dialog."""
        pattern, ok1 = QInputDialog.getText(self, "Sostituzione Regex", "Cerca (Espressione Regolare / Testo):")
        if not ok1 or not pattern:
            return
        replacement, ok2 = QInputDialog.getText(self, "Sostituzione Regex", f"Sostituisci '{pattern}' con:")
        if not ok2:
            return

        selected = self._get_selected_tracks_data()
        if not selected:
            selected = list(enumerate(self.tracks))

        self.grid.blockSignals(True)
        for row_idx, tr in selected:
            for field in ["title", "artist", "album", "genre"]:
                val = str(tr.get(field) or "")
                new_val = re.sub(pattern, replacement, val)
                if new_val != val:
                    tr[field] = new_val
                    self.dirty_files.add(tr["filepath"])
                    for col_idx, (c_id, _) in enumerate(self.COLUMNS):
                        if c_id == field:
                            item = self.grid.item(row_idx, col_idx)
                            if item:
                                item.setText(new_val)
                                item.setForeground(QColor("#00e5ff"))

        self.grid.blockSignals(False)
        self._on_grid_selection_changed()

    # -------------------------------------------------------------
    # Save & Commit to Disk and SQLite
    # -------------------------------------------------------------
    def _on_save_all(self) -> None:
        """Writes dirty tracks to physical audio file tags and SQLite DB."""
        if not self.dirty_files:
            return

        saved_count = 0
        for tr in self.tracks:
            fp = tr.get("filepath", "")
            if fp in self.dirty_files:
                updates = {
                    "title": tr.get("title"),
                    "artist": tr.get("artist"),
                    "album": tr.get("album"),
                    "album_artist": tr.get("album_artist"),
                    "track_num": tr.get("track_num"),
                    "year": tr.get("year"),
                    "genre": tr.get("genre"),
                    "comment": tr.get("comment"),
                    "label": tr.get("label"),
                    "remixer": tr.get("remixer"),
                    "bpm": tr.get("bpm"),
                    "camelot_key": tr.get("camelot_key"),
                }

                # 1. Physical Tag Write
                try:
                    AudioTagEditor.write_metadata(fp, updates)
                except Exception:
                    pass

                # 2. SQLite Update
                try:
                    self.db.update_track_tags(fp, updates)
                    saved_count += 1
                except Exception:
                    pass

        self.dirty_files.clear()
        # Reset grid text colors
        for r in range(self.grid.rowCount()):
            for c in range(self.grid.columnCount()):
                item = self.grid.item(r, c)
                if item:
                    item.setForeground(QColor("#e0e2ec"))

        self.tags_updated.emit()
        self.statusBar().showMessage(f"💾 Salvati con successo {saved_count} file.", 4000)
