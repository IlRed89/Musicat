"""
Live DJ Filter Bar, Camelot Wheel Assistant & Smart Crate Builder for Musicat.

High-performance UI component (<15ms query response) designed for live DJ console use.
Provides multi-genre OR selection, BPM range with Target BPM +- % presets,
harmonic Camelot Wheel matching, Decade/Year filtering, Energy level/Stars,
instant ESC reset, and dynamic Smart Crate management with M3U8 export.
"""

import sys
from typing import Any, Callable, Dict, List, Optional, Set
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..audio.camelot import (
    CamelotWheel,
    CAMELOT_KEYS_ORDERED,
    CAMELOT_TO_KEY,
    KEY_TO_CAMELOT,
)
from ..core.db import Database
from ..core.filter_engine import FilterCriteria, LiveFilterEngine
from ..core.search_factory import SearchEngine
from ..core.logger import MusicatLogger
from ..core.i18n import I18n, _t


COMMON_DJ_GENRES = [
    "Tech House", "Melodic Techno", "Afro House", "Deep House",
    "House", "Techno", "Peak Time Techno", "Progressive House",
    "Minimal / Deep Tech", "Nu Disco / Disco", "Drum & Bass",
    "Trance", "Psy-Trance", "Indie Dance", "Hard Techno",
    "Electro House", "Bass House", "Organic House / Downtempo",
    "Dance / Pop", "UK Garage", "Acapella",
]


class CamelotWheelDialog(QDialog):
    """Interactive visual Camelot Wheel assistant for harmonic mixing."""

    key_selected = Signal(str, bool)  # key, harmonic_matches_only

    def __init__(self, current_key: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🎡 Camelot Wheel Harmonic Mixing Assistant")
        self.resize(780, 480)
        self.setStyleSheet("""
            QDialog { background-color: #13151b; }
            QLabel { color: #e2e4ed; }
        """)
        self.selected_key = CamelotWheel.normalize_key(current_key) or "8A"
        self._buttons: Dict[str, QPushButton] = {}
        self._init_ui()
        self._update_highlights()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header info
        header = QLabel("<h3>Select Master Deck Key & View Harmonic Transition Paths</h3>")
        header.setStyleSheet("color: #00d2ff;")
        layout.addWidget(header)

        # Camelot Grid (12 columns: 1 to 12)
        grid_frame = QFrame()
        grid_frame.setStyleSheet("background-color: #1a1d26; border: 1px solid #2b3040; border-radius: 8px; padding: 10px;")
        grid = QGridLayout(grid_frame)
        grid.setSpacing(6)

        # Row 0: Headers (1 to 12)
        for num in range(1, 13):
            lbl = QLabel(f"<b>{num}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #7b849b; font-size: 13px;")
            grid.addWidget(lbl, 0, num - 1)

        # Row 1: Major Keys (B) - Outer wheel
        for num in range(1, 13):
            k_b = f"{num}B"
            musical_b = CAMELOT_TO_KEY.get(k_b, "")
            btn = QPushButton(f"{k_b}\n{musical_b}")
            btn.setFixedSize(54, 50)
            btn.setStyleSheet(self._button_style(k_b, False))
            btn.clicked.connect(lambda _, k=k_b: self._on_key_clicked(k))
            self._buttons[k_b] = btn
            grid.addWidget(btn, 1, num - 1)

        # Row 2: Minor Keys (A) - Inner wheel
        for num in range(1, 13):
            k_a = f"{num}A"
            musical_a = CAMELOT_TO_KEY.get(k_a, "")
            btn = QPushButton(f"{k_a}\n{musical_a}")
            btn.setFixedSize(54, 50)
            btn.setStyleSheet(self._button_style(k_a, False))
            btn.clicked.connect(lambda _, k=k_a: self._on_key_clicked(k))
            self._buttons[k_a] = btn
            grid.addWidget(btn, 2, num - 1)

        layout.addWidget(grid_frame)

        # Compatibility Legend & Detail
        self.lbl_details = QLabel()
        self.lbl_details.setWordWrap(True)
        self.lbl_details.setStyleSheet("background-color: #161821; border: 1px solid #232735; border-radius: 6px; padding: 12px; font-size: 12px;")
        layout.addWidget(self.lbl_details)

        # Bottom Controls
        bottom_box = QHBoxLayout()
        self.chk_harmonic_only = QCheckBox("Filter 'Harmonic Matches Only' in Library")
        self.chk_harmonic_only.setChecked(True)
        self.chk_harmonic_only.setStyleSheet("color: #38bdf8; font-weight: bold;")
        bottom_box.addWidget(self.chk_harmonic_only)

        bottom_box.addStretch()

        btn_apply = QPushButton("✓ Apply Key to Live Filter")
        btn_apply.setStyleSheet("background-color: #00d2ff; color: #000; font-weight: bold; padding: 8px 18px; border-radius: 5px;")
        btn_apply.clicked.connect(self._on_apply)

        btn_cancel = QPushButton("Close")
        btn_cancel.clicked.connect(self.reject)

        bottom_box.addWidget(btn_cancel)
        bottom_box.addWidget(btn_apply)
        layout.addLayout(bottom_box)

    def _button_style(self, key_code: str, is_active: bool, is_match: bool = False, match_color: str = "#22c55e") -> str:
        is_major = key_code.endswith("B")
        base_border = "#00d2ff" if is_major else "#c77dff"
        base_bg = "#1f2937" if is_major else "#261c36"
        text_color = "#e5e7eb"

        if is_active:
            return f"background-color: #fbbf24; color: #000; font-weight: bold; border: 2px solid #ffffff; border-radius: 6px;"
        elif is_match:
            return f"background-color: {match_color}; color: #000; font-weight: bold; border: 2px solid #ffffff; border-radius: 6px;"
        else:
            return f"background-color: {base_bg}; color: {text_color}; border: 1px solid {base_border}; border-radius: 6px; font-size: 11px;"

    def _on_key_clicked(self, key_code: str) -> None:
        self.selected_key = key_code
        self._update_highlights()

    def _update_highlights(self) -> None:
        sel = self.selected_key
        matches = CamelotWheel.get_harmonic_matches(sel, include_exact=False, include_adjacent=True, include_relative=True, include_energy_boost=True, include_semitone=True)
        rel_key = CamelotWheel.get_relative_key(sel)
        adj_keys = CamelotWheel.get_adjacent_keys(sel)
        boosts = CamelotWheel.get_energy_boost_keys(sel)
        plus2 = boosts.get("plus_two_boost")
        semi7 = boosts.get("semitone_lift")

        for k, btn in self._buttons.items():
            if k == sel:
                btn.setStyleSheet(self._button_style(k, is_active=True))
            elif k in adj_keys:
                btn.setStyleSheet(self._button_style(k, is_active=False, is_match=True, match_color="#4ade80"))  # Smooth +1/-1
            elif k == rel_key:
                btn.setStyleSheet(self._button_style(k, is_active=False, is_match=True, match_color="#38bdf8"))  # Relative scale
            elif k == plus2:
                btn.setStyleSheet(self._button_style(k, is_active=False, is_match=True, match_color="#f97316"))  # +2 Energy boost
            elif k == semi7:
                btn.setStyleSheet(self._button_style(k, is_active=False, is_match=True, match_color="#e11d48"))  # +7 Semitone lift
            else:
                btn.setStyleSheet(self._button_style(k, is_active=False))

        # Update info text
        musical = CAMELOT_TO_KEY.get(sel, "")
        info = (
            f"<b>Active Key:</b> <span style='color: #fbbf24; font-size: 14px;'>{sel} ({musical})</span> &nbsp;|&nbsp; "
            f"<b style='color:#4ade80;'>Smooth Steps (±1):</b> {adj_keys[0]}, {adj_keys[1]} &nbsp;|&nbsp; "
            f"<b style='color:#38bdf8;'>Relative Scale:</b> {rel_key} &nbsp;|&nbsp; "
            f"<b style='color:#f97316;'>Energy Boost (+2):</b> {plus2} &nbsp;|&nbsp; "
            f"<b style='color:#e11d48;'>Peak Semitone Lift (+7):</b> {semi7}"
        )
        self.lbl_details.setText(info)

    def _on_apply(self) -> None:
        self.key_selected.emit(self.selected_key, self.chk_harmonic_only.isChecked())
        self.accept()


class GenreMultiSelectWidget(QWidget):
    """Searchable multi-genre selector supporting OR filtering across subgenres."""

    genres_changed = Signal(list)  # List[str]

    def __init__(self, db: Optional[Database] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.selected_genres: Set[str] = set()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Text input with autocomplete
        self.txt_genre = QLineEdit()
        self.txt_genre.setMinimumWidth(140)
        self.txt_genre.setPlaceholderText(_t("filter_genre_placeholder", "Cerca Generi (Ctrl+G)..."))
        self.txt_genre.setClearButtonEnabled(True)
        self.txt_genre.returnPressed.connect(self._on_add_text_genre)

        # Autocomplete from DB or common genres
        self._refresh_completer()

        # Dropdown button with checkable genre list
        self.btn_genre_menu = QToolButton()
        self.btn_genre_menu.setText("▾")
        self.btn_genre_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._build_menu()

        # Count badge button
        self.btn_count = QPushButton("All")
        self.btn_count.clicked.connect(self._show_selected_summary)

        layout.addWidget(self.txt_genre, 1)
        layout.addWidget(self.btn_genre_menu)
        layout.addWidget(self.btn_count)

        self._update_display()
        self.update_theme("light")
        I18n.get_instance().language_changed.connect(self._retranslate_ui)

    def _refresh_completer(self) -> None:
        genres = list(COMMON_DJ_GENRES)
        if self.db:
            try:
                db_genres = self.db.get_distinct_genres()
                genres = sorted(list(set(genres + db_genres)))
            except Exception:
                pass
        completer = QCompleter(genres, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_genre.setCompleter(completer)

    def _build_menu(self) -> None:
        menu = QMenu(self)
        genres = list(COMMON_DJ_GENRES)
        if self.db:
            try:
                db_genres = self.db.get_distinct_genres()
                genres = sorted(list(set(genres + db_genres)))
            except Exception:
                pass

        act_all = menu.addAction(_t("filter_clear_genres", "Rimuovi Selezione Generi"))
        act_all.triggered.connect(self.clear_selection)
        menu.addSeparator()

        for g in genres[:30]:  # Top 30 genres
            act = menu.addAction(g)
            act.setCheckable(True)
            act.setChecked(g in self.selected_genres)
            act.toggled.connect(lambda chk, genre=g: self._toggle_genre(genre, chk))

        self.btn_genre_menu.setMenu(menu)

    def _retranslate_ui(self) -> None:
        self._update_display()
        self._build_menu()

    def _toggle_genre(self, genre: str, checked: bool) -> None:
        if checked:
            self.selected_genres.add(genre)
        else:
            self.selected_genres.discard(genre)
        self._update_display()
        self.genres_changed.emit(list(self.selected_genres))

    def _on_add_text_genre(self) -> None:
        text = self.txt_genre.text().strip()
        if text:
            self.selected_genres.add(text)
            self.txt_genre.clear()
            self._update_display()
            self._build_menu()
            self.genres_changed.emit(list(self.selected_genres))

    def _update_display(self) -> None:
        if not self.selected_genres:
            self.btn_count.setText(_t("filter_all_genres", "Tutti"))
            self.txt_genre.setPlaceholderText(_t("filter_genre_placeholder", "Cerca Generi (Ctrl+G)..."))
        elif len(self.selected_genres) == 1:
            g = list(self.selected_genres)[0]
            self.btn_count.setText(_t("filter_one_genre", "1 Genere"))
            self.txt_genre.setPlaceholderText(g)
        else:
            self.btn_count.setText(_t("filter_multi_genres", "{count} Generi (OR)", count=len(self.selected_genres)))
            self.txt_genre.setPlaceholderText(", ".join(sorted(self.selected_genres)))

    def update_theme(self, theme_id: str = "light") -> None:
        """Adapts genre count button and menu toolbutton to active theme."""
        is_light = (theme_id == "light")
        if is_light:
            self.btn_count.setStyleSheet(
                "padding: 4px 8px; font-size: 11px; font-weight: 600; "
                "color: #0d6efd; background-color: #e7f1ff; border: 1px solid #b6d4fe; border-radius: 4px;"
            )
            self.btn_genre_menu.setStyleSheet(
                "padding: 5px 8px; font-weight: bold; background-color: #ffffff; "
                "border: 1px solid #ced4da; border-radius: 4px; color: #212529;"
            )
        else:
            self.btn_count.setStyleSheet(
                "padding: 4px 8px; font-size: 11px; font-weight: 600; "
                "color: #00d2ff; background-color: #172033; border: 1px solid #0284c7; border-radius: 4px;"
            )
            self.btn_genre_menu.setStyleSheet(
                "padding: 5px 8px; font-weight: bold; background-color: #20232b; "
                "border: 1px solid #2d313d; border-radius: 4px; color: #e0e2ec;"
            )

    def _show_selected_summary(self) -> None:
        if not self.selected_genres:
            return
        genres_str = "\n".join(f"• {g}" for g in sorted(self.selected_genres))
        QMessageBox.information(self, "Active Genres (OR Filter)", f"Active Genre Filter:\n{genres_str}")

    def clear_selection(self) -> None:
        self.selected_genres.clear()
        self.txt_genre.clear()
        self._update_display()
        self._build_menu()
        self.genres_changed.emit([])

    def set_genres(self, genres: Any) -> None:
        """Safely updates selected genres from a list, set, string, or empty/None value."""
        try:
            if genres is None:
                self.selected_genres = set()
            elif isinstance(genres, (list, set, tuple)):
                self.selected_genres = {str(g).strip() for g in genres if g and str(g).strip()}
            elif isinstance(genres, str):
                self.selected_genres = {genres.strip()} if genres.strip() else set()
            else:
                self.selected_genres = {str(genres).strip()}
            self._update_display()
            self._build_menu()
            self.genres_changed.emit(list(self.selected_genres))
        except Exception as exc:
            MusicatLogger.get_logger().error(f"[GENRE_WIDGET] Errore in set_genres: {exc}")

    def set_selected_genres(self, genres: Any) -> None:
        """Alias for set_genres."""
        self.set_genres(genres)


class LiveFilterBar(QFrame):
    """Primary Live DJ Filter Console & Crate Builder Bar."""

    filter_changed = Signal(FilterCriteria)
    crate_selected = Signal(str)  # crate name
    crate_saved = Signal(str)     # crate name
    export_playlist_requested = Signal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.filter_engine = LiveFilterEngine(db)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(80)  # 80ms live typing debounce
        self._debounce_timer.timeout.connect(self._emit_filter_changed)

        self._init_ui()
        self._connect_signals()
        self._retranslate_ui()
        I18n.get_instance().language_changed.connect(self._retranslate_ui)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 6, 10, 6)
        main_layout.setSpacing(6)

        # -------------------------------------------------------------
        # ROW 1: PRIMARY SEARCH & REPOSITORY FILTERS
        # (Search bar + engine, Folder/Drive selector, Genre multi-select, Cover filter, Reset ESC)
        # -------------------------------------------------------------
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # 1. Text Search Input (Ctrl+F)
        self.txt_search = QLineEdit()
        fast_engine = "Everything MFT" if sys.platform == "win32" else ("Spotlight" if sys.platform == "darwin" else "SQLite FTS")
        self.txt_search.setPlaceholderText(f"🔍 Quick Search / {fast_engine} (Ctrl+F)...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setMinimumWidth(200)

        # Search Engine Badge
        self.lbl_search_engine = QLabel(SearchEngine.get_engine_badge())
        self.lbl_search_engine.setStyleSheet(
            "color: #00d2ff; font-size: 10px; padding: 2px 5px; border: 1px solid #0284c7; border-radius: 3px;"
        )

        # 2. Drive / Directory Folder Filter
        folder_box = QHBoxLayout()
        folder_box.setSpacing(4)
        self.lbl_folder = QLabel("📁 Cartella:")
        self.cmb_folder = QComboBox()
        self.cmb_folder.addItem("Tutte le Cartelle / Drive", "")
        self.cmb_folder.setMinimumWidth(160)
        self.cmb_folder.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.cmb_folder.setToolTip("Filtra per cartella o drive sorgente")
        folder_box.addWidget(self.lbl_folder)
        folder_box.addWidget(self.cmb_folder)

        # 3. Multi-Genre Selector (Ctrl+G)
        self.genre_widget = GenreMultiSelectWidget(self.db, self)

        # 4. Cover Art Filter
        cover_box = QHBoxLayout()
        cover_box.setSpacing(4)
        self.lbl_cover = QLabel("🖼️ Cover:")
        self.cmb_cover = QComboBox()
        self.cmb_cover.addItem("Tutte", "")
        self.cmb_cover.addItem("Con Cover", "with_cover")
        self.cmb_cover.addItem("Senza Cover", "without_cover")
        self.cmb_cover.setMinimumWidth(100)
        self.cmb_cover.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.cmb_cover.setToolTip("Filtra tracce con o senza copertina")
        cover_box.addWidget(self.lbl_cover)
        cover_box.addWidget(self.cmb_cover)

        # 5. Instant Reset Button (ESC)
        self.btn_reset = QPushButton("✕ Reset (ESC)")
        self.btn_reset.setStyleSheet("background-color: #2c1d25; border: 1px solid #991b1b; color: #f87171; font-weight: bold; padding: 4px 10px; border-radius: 4px;")
        self.btn_reset.clicked.connect(self.reset_filters)

        # Assemble Row 1
        row1.addWidget(self.txt_search, 2)
        row1.addWidget(self.lbl_search_engine)
        row1.addLayout(folder_box)
        row1.addWidget(self.genre_widget, 2)
        row1.addLayout(cover_box)
        row1.addWidget(self.btn_reset)
        main_layout.addLayout(row1)

        # -------------------------------------------------------------
        # ROW 2: ACOUSTIC & MUSICAL DJ FILTERS
        # (BPM Range & Tolerance, Camelot Key / Wheel, Decade/Year, Quality, DJ Tags)
        # -------------------------------------------------------------
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        # 1. BPM Range & Target Tolerance (Ctrl+B)
        bpm_box = QHBoxLayout()
        bpm_box.setSpacing(4)
        self.lbl_bpm = QLabel("BPM:")
        self.lbl_bpm.setStyleSheet("color: #0284c7; font-weight: bold; font-size: 11px;")

        self.lbl_bpm_target = QLabel("Target:")
        self.lbl_bpm_target.setStyleSheet("color: #64748b; font-size: 10px;")
        self.spin_target_bpm = QDoubleSpinBox()
        self.spin_target_bpm.setRange(0, 250)
        self.spin_target_bpm.setDecimals(1)
        self.spin_target_bpm.setValue(0)
        self.spin_target_bpm.setSpecialValueText("Target")
        self.spin_target_bpm.setToolTip("Target Deck BPM (es. 126.0)")
        self.spin_target_bpm.setMinimumWidth(75)

        self.cmb_bpm_tolerance = QComboBox()
        self.cmb_bpm_tolerance.addItem("±2%", 2.0)
        self.cmb_bpm_tolerance.addItem("±4%", 4.0)
        self.cmb_bpm_tolerance.addItem("±6%", 6.0)
        self.cmb_bpm_tolerance.addItem("±8%", 8.0)
        self.cmb_bpm_tolerance.setCurrentIndex(1)  # ±4% default
        self.cmb_bpm_tolerance.setToolTip("Tolleranza Pitch BPM")
        self.cmb_bpm_tolerance.setMinimumWidth(62)

        self.lbl_bpm_or = QLabel("o")
        self.lbl_bpm_or.setStyleSheet("color: #64748b; font-size: 10px;")

        self.lbl_bpm_min = QLabel("Min:")
        self.lbl_bpm_min.setStyleSheet("color: #64748b; font-size: 10px;")
        self.spin_bpm_min = QDoubleSpinBox()
        self.spin_bpm_min.setRange(0, 250)
        self.spin_bpm_min.setDecimals(1)
        self.spin_bpm_min.setValue(0)
        self.spin_bpm_min.setSpecialValueText("Min")
        self.spin_bpm_min.setMinimumWidth(68)

        self.lbl_bpm_dash = QLabel("-")
        self.lbl_bpm_dash.setStyleSheet("color: #64748b; font-size: 10px;")

        self.lbl_bpm_max = QLabel("Max:")
        self.lbl_bpm_max.setStyleSheet("color: #64748b; font-size: 10px;")
        self.spin_bpm_max = QDoubleSpinBox()
        self.spin_bpm_max.setRange(0, 250)
        self.spin_bpm_max.setDecimals(1)
        self.spin_bpm_max.setValue(0)
        self.spin_bpm_max.setSpecialValueText("Max")
        self.spin_bpm_max.setMinimumWidth(68)

        bpm_box.addWidget(self.lbl_bpm)
        bpm_box.addWidget(self.lbl_bpm_target)
        bpm_box.addWidget(self.spin_target_bpm)
        bpm_box.addWidget(self.cmb_bpm_tolerance)
        bpm_box.addWidget(self.lbl_bpm_or)
        bpm_box.addWidget(self.lbl_bpm_min)
        bpm_box.addWidget(self.spin_bpm_min)
        bpm_box.addWidget(self.lbl_bpm_dash)
        bpm_box.addWidget(self.lbl_bpm_max)
        bpm_box.addWidget(self.spin_bpm_max)

        # 2. Harmonic Mixing Assistant (Camelot Wheel Matching) (Ctrl+K)
        camelot_box = QHBoxLayout()
        camelot_box.setSpacing(4)
        self.lbl_key = QLabel("Key:")
        self.lbl_key.setStyleSheet("color: #7c3aed; font-weight: bold; font-size: 11px;")

        self.cmb_camelot = QComboBox()
        self.cmb_camelot.addItem("All Keys", "")
        for k in CAMELOT_KEYS_ORDERED:
            musical = CAMELOT_TO_KEY.get(k, "")
            self.cmb_camelot.addItem(f"{k} ({musical})", k)
        self.cmb_camelot.setMinimumWidth(125)
        self.cmb_camelot.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        self.chk_harmonic_only = QCheckBox("Solo Armonici")
        self.chk_harmonic_only.setChecked(True)
        self.chk_harmonic_only.setToolTip("Mostra solo chiavi armonicamente compatibili (±1, Relativo, +2 Boost)")
        self.chk_harmonic_only.setStyleSheet("color: #7c3aed; font-weight: bold; font-size: 11px;")

        self.btn_wheel_popup = QPushButton("🎡 Ruota")
        self.btn_wheel_popup.setToolTip("Apri Ruota Camelot Interattiva (Ctrl+K)")
        self.btn_wheel_popup.setStyleSheet("background-color: #27203b; border: 1px solid #7c3aed; color: #c084fc; font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        self.btn_wheel_popup.clicked.connect(self._open_camelot_wheel)

        camelot_box.addWidget(self.lbl_key)
        camelot_box.addWidget(self.cmb_camelot)
        camelot_box.addWidget(self.chk_harmonic_only)
        camelot_box.addWidget(self.btn_wheel_popup)

        # 3. Decade / Year Filter
        year_box = QHBoxLayout()
        year_box.setSpacing(4)
        self.lbl_year = QLabel("Anno:")
        self.cmb_decade = QComboBox()
        self.cmb_decade.addItem("Qualsiasi Anno", (None, None))
        self.cmb_decade.addItem("2020s (2020-2026)", (2020, 2026))
        self.cmb_decade.addItem("2010s (2010-2019)", (2010, 2019))
        self.cmb_decade.addItem("2000s (2000-2009)", (2000, 2009))
        self.cmb_decade.addItem("90s Revival (1990-1999)", (1990, 1999))
        self.cmb_decade.addItem("80s Classics (1980-1989)", (1980, 1989))
        self.cmb_decade.setMinimumWidth(140)
        self.cmb_decade.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        year_box.addWidget(self.lbl_year)
        year_box.addWidget(self.cmb_decade)

        # 4. Audio Quality / Diagnostics Filter
        quality_box = QHBoxLayout()
        quality_box.setSpacing(4)
        self.lbl_quality = QLabel("Audio:")
        self.lbl_quality.setStyleSheet("font-weight: 600; font-size: 11px;")
        self.cmb_quality = QComboBox()
        self.cmb_quality.addItem("🔊 All Audio", "")
        self.cmb_quality.addItem("⚠️ Clipping (>0 dBTP)", "clipping")
        self.cmb_quality.addItem("🔈 Basso Vol (<-18 LUFS)", "low_volume")
        self.cmb_quality.addItem("🧱 Brickwall (LRA < 3)", "brickwall")
        self.cmb_quality.addItem("⚡ Tracce Problematiche", "problematic")
        self.cmb_quality.addItem("✅ Conforme (OK)", "ok")
        self.cmb_quality.setMinimumWidth(160)
        self.cmb_quality.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        quality_box.addWidget(self.lbl_quality)
        quality_box.addWidget(self.cmb_quality)

        # 5. Quick DJ Tags (Pills)
        tags_box = QHBoxLayout()
        tags_box.setSpacing(4)
        self.btn_tag_intro = QPushButton("Intro")
        self.btn_tag_vocal = QPushButton("Vocal")
        self.btn_tag_inst = QPushButton("Instrumental")
        self.btn_tag_acapella = QPushButton("Acapella")
        self.btn_tag_club = QPushButton("Club")

        self.btn_tag_intro.setMinimumWidth(44)
        self.btn_tag_vocal.setMinimumWidth(46)
        self.btn_tag_inst.setMinimumWidth(80)
        self.btn_tag_acapella.setMinimumWidth(62)
        self.btn_tag_club.setMinimumWidth(44)

        for btn in [self.btn_tag_intro, self.btn_tag_vocal, self.btn_tag_inst, self.btn_tag_acapella, self.btn_tag_club]:
            btn.setCheckable(True)
            btn.toggled.connect(self._trigger_debounce)
            tags_box.addWidget(btn)

        # Smart Crate Actions (Destra)
        crate_box = QHBoxLayout()
        crate_box.setSpacing(4)

        self.cmb_crates = QComboBox()
        self.cmb_crates.addItem("📁 Smart Crates...", "")
        self.cmb_crates.setFixedWidth(135)
        self.cmb_crates.currentIndexChanged.connect(self._on_crate_selected)

        self.btn_save_crate = QPushButton("💾 Salva")
        self.btn_save_crate.setStyleSheet("background-color: #1e3a5f; border: 1px solid #0284c7; color: #38bdf8; font-weight: bold; padding: 3px 6px; border-radius: 4px; font-size: 11px;")
        self.btn_save_crate.clicked.connect(self._on_save_crate)

        self.btn_export_m3u = QPushButton("📤 M3U8")
        self.btn_export_m3u.setStyleSheet("background-color: #14532d; border: 1px solid #16a34a; color: #4ade80; font-weight: bold; padding: 3px 6px; border-radius: 4px; font-size: 11px;")
        self.btn_export_m3u.setToolTip("Esporta crate filtrato corrente in M3U8 per Rekordbox, Traktor, Serato, Engine DJ")
        self.btn_export_m3u.clicked.connect(self.export_playlist_requested.emit)

        crate_box.addWidget(self.cmb_crates)
        crate_box.addWidget(self.btn_save_crate)
        crate_box.addWidget(self.btn_export_m3u)

        row2.addLayout(bpm_box)
        row2.addLayout(camelot_box)
        row2.addLayout(year_box)
        row2.addLayout(quality_box)
        row2.addLayout(tags_box)
        row2.addStretch()
        row2.addLayout(crate_box)
        main_layout.addLayout(row2)

        self.update_theme("light")

    def _retranslate_ui(self) -> None:
        """Dynamically updates filter bar text in response to language change."""
        fast_engine = "Everything MFT" if sys.platform == "win32" else ("Spotlight" if sys.platform == "darwin" else "SQLite FTS")
        self.txt_search.setPlaceholderText(_t("filter_search_placeholder", "🔍 Ricerca Rapida / {engine} (Ctrl+F)...", engine=fast_engine))
        self.btn_reset.setText(_t("filter_reset", "✕ Ripristina (ESC)"))
        self.btn_wheel_popup.setText(_t("filter_wheel_btn", "🎡 Ruota"))
        self.chk_harmonic_only.setText(_t("filter_harmonic_only", "Solo Armonici"))
        self.spin_target_bpm.setSpecialValueText(_t("filter_target_bpm", "Target"))
        self.spin_bpm_min.setSpecialValueText(_t("filter_min_bpm", "Min"))
        self.spin_bpm_max.setSpecialValueText(_t("filter_max_bpm", "Max"))
        self.lbl_bpm.setText(_t("filter_bpm", "BPM:"))
        self.lbl_bpm_target.setText(_t("filter_target_label", "Target:"))
        self.lbl_bpm_min.setText(_t("filter_min_label", "Min:"))
        self.lbl_bpm_max.setText(_t("filter_max_label", "Max:"))
        self.lbl_key.setText(_t("filter_key", "Key:"))
        self.lbl_year.setText(_t("filter_year", "Anno:"))
        self.lbl_quality.setText(_t("filter_audio", "Audio:"))
        self.lbl_folder.setText(_t("filter_folder", "📁 Cartella:"))
        self.lbl_cover.setText(_t("filter_cover", "🖼️ Cover:"))

        self.cmb_camelot.setItemText(0, _t("filter_all_keys", "Tutte le Chiavi"))
        self.cmb_decade.setItemText(0, _t("filter_any_year", "Qualsiasi Anno"))
        self.cmb_quality.setItemText(0, _t("filter_all_audio", "🔊 Tutto l'Audio"))
        self.cmb_quality.setItemText(1, _t("filter_clipping", "⚠️ Clipping (>0 dBTP)"))
        self.cmb_quality.setItemText(2, _t("filter_low_vol", "🔈 Basso Vol (<-18 LUFS)"))
        self.cmb_quality.setItemText(3, _t("filter_brickwall", "🧱 Brickwall (LRA < 3)"))
        self.cmb_quality.setItemText(4, _t("filter_problematic", "⚡ Tracce Problematiche"))
        self.cmb_quality.setItemText(5, _t("filter_conforme", "✅ Conforme (OK)"))
        self.cmb_crates.setItemText(0, _t("filter_smart_crates", "📁 Smart Crates..."))
        self.btn_save_crate.setText(_t("filter_save_crate", "💾 Salva Crate"))
        self.btn_export_m3u.setText(_t("filter_export_m3u", "📤 Esporta M3U8"))
        self.cmb_folder.setItemText(0, _t("filter_all_folders", "Tutte le Cartelle / Drive"))
        self.cmb_cover.setItemText(0, _t("filter_all_covers", "Tutte"))
        self.cmb_cover.setItemText(1, _t("filter_with_cover", "Con Cover"))
        self.cmb_cover.setItemText(2, _t("filter_without_cover", "Senza Cover"))

        self._refresh_crates_dropdown()
        self.refresh_directories()

    def update_theme(self, theme_id: str = "light") -> None:
        """Adapts filter bar buttons, badges, and tag pills to active Light/Dark theme."""
        is_light = (theme_id == "light")
        if hasattr(self, "genre_widget") and hasattr(self.genre_widget, "update_theme"):
            self.genre_widget.update_theme(theme_id)

        if is_light:
            tag_style = """
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 500;
                    color: #495057;
                }
                QPushButton:hover {
                    background-color: #f1f3f5;
                    border-color: #0d6efd;
                    color: #0d6efd;
                }
                QPushButton:checked {
                    background-color: #0d6efd;
                    color: #ffffff;
                    font-weight: bold;
                    border-color: #0b5ed7;
                }
            """
            self.btn_reset.setStyleSheet("""
                QPushButton {
                    background-color: #fee2e2;
                    border: 1px solid #fca5a5;
                    color: #b91c1c;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #fecaca;
                    border-color: #ef4444;
                    color: #991b1b;
                }
            """)
            self.btn_wheel_popup.setStyleSheet("""
                QPushButton {
                    background-color: #f3e8ff;
                    border: 1px solid #d8b4fe;
                    color: #7e22ce;
                    font-weight: bold;
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e9d5ff;
                    border-color: #a855f7;
                    color: #6b21a8;
                }
            """)
            self.lbl_search_engine.setStyleSheet(
                "color: #0369a1; font-size: 10px; font-weight: 600; padding: 2px 6px; "
                "background-color: #e0f2fe; border: 1px solid #7dd3fc; border-radius: 3px;"
            )
        else:
            tag_style = """
                QPushButton {
                    background-color: #1a1d27;
                    border: 1px solid #2e3447;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    color: #94a3b8;
                }
                QPushButton:hover {
                    background-color: #242938;
                    border-color: #38bdf8;
                    color: #ffffff;
                }
                QPushButton:checked {
                    background-color: #0284c7;
                    color: #ffffff;
                    font-weight: bold;
                    border-color: #38bdf8;
                }
            """
            self.btn_reset.setStyleSheet("""
                QPushButton {
                    background-color: #2c1d25;
                    border: 1px solid #991b1b;
                    color: #f87171;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #3b1e28;
                    border-color: #ef4444;
                    color: #ffffff;
                }
            """)
            self.btn_wheel_popup.setStyleSheet("""
                QPushButton {
                    background-color: #27203b;
                    border: 1px solid #7c3aed;
                    color: #c084fc;
                    font-weight: bold;
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #342950;
                    border-color: #a855f7;
                    color: #ffffff;
                }
            """)
            self.lbl_search_engine.setStyleSheet(
                "color: #00d2ff; font-size: 10px; padding: 2px 5px; border: 1px solid #0284c7; border-radius: 3px;"
            )

        for btn in [self.btn_tag_intro, self.btn_tag_vocal, self.btn_tag_inst, self.btn_tag_acapella, self.btn_tag_club]:
            btn.setStyleSheet(tag_style)

    def _connect_signals(self) -> None:
        self.txt_search.textChanged.connect(self._trigger_debounce)
        self.genre_widget.genres_changed.connect(self._trigger_debounce)
        self.spin_target_bpm.valueChanged.connect(self._on_target_bpm_changed)
        self.cmb_bpm_tolerance.currentIndexChanged.connect(self._on_target_bpm_changed)
        self.spin_bpm_min.valueChanged.connect(self._trigger_debounce)
        self.spin_bpm_max.valueChanged.connect(self._trigger_debounce)
        self.cmb_camelot.currentIndexChanged.connect(self._trigger_debounce)
        self.chk_harmonic_only.toggled.connect(self._trigger_debounce)
        self.cmb_folder.currentIndexChanged.connect(self._trigger_debounce)
        self.cmb_cover.currentIndexChanged.connect(self._trigger_debounce)
        self.cmb_decade.currentIndexChanged.connect(self._trigger_debounce)
        self.cmb_quality.currentIndexChanged.connect(self._trigger_debounce)

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _on_target_bpm_changed(self) -> None:
        target = self.spin_target_bpm.value()
        if target > 0:
            tol = float(self.cmb_bpm_tolerance.currentData() or 4.0)
            min_b, max_b = CamelotWheel.calculate_bpm_tolerance_range(target, tol)
            # Temporarily block signals on min/max spinboxes to prevent circular events
            self.spin_bpm_min.blockSignals(True)
            self.spin_bpm_max.blockSignals(True)
            self.spin_bpm_min.setValue(min_b)
            self.spin_bpm_max.setValue(max_b)
            self.spin_bpm_min.blockSignals(False)
            self.spin_bpm_max.blockSignals(False)
        self._trigger_debounce()

    def _emit_filter_changed(self) -> None:
        criteria = self.get_current_criteria()
        self.filter_changed.emit(criteria)

    def get_current_criteria(self) -> FilterCriteria:
        """Collects state from all controls and returns a FilterCriteria object."""
        target_bpm = self.spin_target_bpm.value()
        tol = float(self.cmb_bpm_tolerance.currentData() or 4.0)

        min_bpm = self.spin_bpm_min.value()
        max_bpm = self.spin_bpm_max.value()

        key = self.cmb_camelot.currentData() or ""
        harmonic = self.chk_harmonic_only.isChecked()

        year_min, year_max = self.cmb_decade.currentData() or (None, None)
        energy_levels: List[int] = []
        rating_min = None
        quality_filter = self.cmb_quality.currentData() or None
        folder_path = self.cmb_folder.currentData() or None
        cover_filter = self.cmb_cover.currentData() or None

        active_tags = []
        if self.btn_tag_intro.isChecked():
            active_tags.append("Intro")
        if self.btn_tag_vocal.isChecked():
            active_tags.append("Vocal")
        if self.btn_tag_inst.isChecked():
            active_tags.append("Instrumental")
        if self.btn_tag_acapella.isChecked():
            active_tags.append("Acapella")
        if self.btn_tag_club.isChecked():
            active_tags.append("Club")

        return FilterCriteria(
            query_text=self.txt_search.text().strip(),
            genres=self.genre_widget.selected_genres,
            target_bpm=target_bpm if target_bpm > 0 else None,
            bpm_tolerance_pct=tol if target_bpm > 0 else None,
            bpm_min=min_bpm if min_bpm > 0 else None,
            bpm_max=max_bpm if max_bpm > 0 else None,
            camelot_key=key if key else None,
            harmonic_matches_only=harmonic,
            year_min=year_min,
            year_max=year_max,
            rating_min=rating_min,
            energy_levels=energy_levels,
            tags=active_tags,
            quality_filter=quality_filter,
            folder_path=folder_path,
            cover_filter=cover_filter,
        )

    def set_criteria(self, criteria: FilterCriteria) -> None:
        """Applies a FilterCriteria configuration to the UI widgets."""
        self.txt_search.setText(criteria.query_text)
        self.genre_widget.set_genres(criteria.genres)

        if criteria.target_bpm:
            self.spin_target_bpm.setValue(criteria.target_bpm)
        else:
            self.spin_target_bpm.setValue(0)

        if criteria.bpm_min:
            self.spin_bpm_min.setValue(criteria.bpm_min)
        else:
            self.spin_bpm_min.setValue(0)

        if criteria.bpm_max:
            self.spin_bpm_max.setValue(criteria.bpm_max)
        else:
            self.spin_bpm_max.setValue(0)

        if criteria.camelot_key:
            idx = self.cmb_camelot.findData(criteria.camelot_key)
            if idx >= 0:
                self.cmb_camelot.setCurrentIndex(idx)
        else:
            self.cmb_camelot.setCurrentIndex(0)

        self.chk_harmonic_only.setChecked(criteria.harmonic_matches_only)

        if getattr(criteria, "folder_path", None):
            idx = self.cmb_folder.findData(criteria.folder_path)
            if idx >= 0:
                self.cmb_folder.setCurrentIndex(idx)
            else:
                self.cmb_folder.addItem(criteria.folder_path, criteria.folder_path)
                self.cmb_folder.setCurrentIndex(self.cmb_folder.count() - 1)
        else:
            self.cmb_folder.setCurrentIndex(0)

        if getattr(criteria, "cover_filter", None):
            idx = self.cmb_cover.findData(criteria.cover_filter)
            if idx >= 0:
                self.cmb_cover.setCurrentIndex(idx)
        else:
            self.cmb_cover.setCurrentIndex(0)

        if getattr(criteria, "quality_filter", None):
            idx = self.cmb_quality.findData(criteria.quality_filter)
            if idx >= 0:
                self.cmb_quality.setCurrentIndex(idx)
        else:
            self.cmb_quality.setCurrentIndex(0)

        # Tags
        tags = set(criteria.tags)
        self.btn_tag_intro.setChecked("Intro" in tags)
        self.btn_tag_vocal.setChecked("Vocal" in tags)
        self.btn_tag_inst.setChecked("Instrumental" in tags)
        self.btn_tag_acapella.setChecked("Acapella" in tags)
        self.btn_tag_club.setChecked("Club" in tags)

        self._emit_filter_changed()

    def reset_filters(self) -> None:
        """Clears all active filters instantly (keyboard shortcut: ESC)."""
        self.txt_search.clear()
        self.genre_widget.clear_selection()
        self.spin_target_bpm.setValue(0)
        self.spin_bpm_min.setValue(0)
        self.spin_bpm_max.setValue(0)
        self.cmb_camelot.setCurrentIndex(0)
        self.chk_harmonic_only.setChecked(True)
        self.cmb_folder.setCurrentIndex(0)
        self.cmb_cover.setCurrentIndex(0)
        self.cmb_decade.setCurrentIndex(0)
        self.cmb_quality.setCurrentIndex(0)
        for btn in [self.btn_tag_intro, self.btn_tag_vocal, self.btn_tag_inst, self.btn_tag_acapella, self.btn_tag_club]:
            btn.setChecked(False)

        self._emit_filter_changed()

    def refresh_directories(self) -> None:
        """Refreshes distinct directories dropdown from the database."""
        if not self.db:
            return
        cur_val = self.cmb_folder.currentData() or ""
        self.cmb_folder.blockSignals(True)
        self.cmb_folder.clear()
        self.cmb_folder.addItem("Tutte le Cartelle / Drive", "")
        try:
            dirs = self.db.get_distinct_directories()
            for d in dirs:
                display = d
                if len(display) > 36:
                    display = "..." + display[-33:]
                self.cmb_folder.addItem(display, d)
        except Exception:
            pass
        idx = self.cmb_folder.findData(cur_val)
        if idx >= 0:
            self.cmb_folder.setCurrentIndex(idx)
        else:
            self.cmb_folder.setCurrentIndex(0)
        self.cmb_folder.blockSignals(False)

    def set_folder_filter(self, folder_path: str) -> None:
        """Sets active folder filter and triggers debounced search."""
        idx = self.cmb_folder.findData(folder_path)
        if idx >= 0:
            self.cmb_folder.setCurrentIndex(idx)
        else:
            self.cmb_folder.addItem(folder_path, folder_path)
            self.cmb_folder.setCurrentIndex(self.cmb_folder.count() - 1)
        self._trigger_debounce()

    def _open_camelot_wheel(self) -> None:
        current_k = self.cmb_camelot.currentData() or "8A"
        dlg = CamelotWheelDialog(current_k, self)
        dlg.key_selected.connect(self._on_wheel_key_selected)
        dlg.exec()

    def _on_wheel_key_selected(self, key_code: str, harmonic_only: bool) -> None:
        idx = self.cmb_camelot.findData(key_code)
        if idx >= 0:
            self.cmb_camelot.setCurrentIndex(idx)
        self.chk_harmonic_only.setChecked(harmonic_only)
        self._trigger_debounce()

    # Smart Crate management
    def _refresh_crates_dropdown(self) -> None:
        self.cmb_crates.blockSignals(True)
        self.cmb_crates.clear()
        self.cmb_crates.addItem("📁 Smart Crates...", "")
        try:
            crates = self.filter_engine.get_smart_crates()
            for c in crates:
                self.cmb_crates.addItem(f"⚡ {c['name']}", c["name"])
        except Exception:
            pass
        self.cmb_crates.blockSignals(False)

    def _on_save_crate(self) -> None:
        crit = self.get_current_criteria()
        if crit.is_empty():
            QMessageBox.warning(self, "Empty Filter", "Please set at least one filter rule before saving a Smart Crate.")
            return

        name, ok = QInputDialog.getText(
            self,
            "Save Smart Crate",
            "Enter a name for this dynamic Smart Crate (e.g. 'Peak Time Tech House 126-128'):",
        )
        if ok and name.strip():
            crate_name = name.strip()
            self.filter_engine.save_smart_crate(crate_name, crit)
            self._refresh_crates_dropdown()
            # Select it
            idx = self.cmb_crates.findData(crate_name)
            if idx >= 0:
                self.cmb_crates.setCurrentIndex(idx)
            self.crate_saved.emit(crate_name)
            QMessageBox.information(self, "Smart Crate Saved", f"Smart Crate '{crate_name}' saved!\nIt will auto-update as new tracks are added to your library.")

    def _on_crate_selected(self, index: int) -> None:
        crate_name = self.cmb_crates.currentData()
        if not crate_name:
            return
        crit = self.filter_engine.load_smart_crate_criteria(crate_name)
        if crit:
            self.set_criteria(crit)
            self.crate_selected.emit(crate_name)

    # Keyboard Focus Helpers
    def focus_search(self) -> None:
        self.txt_search.setFocus()
        self.txt_search.selectAll()

    def focus_genre(self) -> None:
        self.genre_widget.txt_genre.setFocus()
        self.genre_widget.txt_genre.selectAll()

    def focus_bpm(self) -> None:
        self.spin_target_bpm.setFocus()
        self.spin_target_bpm.selectAll()
