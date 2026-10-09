"""
Main Window for Musicat.

Central DJ Console integrating virtual track library, instant multi-attribute filters,
Voidtools Everything MFT instant search, live logging console, multi-source metadata
reconciliation, and libVLC mini-player.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QByteArray, QDir, QModelIndex, QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableView,
    QToolBar,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.db import Database
from ..core.path_resolver import PathResolver
from ..core.scanner import LibraryScanner
from ..core.logger import MusicatLogger
from ..core.settings import SettingsManager
from ..core.file_manager import MusicFileManager
from ..core.hardware_monitor import HardwareMonitor
from ..core.search_factory import SearchEngine, EverythingSearchEngine
from ..core.filter_engine import FilterCriteria, LiveFilterEngine
from ..core.i18n import I18n, _t
from ..audio.analyzer import AcousticAnalyzer
from .table_model import TrackTableModel
from .player_widget import MiniPlayerWidget
from .live_filters import LiveFilterBar, CamelotWheelDialog
from .tag_editor_dialog import TagEditorDialog
from .sorter_dialog import SorterDialog
from .pattern_dialog import PatternDialog
from .reconciler_dialog import ReconciliationDialog, ReconcilerDialog
from .settings_dialog import SettingsDialog
from .mp3tag_workspace import Mp3tagWorkspaceWindow
from .views import (
    HomeTrendsView,
    QualityDiagnosisDialog,
    SimilarTracksDialog,
    SmartCratesView,
    SimilarTracksView,
    OrganizerView,
)
from .styles import get_theme_stylesheet


class HardwareProgressBar(QProgressBar):
    """Compact horizontal progress bar with dynamic load coloring and centered text."""

    def __init__(self, prefix: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.prefix = prefix
        self.setRange(0, 100)
        self.setFixedHeight(18)
        self.setFixedWidth(135)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setTextVisible(True)
        self._current_pct = 0.0

    def update_load(self, percent: float, display_text: str, is_light: bool = True) -> None:
        self._current_pct = max(0.0, min(100.0, percent))
        self.setValue(int(round(self._current_pct)))
        self.setFormat(display_text)

        # Dynamic color thresholds:
        # Green (#28A745): 0% - 60%
        # Yellow / Orange (#FD7E14): 61% - 84%
        # Red (#DC3545): 85% - 100%
        if self._current_pct <= 60.0:
            chunk_color = "#28A745"
        elif self._current_pct <= 84.0:
            chunk_color = "#FD7E14"
        else:
            chunk_color = "#DC3545"

        bg_color = "#e9ecef" if is_light else "#1a1d26"
        border_color = "#ced4da" if is_light else "#2d313f"
        text_color = "#212529" if is_light else "#f1f3f5"

        self.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {border_color};
                border-radius: 4px;
                text-align: center;
                background-color: {bg_color};
                color: {text_color};
                font-size: 10px;
                font-weight: 700;
            }}
            QProgressBar::chunk {{
                background-color: {chunk_color};
                border-radius: 3px;
            }}
        """)


class BackgroundScanWorker(QThread):
    """Background worker thread for filesystem scanning and SQLite indexing."""

    progress = Signal(int, int, str)  # cur, total, path
    finished = Signal(dict)

    def __init__(self, folder_path: str, db: Database) -> None:
        super().__init__()
        self.folder_path = folder_path
        self.db = db
        self.scanner = LibraryScanner(self.db)

    def run(self) -> None:
        result = self.scanner.scan_directory(self.folder_path, progress_callback=self.progress.emit)
        self.finished.emit(result)

    def cancel(self) -> None:
        self.scanner.cancel()


class AsyncAnalysisWorker(QThread):
    """Background worker thread for bulk acoustic analysis (BPM & Camelot Key) and physical tag persistence."""

    progress = Signal(int, int, str)
    track_completed = Signal(dict)
    finished = Signal(int, list)
    cancelled = Signal()

    def __init__(self, tracks: List[Dict[str, Any]], db: Database) -> None:
        super().__init__()
        self.tracks = tracks
        self.db = db
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        total = len(self.tracks)
        success_count = 0
        updated_tracks: List[Dict[str, Any]] = []

        from ..audio.analyzer import AcousticAnalyzer
        from ..tags.editor import AudioTagEditor
        from ..core.logger import MusicatLogger

        for idx, tr in enumerate(self.tracks):
            if self._is_cancelled:
                self.cancelled.emit()
                return

            fp = tr.get("filepath", "")
            filename = Path(fp).name
            self.progress.emit(idx + 1, total, filename)

            try:
                # 1. Acoustic extraction (BPM, Key, Camelot)
                profile = AcousticAnalyzer.analyze_file(fp)
                updates: Dict[str, Any] = {
                    "bpm": profile.bpm,
                    "musical_key": profile.musical_key,
                    "camelot_key": profile.camelot_key,
                    "initial_key": profile.camelot_key,
                }

                # 2. Clean separation: If Artist is empty and Title or stem contains " - ", split cleanly
                cur_title = tr.get("title") or Path(fp).stem
                cur_artist = tr.get("artist") or ""

                if not cur_artist or cur_artist.strip() == "" or cur_artist.lower() in ("various", "unknown"):
                    if " - " in cur_title:
                        parts = cur_title.split(" - ", 1)
                        clean_artist = parts[0].strip()
                        clean_title = parts[1].strip()
                        if clean_artist and clean_title:
                            updates["artist"] = clean_artist
                            updates["title"] = clean_title
                    else:
                        stem = Path(fp).stem
                        if " - " in stem:
                            parts = stem.split(" - ", 1)
                            if clean_artist and clean_title:
                                updates["artist"] = clean_artist
                                updates["title"] = clean_title

                # 3. Cascading metadata enrichment (Genre & Year fallback) if missing or generic
                cur_genre = tr.get("genre") or ""
                cur_year = tr.get("year")
                need_genre = not cur_genre or cur_genre.strip() == "" or cur_genre.lower() in ("vario", "other", "unknown")
                need_year = not cur_year or not str(cur_year).isdigit()

                if need_genre or need_year:
                    search_artist = updates.get("artist") or cur_artist
                    search_title = updates.get("title") or cur_title
                    query = f"{search_artist} - {search_title}" if search_artist else search_title

                    years_by_source: Dict[str, Any] = {}
                    genres_by_source: Dict[str, Any] = {}

                    if cur_year and str(cur_year).isdigit():
                        years_by_source["File Attuale"] = int(cur_year)
                    if cur_genre and cur_genre.strip() and cur_genre.lower() not in ("vario", "other", "unknown"):
                        genres_by_source["File Attuale"] = cur_genre

                    from ..scrapers.discogs import DiscogsClient
                    from ..scrapers.musicbrainz import MusicBrainzClient
                    from ..scrapers.reconciler import MetadataReconciler
                    from ..scrapers.web_enricher import WebEnricher

                    # 1. Discogs API
                    try:
                        disc_results = DiscogsClient().search_releases(query, limit=2)
                        for d in disc_results:
                            if d.get("year") and str(d["year"]).isdigit():
                                years_by_source.setdefault("Discogs", int(d["year"]))
                            if d.get("genre"):
                                cleaned = MetadataReconciler.clean_and_normalize_genre(d["genre"])
                                if cleaned and cleaned.lower() not in MetadataReconciler.BROAD_GENRES:
                                    genres_by_source.setdefault("Discogs", cleaned)
                    except Exception:
                        pass

                    # 2. MusicBrainz API
                    try:
                        mb_results = MusicBrainzClient.search_track(search_title, search_artist, limit=2)
                        for m in mb_results:
                            if m.get("year") and str(m["year"]).isdigit():
                                years_by_source.setdefault("MusicBrainz", int(m["year"]))
                            if m.get("genre"):
                                cleaned = MetadataReconciler.clean_and_normalize_genre(m["genre"])
                                if cleaned:
                                    genres_by_source.setdefault("MusicBrainz", cleaned)
                    except Exception:
                        pass

                    # 3. Web & YouTube fallback
                    try:
                        web_res = WebEnricher.search_genre_and_year(search_artist, search_title)
                        if web_res:
                            if web_res.get("year") and str(web_res["year"]).isdigit():
                                years_by_source.setdefault("Web/YouTube", int(web_res["year"]))
                            if web_res.get("genre"):
                                cleaned = MetadataReconciler.clean_and_normalize_genre(web_res["genre"])
                                if cleaned:
                                    genres_by_source.setdefault("Web/YouTube", cleaned)
                    except Exception:
                        pass

                    # Detect conflicts across providers
                    conflicts: Dict[str, Dict[str, Any]] = {}
                    distinct_years = {v for v in years_by_source.values() if v is not None}
                    if len(distinct_years) > 1:
                        conflicts["year"] = years_by_source

                    distinct_genres = {str(v).strip().lower() for v in genres_by_source.values() if v is not None}
                    if len(distinct_genres) > 1:
                        conflicts["genre"] = genres_by_source

                    if conflicts:
                        updates["_conflicts"] = conflicts
                        tr["_conflicts"] = conflicts

                    # Select recommended consensus values
                    if genres_by_source:
                        updates["genre"] = MetadataReconciler._select_recommended_genre(genres_by_source)
                    elif need_genre and not tr.get("genre"):
                        updates["genre"] = "Vario"

                    if years_by_source:
                        rec_year = MetadataReconciler._select_recommended_year(years_by_source)
                        if rec_year:
                            updates["year"] = rec_year

                # 4. Write physical tags with Mutagen
                AudioTagEditor.write_metadata(fp, {k: v for k, v in updates.items() if not k.startswith("_")})

                # 5. Write to SQLite database
                self.db.update_track_tags(fp, {k: v for k, v in updates.items() if not k.startswith("_")})

                full_updated = dict(tr)
                full_updated.update(updates)
                updated_tracks.append(full_updated)
                self.track_completed.emit(full_updated)
                success_count += 1
            except Exception as exc:
                MusicatLogger.warning("ASYNC_ANALYSIS", f"Error analyzing '{filename}': {exc}")

        self.finished.emit(success_count, updated_tracks)


# Backwards compatibility alias
BackgroundAnalysisWorker = AsyncAnalysisWorker

DEFAULT_VISIBLE_COLUMN_IDS = [
    "id", "has_cover", "title", "artist", "remixer", "bpm",
    "camelot_key", "musical_key", "genre", "year", "duration", "bitrate"
]

DEFAULT_COLUMN_WIDTHS = {
    "id": 40,
    "has_cover": 45,
    "title": 220,
    "artist": 180,
    "remixer": 130,
    "bpm": 65,
    "camelot_key": 70,
    "musical_key": 65,
    "genre": 120,
    "year": 60,
    "duration": 65,
    "bitrate": 65,
    "album": 140,
    "label": 120,
    "energy_level": 70,
    "lufs": 80,
    "true_peak": 80,
    "audio_status": 80,
    "filepath": 200,
}


class MainWindow(QMainWindow):
    """Musicat Primary Window."""

    log_signal = Signal(str, int, str)  # time, level, msg

    def __init__(self, db: Optional[Database] = None) -> None:
        super().__init__()
        self.db = db or Database()
        self.settings_manager = SettingsManager()
        self.file_manager = MusicFileManager(self.db)
        self.filter_engine = LiveFilterEngine(self.db)
        self.table_model = TrackTableModel()
        self.all_tracks: List[Dict[str, Any]] = []
        self._mp3tag_window: Optional[Mp3tagWorkspaceWindow] = None
        self._custom_columns_active: bool = False
        self.analysis_worker: Optional[AsyncAnalysisWorker] = None

        self.setWindowTitle(_t("app_title", "Musicat — DJ Catalog & Smart Organizer"))
        self.resize(1300, 820)

        self._init_ui()
        self._init_shortcuts()
        self._init_menu_and_toolbar()
        self._init_live_log_dock()
        self._refresh_library()
        self._retranslate_ui()
        I18n.get_instance().language_changed.connect(self._retranslate_ui)

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Clean Minimal Top Navigation Bar (Macro-Modules)
        self.nav_bar = QFrame(self)
        self.nav_bar.setObjectName("topNavBar")
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(10, 4, 10, 4)
        nav_layout.setSpacing(6)

        # Main Navigation Macro-Buttons:
        # [Libreria], [Top Charts], [Tag Editor (Mp3tag)], [Trova Simili], [Organizza File], [Smart Crates], [Impostazioni]
        self.btn_nav_library = QPushButton(_t("nav_library", "📁  Libreria"))
        self.btn_nav_library.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_library.clicked.connect(lambda: self._switch_view(0))

        self.btn_nav_trends = QPushButton(_t("nav_top_charts", "🔥  Top Charts"))
        self.btn_nav_trends.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_trends.clicked.connect(lambda: self._switch_view(1))

        self.btn_nav_mp3tag = QPushButton(_t("nav_mp3tag", "🏷️  Tag Editor (Mp3tag)"))
        self.btn_nav_mp3tag.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_mp3tag.clicked.connect(lambda: self._switch_view(2))

        self.btn_nav_similar = QPushButton(_t("nav_similar", "🔍  Trova Simili"))
        self.btn_nav_similar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_similar.clicked.connect(lambda: self._switch_view(3))

        self.btn_nav_organizer = QPushButton(_t("nav_organizer", "📂  Organizza File"))
        self.btn_nav_organizer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_organizer.clicked.connect(lambda: self._switch_view(4))

        self.btn_nav_crates = QPushButton(_t("nav_crates", "📦  Smart Crates"))
        self.btn_nav_crates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_crates.clicked.connect(lambda: self._switch_view(5))

        nav_layout.addWidget(self.btn_nav_library)
        nav_layout.addWidget(self.btn_nav_trends)
        nav_layout.addWidget(self.btn_nav_mp3tag)
        nav_layout.addWidget(self.btn_nav_similar)
        nav_layout.addWidget(self.btn_nav_organizer)
        nav_layout.addWidget(self.btn_nav_crates)
        nav_layout.addStretch()

        # Dedicated Settings button in top-right corner
        self.btn_nav_settings = QPushButton(_t("nav_settings", "⚙️  Impostazioni"))
        self.btn_nav_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_settings.clicked.connect(self._on_open_settings)
        nav_layout.addWidget(self.btn_nav_settings)

        main_layout.addWidget(self.nav_bar)

        # 2. Central View Stack (0: Libreria, 1: Top Charts, 2: Tag Editor, 3: Smart Crates, 4: Trova Simili, 5: Organizza File)
        self.view_stack = QStackedWidget(self)

        # Index 0: DJ Library Container (Filter Bar + Left Filesystem Sidebar + Table View)
        self.library_container = QWidget(self)
        lib_layout = QVBoxLayout(self.library_container)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        lib_layout.setSpacing(0)

        # High-Performance Live DJ Filter Bar & Crate Builder
        self.filter_bar = LiveFilterBar(self.db, self)
        self.filter_bar.filter_changed.connect(self._on_live_filter_changed)
        self.filter_bar.export_playlist_requested.connect(self._on_export_current_crate)
        self.filter_bar.analyze_requested.connect(self._on_toolbar_analyze_clicked)
        self.filter_bar.refresh_requested.connect(self._on_toolbar_refresh_clicked)
        lib_layout.addWidget(self.filter_bar)

        # Horizontal Splitter: Left Sidebar (Tree) and Right Table
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Dynamic Collapsible Left Sidebar (Dedicated Folder Tree / Filesystem Navigator)
        self.sidebar_widget = QWidget(self)
        sb_layout = QVBoxLayout(self.sidebar_widget)
        sb_layout.setContentsMargins(6, 6, 6, 6)
        sb_layout.setSpacing(6)

        sb_header = QHBoxLayout()
        self.sb_title = QLabel(_t("sidebar_folders", "📁 CARTELLE FILESYSTEM"))
        self.sb_title.setStyleSheet("font-weight: bold; font-size: 11px;")
        btn_clear_folder = QPushButton("✕ Reset")
        btn_clear_folder.setToolTip("Rimuovi filtro cartella")
        btn_clear_folder.clicked.connect(lambda: self.filter_bar.set_folder_filter(""))
        self.btn_collapse_sidebar = QPushButton("◀")
        self.btn_collapse_sidebar.setFixedSize(22, 22)
        self.btn_collapse_sidebar.setStyleSheet("padding: 0; font-size: 10px; font-weight: bold;")
        self.btn_collapse_sidebar.clicked.connect(self._toggle_sidebar)
        sb_header.addWidget(self.sb_title)
        sb_header.addStretch()
        sb_header.addWidget(btn_clear_folder)
        sb_header.addWidget(self.btn_collapse_sidebar)
        sb_layout.addLayout(sb_header)

        logical_root = "/Volumes" if sys.platform == "darwin" else ""
        self.folder_model = QFileSystemModel(self)
        self.folder_model.setRootPath(logical_root)
        self.folder_model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)

        self.folder_tree = QTreeView(self.sidebar_widget)
        self.folder_tree.setModel(self.folder_model)
        self.folder_tree.setRootIndex(self.folder_model.index(logical_root))
        self.folder_tree.setHeaderHidden(True)
        for col in range(1, 4):
            self.folder_tree.setColumnHidden(col, True)
        self.folder_tree.collapseAll()
        self.folder_tree.clicked.connect(self._handle_folder_selection)
        self.folder_tree.selectionModel().selectionChanged.connect(
            lambda selected, deselected: (
                self._handle_folder_selection(selected.indexes()[0])
                if selected.indexes() else None
            )
        )
        sb_layout.addWidget(self.folder_tree, 1)

        self.sidebar_widget.setMinimumWidth(180)
        self.sidebar_widget.setMaximumWidth(360)
        self.main_splitter.addWidget(self.sidebar_widget)

        # Virtual Table View (Right)
        self.table_view = QTableView(self)
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.setDragEnabled(True)
        self.table_header = self.table_view.horizontalHeader()
        self.table_header.setSectionsMovable(True)
        self.table_header.setDragEnabled(True)
        self.table_header.setStretchLastSection(True)
        self.table_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_header.customContextMenuRequested.connect(self._on_table_header_context_menu)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.activated.connect(self._on_row_double_clicked)  # Enter key loads/plays track!
        self.main_splitter.addWidget(self.table_view)

        # Restore saved table header state (order, visibility & widths) if saved
        saved_header_state = self.settings_manager.get("ui.header_state", "")
        self._header_state_restored = False
        if saved_header_state and isinstance(saved_header_state, str):
            try:
                state_bytes = QByteArray.fromHex(saved_header_state.encode("ascii"))
                if self.table_header.restoreState(state_bytes):
                    self._header_state_restored = True
            except Exception:
                self._header_state_restored = False

        if not self._header_state_restored:
            # Restore custom visible columns if user configured them
            self._custom_columns_active = bool(self.settings_manager.get("ui.custom_columns_active", False))
            if self._custom_columns_active:
                saved_cols = self.settings_manager.get("ui.visible_columns", [])
                if saved_cols and isinstance(saved_cols, list):
                    self._apply_saved_column_visibility(saved_cols)
            else:
                self._apply_default_columns()

            # Restore saved column widths if configured
            saved_widths = self.settings_manager.get("ui.column_widths", {})
            if saved_widths and isinstance(saved_widths, dict):
                self._apply_saved_column_widths(saved_widths)

        # Connect signals for interactive reordering and resizing persistence
        self.table_header.sectionMoved.connect(self._on_table_section_moved)
        self.table_header.sectionResized.connect(self._on_table_section_resized)

        self.main_splitter.setStretchFactor(0, 1)  # Left Sidebar
        self.main_splitter.setStretchFactor(1, 5)  # Right Table View

        lib_layout.addWidget(self.main_splitter, 1)
        self.view_stack.addWidget(self.library_container)

        # Index 1: Home Trends Dashboard (Top Charts)
        self.home_view = HomeTrendsView(self.db, self)
        self.home_view.play_track_requested.connect(self._on_home_play_track)
        self.home_view.find_similar_requested.connect(self._on_home_find_similar)
        self.home_view.navigate_to_library_requested.connect(lambda: self._switch_view(0))
        self.home_view.filter_genre_requested.connect(self._on_home_genre_filter_requested)
        self.home_view.open_settings_requested.connect(self._on_open_settings_to_tab)
        self.view_stack.addWidget(self.home_view)

        # Index 2: Tag Editor (Embedded Mp3tag Workspace)
        self.mp3tag_view = Mp3tagWorkspaceWindow(self.db, [], parent=self)
        self.mp3tag_view.workspace_saved.connect(self._refresh_library)
        self.mp3tag_view.close_requested.connect(lambda: self._switch_view(0))
        self.view_stack.addWidget(self.mp3tag_view)

        # Index 3: Trova Simili (Embedded Similar Tracks Workspace)
        self.similar_view = SimilarTracksView(self.db, self)
        self.similar_view.play_track_requested.connect(self._on_home_play_track)
        self.similar_view.navigate_to_library_requested.connect(lambda: self._switch_view(0))
        self.similar_view.crates_updated.connect(self._refresh_library)
        self.view_stack.addWidget(self.similar_view)

        # Index 4: Organizza File (Embedded Organizer Workspace)
        self.organizer_view = OrganizerView(parent=self)
        self.organizer_view.operation_completed.connect(self._refresh_library)
        self.organizer_view.back_requested.connect(lambda: self._switch_view(0))
        self.view_stack.addWidget(self.organizer_view)

        # Index 5: Dedicated Smart Crates Workbench
        self.crates_view = SmartCratesView(self.db, self)
        self.crates_view.play_track_requested.connect(self._on_home_play_track)
        self.crates_view.crates_updated.connect(self._refresh_library)
        self.view_stack.addWidget(self.crates_view)

        main_layout.addWidget(self.view_stack, 1)

        # Bottom Mini-Player
        self.player_widget = MiniPlayerWidget(self)
        self.player_widget.track_normalized.connect(lambda _: self._refresh_library())
        self.player_widget.directory_selected.connect(self._on_breadcrumb_directory_selected)
        main_layout.addWidget(self.player_widget)

        # Start up strictly on View 0: Libreria
        self._switch_view(0)

        # Status Bar with Dynamic Hardware Resource Monitor
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.btn_cancel_task = QPushButton(_t("btn_cancel_task", "✕ Annulla"))
        self.btn_cancel_task.setVisible(False)
        self.btn_cancel_task.setToolTip("Interrompi elaborazione in corso")
        self.btn_cancel_task.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        self.btn_cancel_task.clicked.connect(self._on_cancel_current_task)
        self.status_bar.addPermanentWidget(self.btn_cancel_task)

        self.hw_container = QWidget(self)
        hw_layout = QHBoxLayout(self.hw_container)
        hw_layout.setContentsMargins(0, 0, 4, 0)
        hw_layout.setSpacing(6)

        self.bar_cpu = HardwareProgressBar("CPU", parent=self.hw_container)
        self.bar_cpu.setToolTip(_t("status_cpu_tooltip", "Utilizzo complessivo CPU del sistema"))

        self.bar_ram = HardwareProgressBar("RAM", parent=self.hw_container)
        self.bar_ram.setToolTip(
            _t(
                "status_hw_tooltip",
                "Uso memoria RAM di sistema (Musicat a 64-bit può utilizzare tutta la memoria disponibile)."
            )
        )

        hw_layout.addWidget(self.bar_cpu)
        hw_layout.addWidget(self.bar_ram)
        self.status_bar.addPermanentWidget(self.hw_container)

        self.lbl_hw_monitor = QLabel(self)
        self.lbl_hw_monitor.setVisible(False)
        self.status_bar.showMessage(_t("ready", "Pronto"))

        self._hw_timer = QTimer(self)
        self._hw_timer.setInterval(1500)
        self._hw_timer.timeout.connect(self._update_hardware_monitor)
        self._hw_timer.start()
        self._update_hardware_monitor()
        self._update_nav_button_styles(0)

    def _update_hardware_monitor(self) -> None:
        """Refreshes hardware telemetry metrics asynchronously."""
        is_light = True
        if hasattr(self, "settings_manager"):
            is_light = (self.settings_manager.get("ui", "theme", "light") != "dark")
        cpu_pct = HardwareMonitor.get_cpu_percent()
        ram_used = HardwareMonitor.get_system_memory_used_gb()
        ram_total = HardwareMonitor.get_total_system_memory_gb()
        ram_pct = HardwareMonitor.get_system_memory_percent()

        if hasattr(self, "bar_cpu"):
            self.bar_cpu.update_load(cpu_pct, f"CPU {int(round(cpu_pct))}%", is_light=is_light)
        if hasattr(self, "bar_ram"):
            self.bar_ram.update_load(ram_pct, f"RAM {ram_used:.1f}/{ram_total:.0f} GB", is_light=is_light)

        if hasattr(self, "lbl_hw_monitor"):
            self.lbl_hw_monitor.setText(HardwareMonitor.get_status_text())

    def _handle_folder_selection(self, index: QModelIndex) -> None:
        """Handles user clicking/selecting a directory in the left filesystem tree."""
        if not hasattr(self, "folder_model"):
            return
        folder_path = self.folder_model.filePath(index)
        if not folder_path or not os.path.exists(folder_path):
            return

        if os.path.isfile(folder_path):
            folder_path = os.path.dirname(folder_path)

        norm_b = folder_path.replace("/", "\\").rstrip("\\")
        norm_f = folder_path.replace("\\", "/").rstrip("/")

        # Check if tracks in this folder exist in SQLite
        count = 0
        try:
            with self.db.get_cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM tracks 
                    WHERE filepath LIKE ? OR filepath LIKE ? 
                       OR directory LIKE ? OR directory LIKE ?
                    LIMIT 1
                    """,
                    (f"{norm_b}\\%", f"{norm_f}/%", f"{norm_b}%", f"{norm_f}%"),
                )
                row = cur.fetchone()
                if row:
                    count = row[0]
        except Exception as exc:
            MusicatLogger.warning("FOLDER_TREE", f"Error checking tracks for folder: {exc}")

        if count > 0:
            # Already indexed: filter immediately
            self.filter_bar.set_folder_filter(folder_path)
            self.status_bar.showMessage(
                _t("folder_filter_applied", "Cartella: {path} ({count} tracce)", path=folder_path, count=count),
                4000,
            )
        else:
            # Unindexed directory: auto-scan audio files in background
            self._start_folder_auto_scan(folder_path)

    def _on_folder_tree_clicked(self, index: QModelIndex) -> None:
        """Alias for _handle_folder_selection."""
        self._handle_folder_selection(index)

    def _start_folder_auto_scan(self, folder_path: str) -> None:
        """Asynchronously scans an unindexed directory and populates library view."""
        if hasattr(self, "scan_worker") and self.scan_worker.isRunning():
            self.status_bar.showMessage(_t("scan_already_running", "Scansione già in corso..."), 3000)
            return

        # Quick check if directory has any audio files
        has_audio = False
        supported_exts = {".mp3", ".flac", ".wav", ".aiff", ".aif", ".m4a", ".aac", ".ogg", ".wma"}
        try:
            for root, _, files in os.walk(folder_path):
                if any(os.path.splitext(f)[1].lower() in supported_exts for f in files):
                    has_audio = True
                    break
        except Exception:
            pass

        if not has_audio:
            self.filter_bar.set_folder_filter(folder_path)
            self.status_bar.showMessage(
                _t("folder_no_audio", "Nessun file audio trovato nella cartella: {path}", path=folder_path),
                4000,
            )
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        if hasattr(self, "btn_cancel_task"):
            self.btn_cancel_task.setVisible(True)
        self.status_bar.showMessage(f"Scansione automatica: {folder_path}...")

        self.scan_worker = BackgroundScanWorker(folder_path, self.db)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(lambda res, fp=folder_path: self._on_auto_scan_finished(res, fp))
        self.scan_worker.start()

    def _on_auto_scan_finished(self, result: Dict[str, Any], folder_path: str) -> None:
        """Handles completion of automatic folder indexing."""
        self.progress_bar.setVisible(False)
        if hasattr(self, "btn_cancel_task"):
            self.btn_cancel_task.setVisible(False)
        self._refresh_library()
        self.filter_bar.set_folder_filter(folder_path)
        self.status_bar.showMessage(
            _t(
                "auto_scan_complete",
                "Scansione completata: {found} file audio indicizzati in '{folder}'",
                found=result.get("total_found", 0),
                folder=Path(folder_path).name or folder_path,
            ),
            5000,
        )

    def _init_menu_and_toolbar(self) -> None:
        """Initializes application actions and shortcuts without cluttered redundant toolbars."""
        # Sidebar Toggle
        self.act_toggle_sb = QAction(_t("tb_sidebar", "📁 Barra laterale"), self)
        self.act_toggle_sb.setShortcut(QKeySequence("F9"))
        self.act_toggle_sb.triggered.connect(self._toggle_sidebar)
        self.addAction(self.act_toggle_sb)

        # Scan Folder
        self.act_scan = QAction(_t("tb_scan", "📂 Scansiona cartella"), self)
        self.act_scan.setShortcut(QKeySequence("Ctrl+O"))
        self.act_scan.triggered.connect(self._on_scan_folder)
        self.addAction(self.act_scan)

        # Refresh
        self.act_refresh = QAction(_t("tb_refresh", "🔄 Aggiorna"), self)
        self.act_refresh.setShortcut(QKeySequence("F5"))
        self.act_refresh.triggered.connect(self._refresh_library)
        self.addAction(self.act_refresh)

        # Dedicated Mp3tag Workspace
        self.act_mp3tag = QAction(_t("tb_mp3tag", "🏷️ Spazio Mp3tag"), self)
        self.act_mp3tag.setShortcut(QKeySequence("Ctrl+T"))
        self.act_mp3tag.triggered.connect(self._on_open_mp3tag_workspace)
        self.addAction(self.act_mp3tag)

        # Quick Tag Editor Dialog
        self.act_edit = QAction(_t("tb_quick_tag", "✏️ Tag Rapidi"), self)
        self.act_edit.setShortcut(QKeySequence("Ctrl+E"))
        self.act_edit.triggered.connect(self._on_open_tag_editor)
        self.addAction(self.act_edit)

        # Pattern Converter
        self.act_patterns = QAction(_t("tb_filename_tag", "🔀 Nome File <-> Tag"), self)
        self.act_patterns.setShortcut(QKeySequence("Ctrl+K"))
        self.act_patterns.triggered.connect(self._on_open_pattern_converter)
        self.addAction(self.act_patterns)

        # Multi-Source Reconciler
        self.act_reconcile = QAction(_t("tb_reconcile", "⚖️ Riconciliazione & Cover HD"), self)
        self.act_reconcile.setShortcut(QKeySequence("Ctrl+R"))
        self.act_reconcile.triggered.connect(self._on_open_reconciler)
        self.addAction(self.act_reconcile)

        # Acoustic Batch Analyzer
        self.act_acoustic = QAction(_t("tb_analyze", "🎵 Analizza BPM & Key"), self)
        self.act_acoustic.setShortcut(QKeySequence("Ctrl+A"))
        self.act_acoustic.triggered.connect(self._on_batch_acoustic_analysis)
        self.addAction(self.act_acoustic)

        # Audio Quality Diagnosis & Loudnorm
        self.act_quality = QAction(_t("tb_audio_quality", "🔊 Qualità Audio"), self)
        self.act_quality.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_quality.triggered.connect(self._on_action_quality_diagnosis)
        self.addAction(self.act_quality)

        # Smart Recommendations (Similar Tracks)
        self.act_similar = QAction(_t("tb_find_similar", "✨ Trova Simili"), self)
        self.act_similar.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_similar.setToolTip("Cerca tracce simili per affinità armonica, BPM e genere online e locale")
        self.act_similar.triggered.connect(self._on_action_find_similar)
        self.addAction(self.act_similar)

        # Smart Organizer
        self.act_organize = QAction(_t("tb_organizer", "📦 Organizzatore Smart"), self)
        self.act_organize.setShortcut(QKeySequence("Ctrl+S"))
        self.act_organize.triggered.connect(self._on_open_sorter)
        self.addAction(self.act_organize)

        # Settings
        self.act_settings = QAction(_t("tb_settings", "⚙️ Impostazioni"), self)
        self.act_settings.setShortcut(QKeySequence("Ctrl+,"))
        self.act_settings.triggered.connect(self._on_open_settings)
        self.addAction(self.act_settings)

        # Toggle Live Log
        self.act_log = QAction(_t("tb_live_log", "📜 Log in Tempo Reale"), self)
        self.act_log.setShortcut(QKeySequence("Ctrl+L"))
        self.act_log.triggered.connect(self._toggle_log_dock)
        self.addAction(self.act_log)

        # Stats
        self.act_stats = QAction(_t("tb_stats", "📊 Statistiche"), self)
        self.act_stats.triggered.connect(self._on_show_stats)
        self.addAction(self.act_stats)

    def _init_live_log_dock(self) -> None:
        """Initializes collapsible live logging dock at the bottom."""
        self.log_dock = QDockWidget(_t("live_log_title", "Musicat — Console di Log Live & Diagnostica"), self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)

        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(6, 4, 6, 4)
        dock_layout.setSpacing(4)

        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(8)

        # Level filter
        self.cmb_log_level = QComboBox()
        self.cmb_log_level.addItem(_t("filter_all_levels", "Tutti i Livelli (DEBUG+)"), 10)
        self.cmb_log_level.addItem(_t("filter_info", "Solo INFO, WARNING, ERROR"), 20)
        self.cmb_log_level.addItem(_t("filter_warning", "Solo WARNING & ERROR"), 30)
        self.cmb_log_level.addItem(_t("filter_error", "Solo ERROR"), 40)
        toolbar_row.addWidget(self.cmb_log_level)

        # Auto-scroll checkbox
        self.chk_log_autoscroll = QCheckBox(_t("chk_auto_scroll", "Auto-scroll"))
        self.chk_log_autoscroll.setChecked(True)
        toolbar_row.addWidget(self.chk_log_autoscroll)

        toolbar_row.addStretch()

        # Export support bundle button
        self.btn_export_logs = QPushButton(_t("btn_export_support_logs", "📦 Esporta Log per Assistenza (.zip)"))
        self.btn_export_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_logs.clicked.connect(self._on_export_support_bundle)
        toolbar_row.addWidget(self.btn_export_logs)

        # Clear button
        self.btn_clear_log = QPushButton(_t("btn_clear_log", "✕ Pulisci"))
        self.btn_clear_log.setFixedWidth(80)
        self.btn_clear_log.clicked.connect(lambda: self.log_console.clear())
        toolbar_row.addWidget(self.btn_clear_log)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(160)
        self.log_console.setFont(QFont("Consolas", 10))
        self.log_console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #121316;
                color: #cbd5e1;
                border: 1px solid #282c3c;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        dock_layout.addLayout(toolbar_row)
        dock_layout.addWidget(self.log_console)

        self.log_dock.setWidget(dock_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.setVisible(False)

        # Connect logger callback through Qt Signal
        self.log_signal.connect(self._append_log_message)
        MusicatLogger.register_gui_callback(lambda t, lvl, msg: self.log_signal.emit(t, lvl, msg))

    def _toggle_log_dock(self) -> None:
        self.log_dock.setVisible(not self.log_dock.isVisible())

    def _append_log_message(self, time_str: str, levelno: int, message: str) -> None:
        min_level = self.cmb_log_level.currentData() if hasattr(self, "cmb_log_level") else 10
        if levelno < (min_level or 10):
            return

        color = "#a0a5b8"
        if levelno >= 40:    # ERROR
            color = "#ef4444"
        elif levelno >= 30:  # WARNING
            color = "#f59e0b"
        elif levelno >= 20:  # INFO
            color = "#0ea5e9"

        html_line = f'<span style="color: #64748b;">[{time_str}]</span> <span style="color: {color};">{message}</span>'
        self.log_console.appendHtml(html_line)

        if hasattr(self, "chk_log_autoscroll") and self.chk_log_autoscroll.isChecked():
            cursor = self.log_console.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_console.setTextCursor(cursor)

    def _on_export_support_bundle(self) -> None:
        """Exports diagnostic support ZIP bundle containing logs, hardware info, and system state."""
        from datetime import datetime
        default_name = f"musicat_support_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            _t("export_logs_title", "Salva Pacchetto Log per Assistenza"),
            default_name,
            "ZIP Archives (*.zip)",
        )
        if not dest_path:
            return

        try:
            out_file = MusicatLogger.export_support_bundle(destination_zip=dest_path, db=self.db)
            QMessageBox.information(
                self,
                _t("export_logs_success_title", "Log Esportati con Successo"),
                _t(
                    "export_logs_success_msg",
                    "Il pacchetto di diagnostica è stato salvato in:\n{path}\n\nPuoi allegarlo alla richiesta di supporto o issue GitHub.",
                    path=out_file,
                ),
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore Esportazione Log", f"Impossibile creare il pacchetto log:\n{e}")

    def _init_shortcuts(self) -> None:
        """Configures DJ live performance keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.filter_bar.focus_search)
        QShortcut(QKeySequence("Ctrl+G"), self).activated.connect(self.filter_bar.focus_genre)
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(self.filter_bar.focus_bpm)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self.filter_bar._open_camelot_wheel)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.filter_bar.reset_filters)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self._on_space_pressed)
        QShortcut(QKeySequence("Ctrl+X"), self).activated.connect(self._on_cut_tracks)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._on_copy_tracks)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self._on_paste_tracks)
        QShortcut(QKeySequence("Alt+1"), self).activated.connect(lambda: self._switch_view(0))
        QShortcut(QKeySequence("Alt+2"), self).activated.connect(lambda: self._switch_view(1))
        QShortcut(QKeySequence("Alt+3"), self).activated.connect(lambda: self._switch_view(2))
        QShortcut(QKeySequence("Alt+4"), self).activated.connect(lambda: self._switch_view(3))
        QShortcut(QKeySequence("Alt+5"), self).activated.connect(lambda: self._switch_view(4))
        QShortcut(QKeySequence("Alt+6"), self).activated.connect(lambda: self._switch_view(5))
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self._on_action_find_similar)

    def _on_space_pressed(self) -> None:
        """Toggles playback on active deck or auditions selected table track."""
        if self.player_widget.current_track:
            self.player_widget.toggle_play_pause()
        else:
            selected = self._get_selected_tracks()
            if selected:
                self.player_widget.load_track(selected[0])
                self.player_widget.play()

    def _refresh_library(self) -> None:
        """Reloads tracks from SQLite, warms in-memory RAM cache and reapplies filters."""
        self.all_tracks = self.db.search_tracks(limit=100000)
        self.filter_engine.warm_cache(self.all_tracks)
        self._on_live_filter_changed(self.filter_bar.get_current_criteria())
        self.filter_bar._refresh_crates_dropdown()
        self.filter_bar.refresh_directories()
        self.filter_bar.genre_widget._refresh_completer()
        self.filter_bar.genre_widget._build_menu()
        if hasattr(self, "sidebar_tree"):
            self._populate_sidebar_tree()
        if hasattr(self, "home_view"):
            self.home_view.refresh_library_status()

        total_dur = sum(t.get("duration") or 0.0 for t in self.all_tracks)
        hours = int(total_dur // 3600)
        mins = int((total_dur % 3600) // 60)
        self.status_bar.showMessage(
            _t("library_status", "Libreria: {count} tracce ({hours}h {mins}m) | Database: {db}",
               count=f"{len(self.all_tracks):,}", hours=hours, mins=mins, db=Path(self.db.db_path).name)
        )

    def _on_live_filter_changed(self, criteria: FilterCriteria) -> None:
        """Routes filtering query to Everything MFT IPC or microsecond in-memory index."""
        if (
            criteria.query_text
            and not criteria.genres
            and criteria.target_bpm is None
            and criteria.bpm_min is None
            and criteria.bpm_max is None
            and not criteria.camelot_key
            and not criteria.harmonic_matches_only
            and criteria.year_min is None
            and criteria.year_max is None
            and criteria.rating_min is None
            and not criteria.energy_levels
            and not criteria.tags
        ):
            # Pure text search: route via OS fast search (Everything on Win, Spotlight on Mac) or SQLite FTS
            results, engine_name = SearchEngine.unified_search(criteria.query_text, self.db, limit=100000)
            self.table_model.set_tracks(results)
            self.status_bar.showMessage(
                _t("found_tracks", "Trovate {count} tracce tramite {engine}",
                   count=f"{len(results):,}", engine=engine_name)
            )
        else:
            # Complex DJ multi-attribute filter (<15ms latency in RAM)
            filtered = self.filter_engine.query(criteria, prefer_ram=True)
            self.table_model.set_tracks(filtered)
            self.status_bar.showMessage(
                _t("showing_tracks", "Visualizzate {filtered} di {total} tracce",
                   filtered=f"{len(filtered):,}", total=f"{len(self.all_tracks):,}")
            )

    def _on_export_current_crate(self) -> None:
        """Exports currently filtered tracks as an extended M3U8 playlist."""
        tracks = self.table_model._tracks
        if not tracks:
            QMessageBox.information(self, "Export Playlist", "No tracks matching current filter to export.")
            return

        default_name = f"Musicat_Crate_{len(tracks)}_tracks.m3u8"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Smart Crate Playlist",
            default_name,
            "Extended M3U8 Playlist (*.m3u8 *.m3u)",
        )
        if file_path:
            try:
                out_path = LiveFilterEngine.export_m3u(tracks, file_path)
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Successfully exported {len(tracks):,} tracks to:\n{out_path}\n\nCompatible with Rekordbox, Traktor, Serato, and Engine DJ.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Could not export playlist:\n{e}")

    def _get_selected_tracks(self) -> List[Dict[str, Any]]:
        rows = sorted(list({idx.row() for idx in self.table_view.selectionModel().selectedRows()}))
        return self.table_model.get_tracks_by_rows(rows)

    def _on_row_double_clicked(self, index) -> None:
        track = self.table_model.get_track(index.row())
        if track:
            self.player_widget.load_track(track)
            self.player_widget.play()

    def _on_scan_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Music Directory to Scan")
        if not folder:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        if hasattr(self, "btn_cancel_task"):
            self.btn_cancel_task.setVisible(True)
        self.status_bar.showMessage(f"Scanning {folder}...")

        self.scan_worker = BackgroundScanWorker(folder, self.db)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_progress(self, cur: int, total: int, path: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(cur)
        self.status_bar.showMessage(f"Indexing ({cur}/{total}): {Path(path).name}")

    def _on_scan_finished(self, result: Dict[str, Any]) -> None:
        self.progress_bar.setVisible(False)
        if hasattr(self, "btn_cancel_task"):
            self.btn_cancel_task.setVisible(False)
        self._refresh_library()
        QMessageBox.information(
            self,
            "Scan Complete",
            f"Scanned {result['total_found']} audio files.\nInserted/Updated: {result['inserted']}\nErrors: {result['errors']}",
        )

    def _on_open_tag_editor(self) -> None:
        selected = self._get_selected_tracks()
        if not selected:
            QMessageBox.information(self, "Selection", "Please select at least one track to edit.")
            return

        dlg = TagEditorDialog(selected, self)
        dlg.tags_saved.connect(self._on_tags_saved)
        dlg.exec()

    def _on_tags_saved(self, updated_tracks: List[Dict[str, Any]]) -> None:
        for tr in updated_tracks:
            self.db.update_track_tags(tr["filepath"], tr)
        self._refresh_library()

    def _on_open_pattern_converter(self) -> None:
        selected = self._get_selected_tracks()
        if not selected:
            QMessageBox.information(self, "Selection", "Please select tracks to convert.")
            return

        dlg = PatternDialog(selected, self)
        dlg.conversion_applied.connect(self._refresh_library)
        dlg.exec()

    def _on_open_reconciler(self) -> None:
        selected = self._get_selected_tracks()
        if not selected:
            QMessageBox.information(self, "Selezione", "Seleziona almeno una traccia da revisionare.")
            return

        self._open_reconciler_for_track(selected[0])

    def _open_reconciler_for_track(self, track: Dict[str, Any]) -> None:
        dlg = ReconciliationDialog(track, conflicts=track.get("_conflicts"), parent=self)
        dlg.metadata_reconciled.connect(
            lambda updated: [self.db.update_track_tags(updated["filepath"], updated), self._refresh_library()]
        )
        dlg.exec()

    def _on_cancel_current_task(self) -> None:
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.cancel()
            self.status_bar.showMessage("Annullamento analisi in corso...")
        if hasattr(self, "scan_worker") and self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.cancel()
            self.status_bar.showMessage("Annullamento scansione in corso...")

    def _on_toolbar_refresh_clicked(self) -> None:
        """Dedicated toolbar action to instantly reload the active directory or re-query SQLite library."""
        active_folder = self.filter_bar.get_active_folder() if hasattr(self.filter_bar, "get_active_folder") else None
        if active_folder and os.path.exists(active_folder) and os.path.isdir(active_folder):
            self.status_bar.showMessage(f"🔄 Aggiornamento e scansione cartella: {active_folder}...")
            self._start_folder_auto_scan(active_folder)
        else:
            self._refresh_library()
            self.status_bar.showMessage("🔄 Libreria aggiornata con successo.", 3000)

    def _on_toolbar_analyze_clicked(self) -> None:
        """Dedicated toolbar action to analyze selected tracks or current folder/view."""
        selected = self._get_selected_tracks()
        if selected:
            tracks_to_analyze = selected
        else:
            tracks_to_analyze = [t for t in self.table_model._tracks] if self.table_model._tracks else self.all_tracks

        if not tracks_to_analyze:
            self.status_bar.showMessage(
                _t("msg_select_track_or_folder", "⚠️ Seleziona almeno una traccia o una cartella da analizzare."),
                5000,
            )
            return

        self._start_async_analysis(tracks_to_analyze)

    def _start_async_analysis(self, tracks: List[Dict[str, Any]]) -> None:
        """Launches non-blocking background analysis on the given tracks."""
        if not tracks:
            return

        if self.analysis_worker and self.analysis_worker.isRunning():
            QMessageBox.warning(
                self,
                "Analisi in Corso",
                "Un'analisi è già in esecuzione in background. Attendi il completamento o clicca [Annulla].",
            )
            return

        total = len(tracks)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_cancel_task.setVisible(True)
        self.status_bar.showMessage(f"⚡ Analisi in background avviata per {total} tracce...")

        self.analysis_worker = AsyncAnalysisWorker(tracks, self.db)
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.track_completed.connect(self._on_analysis_track_completed)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.cancelled.connect(self._on_analysis_cancelled)
        self.analysis_worker.start()

    def _on_analysis_progress(self, cur: int, total: int, filename: str) -> None:
        self.progress_bar.setValue(cur)
        self.status_bar.showMessage(f"⚡ Analisi in corso ({cur}/{total}): {filename}")

    def _on_analysis_track_completed(self, track_dict: Dict[str, Any]) -> None:
        fp = track_dict.get("filepath", "")
        for idx, t in enumerate(self.table_model._tracks):
            if t.get("filepath") == fp:
                t.update(track_dict)
                top_left = self.table_model.index(idx, 0)
                bottom_right = self.table_model.index(idx, self.table_model.columnCount() - 1)
                self.table_model.dataChanged.emit(top_left, bottom_right)
                break

    def _on_analysis_finished(self, success_count: int, updated_tracks: List[Dict[str, Any]]) -> None:
        self.progress_bar.setVisible(False)
        self.btn_cancel_task.setVisible(False)
        self._refresh_library()

        total = len(updated_tracks)
        conflicting = [t for t in updated_tracks if t.get("_conflicts")]

        if conflicting:
            if len(conflicting) == 1:
                self.status_bar.showMessage(f"⚠️ Discrepanze rilevate per '{conflicting[0].get('title')}'. Apertura Riconciliazione Conflitti...", 7000)
                self._open_reconciler_for_track(conflicting[0])
            else:
                reply = QMessageBox.question(
                    self,
                    _t("reconciliation_needed_title", "Discrepanze Metadati Rilevate"),
                    _t(
                        "reconciliation_needed_prompt",
                        "Sono state rilevate discrepanze tra le fonti online per {count} tracce.\nVuoi risolvere i conflitti ora?",
                        count=len(conflicting),
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    for c_tr in conflicting:
                        self._open_reconciler_for_track(c_tr)
        elif total == 1 and updated_tracks:
            tr = updated_tracks[0]
            title = tr.get("title") or Path(tr.get("filepath", "")).name
            bpm = f"{tr.get('bpm', 0.0):.1f}" if tr.get("bpm") else "-"
            key = tr.get("camelot_key") or tr.get("musical_key") or "-"
            self.status_bar.showMessage(f"✅ Analisi completata per '{title}' (BPM: {bpm}, Key: {key})", 7000)

            reply = QMessageBox.question(
                self,
                _t("analysis_done_title", "Analisi Completata"),
                _t(
                    "analysis_done_review_prompt",
                    "Analisi completata con successo!\nBPM: {bpm} | Chiave: {musical_key}\nVuoi aprire la revisione online per cercare etichetta, anno e copertina HD?",
                    bpm=bpm,
                    musical_key=key,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._open_reconciler_for_track(tr)
        else:
            self.status_bar.showMessage(
                f"✅ Analisi completata: {success_count}/{total} tracce analizzate e tag salvati con successo.",
                8000,
            )

    def _on_analysis_cancelled(self) -> None:
        self.progress_bar.setVisible(False)
        self.btn_cancel_task.setVisible(False)
        self.status_bar.showMessage("Analisi interrotta dall'utente.", 5000)
        self._refresh_library()

    def _on_open_sorter(self) -> None:
        """Switches to integrated File Organizer workspace."""
        self._switch_view(4)

    def _on_batch_acoustic_analysis(self) -> None:
        self._on_toolbar_analyze_clicked()

    def _on_show_stats(self) -> None:
        stats = self.db.get_library_statistics()
        top_g = "\n".join([f"• {g['genre']}: {g['count']} tracks" for g in stats.get("top_genres", [])[:5]])
        top_k = ", ".join([f"{k['camelot_key']} ({k['count']})" for k in stats.get("key_distribution", [])[:6]])

        msg = (
            f"<b>Total Tracks:</b> {stats['total_tracks']:,}<br>"
            f"<b>Total Playtime:</b> {int(stats['total_duration'] // 3600)} hours<br>"
            f"<b>Unique Artists:</b> {stats['unique_artists']}<br>"
            f"<b>Analyzed BPM:</b> {stats['analyzed_bpm']} / {stats['total_tracks']}<br>"
            f"<b>Analyzed Keys:</b> {stats['analyzed_keys']} / {stats['total_tracks']}<br><br>"
            f"<b>Top Genres:</b><br>{top_g.replace(chr(10), '<br>')}<br><br>"
            f"<b>Key Distribution:</b> {top_k}"
        )
        QMessageBox.information(self, "Library Analytics", msg)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_responsive_columns(event.size().width())

    def _apply_responsive_columns(self, width: int) -> None:
        """Adapts table column visibility dynamically based on viewport width if user hasn't set custom columns."""
        if getattr(self, "_custom_columns_active", False) or getattr(self, "_header_state_restored", False):
            return
        header = getattr(self, "table_header", self.table_view.horizontalHeader())

        # Ensure non-essential/superfluous columns remain hidden by default
        hidden_by_default = {"energy_level", "lufs", "true_peak", "audio_status", "album", "label", "filepath"}
        for idx, (_, col_id) in enumerate(TrackTableModel.COLUMNS):
            if col_id in hidden_by_default and idx < header.count():
                header.setSectionHidden(idx, True)

        # Essential columns: id(0), cover(1), title(2), artist(3), remixer(4), bpm(5), camelot(6), key(7), genre(8), year(9), duration(12), bitrate(13)
        if width < 1100:
            # Compact view (< 1100px): hide Remixer (4), Musical Key (7), Bitrate (13)
            for col_idx in [4, 7, 13]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, True)
            for col_idx in [0, 1, 2, 3, 5, 6, 8, 9, 12]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, False)
        elif width < 1350:
            # Medium view: hide Remixer (4)
            for col_idx in [4]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, True)
            for col_idx in [0, 1, 2, 3, 5, 6, 7, 8, 9, 12, 13]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, False)
        else:
            # Wide view: show all essential DJ columns
            for idx, (_, col_id) in enumerate(TrackTableModel.COLUMNS):
                if col_id in DEFAULT_VISIBLE_COLUMN_IDS and idx < header.count():
                    header.setSectionHidden(idx, False)

    def _toggle_sidebar(self) -> None:
        """Toggles visibility of the left filesystem sidebar."""
        new_vis = self.sidebar_widget.isHidden()
        self.sidebar_widget.setVisible(new_vis)
        self.btn_collapse_sidebar.setText("◀" if new_vis else "▶")

    def _populate_sidebar_tree(self) -> None:
        """Populates hierarchical tree in the collapsible sidebar."""
        if not hasattr(self, "sidebar_tree"):
            return
        self.sidebar_tree.clear()

        # All Tracks item
        item_all = QTreeWidgetItem(self.sidebar_tree, [f"📚 All Tracks ({len(self.all_tracks):,})"])
        item_all.setData(0, Qt.ItemDataRole.UserRole, {"type": "all"})

        # Top Genres node
        genres_count: Dict[str, int] = {}
        camelot_count: Dict[str, int] = {}
        for t in self.all_tracks:
            g = (t.get("genre") or "").strip()
            if g:
                genres_count[g] = genres_count.get(g, 0) + 1
            k = (t.get("camelot_key") or "").strip()
            if k:
                camelot_count[k] = camelot_count.get(k, 0) + 1

        genre_root = QTreeWidgetItem(self.sidebar_tree, [f"🏷️ Genres ({len(genres_count)})"])
        genre_root.setExpanded(True)
        for g, count in sorted(genres_count.items(), key=lambda x: -x[1])[:12]:
            g_item = QTreeWidgetItem(genre_root, [f"{g} ({count})"])
            g_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "genre", "value": g})

        # Smart Crates node
        crates = self.db.get_crates()
        crates_root = QTreeWidgetItem(self.sidebar_tree, [f"🎛️ Smart Crates ({len(crates)})"])
        crates_root.setExpanded(True)
        for c in crates:
            c_item = QTreeWidgetItem(crates_root, [f"🗂️ {c['name']}"])
            c_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "crate", "value": c["name"]})

        # Camelot Keys node
        camelot_root = QTreeWidgetItem(self.sidebar_tree, ["🔑 Camelot Keys"])
        for k in sorted(camelot_count.keys()):
            k_item = QTreeWidgetItem(camelot_root, [f"{k} ({camelot_count[k]})"])
            k_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "camelot", "value": k})

    def _on_sidebar_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handles selection of sidebar items to filter the main library view."""
        try:
            if not hasattr(self, "sidebar_tree"):
                return
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data or not isinstance(data, dict):
                return
            itype = data.get("type")
            val = data.get("value")
            MusicatLogger.get_logger().info(f"[SIDEBAR_CLICK] Selezione: type={itype!r}, value={val!r}")

            if itype == "all":
                self.filter_bar.reset_filters()
            elif itype == "genre" and val:
                if not self.all_tracks:
                    self.status_bar.showMessage(f"Libreria vuota: nessuna traccia trovata per '{val}'", 4000)
                    return
                self.filter_bar.genre_widget.set_genres([val])
            elif itype == "crate" and val:
                self._switch_view(5)
                if hasattr(self, "crates_view"):
                    self.crates_view.select_crate_by_name(val)
            elif itype == "camelot" and val:
                idx = self.filter_bar.cmb_camelot.findData(val)
                if idx >= 0:
                    self.filter_bar.cmb_camelot.setCurrentIndex(idx)
                else:
                    crit = self.filter_bar.get_current_criteria()
                    crit.camelot_key = val
                    self.filter_bar.filter_changed.emit(crit)
        except Exception as exc:
            MusicatLogger.get_logger().error(f"[SIDEBAR_CLICK] Errore gestito: {exc}\n{traceback.format_exc()}")

    def _on_cut_tracks(self) -> None:
        """Cuts selected tracks to clipboard for physical moving."""
        selected = self._get_selected_tracks()
        if not selected:
            return
        paths = [t["filepath"] for t in selected if t.get("filepath")]
        if paths:
            self.file_manager.cut_files(paths)
            self.status_bar.showMessage(f"✂️ Cut {len(paths)} track(s) to clipboard. Ready to paste.")

    def _on_copy_tracks(self) -> None:
        """Copies selected tracks to clipboard for physical duplication."""
        selected = self._get_selected_tracks()
        if not selected:
            return
        paths = [t["filepath"] for t in selected if t.get("filepath")]
        if paths:
            self.file_manager.copy_files(paths)
            self.status_bar.showMessage(f"📋 Copied {len(paths)} track(s) to clipboard. Ready to paste.")

    def _on_paste_tracks(self) -> None:
        """Pastes files from clipboard into a chosen destination directory with DB sync."""
        if not self.file_manager.clipboard_files:
            sys_files = self.file_manager._get_system_clipboard_files()
            if not sys_files:
                QMessageBox.information(self, "Paste Tracks", "Clipboard is empty. Cut or copy tracks first.")
                return

        dest_dir = QFileDialog.getExistingDirectory(self, "Select Destination Folder for Paste")
        if not dest_dir:
            return

        res = self.file_manager.paste_files(dest_dir)
        msg = f"Paste complete: {len(res.processed_files)} file(s) processed."
        if res.errors:
            msg += f" (Errors: {len(res.errors)})"
        self.status_bar.showMessage(msg)
        self._refresh_library()

    def _on_open_mp3tag_workspace(self) -> None:
        """Switches to integrated Mp3tag Workbench workspace."""
        self._switch_view(2)

    def _on_open_settings(self) -> None:
        """Opens modular Preferences and Settings dialog."""
        dlg = SettingsDialog(self.settings_manager, parent=self)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.exec()

    def _on_open_settings_to_tab(self, tab_name: str) -> None:
        """Opens modular Preferences dialog directly navigated to specified category."""
        dlg = SettingsDialog(self.settings_manager, parent=self)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.set_active_category(tab_name)
        dlg.exec()

    def _on_settings_applied(self, ui_settings: Dict[str, Any]) -> None:
        """Applies updated UI configuration immediately."""
        theme_id = ui_settings.get("theme", "light")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_theme_stylesheet(theme_id))
        self._update_nav_button_styles(self.view_stack.currentIndex())
        if hasattr(self, "player_widget"):
            self.player_widget.update_theme(theme_id)
        if hasattr(self, "filter_bar"):
            self.filter_bar.update_theme(theme_id)
        if hasattr(self, "home_view") and hasattr(self.home_view, "update_theme"):
            self.home_view.update_theme(theme_id)
        if hasattr(self, "crates_view") and hasattr(self.crates_view, "update_theme"):
            self.crates_view.update_theme(theme_id)
        if hasattr(self, "similar_view") and hasattr(self.similar_view, "update_theme"):
            self.similar_view.update_theme(theme_id)
        self.status_bar.showMessage(f"Applied settings: Theme '{theme_id}'")

    def _on_table_header_context_menu(self, pos: QPoint) -> None:
        """Opens context menu to toggle column visibility when right-clicking the table header."""
        menu = QMenu(self)
        title_action = menu.addAction(_t("menu_columns_title", "Colonne Visibili"))
        title_action.setEnabled(False)
        menu.addSeparator()

        for idx, (default_name, col_id) in enumerate(TrackTableModel.COLUMNS):
            col_name = _t(f"col_{col_id}", default=default_name)
            action = menu.addAction(col_name)
            action.setCheckable(True)
            action.setChecked(not self.table_header.isSectionHidden(idx))
            action.triggered.connect(
                lambda checked, c_idx=idx, c_id=col_id: self._toggle_column_visibility(c_idx, c_id, checked)
            )

        menu.addSeparator()
        act_show_all = menu.addAction(_t("menu_columns_show_all", "Mostra Tutte le Colonne"))
        act_show_all.triggered.connect(self._show_all_columns)

        act_reset_def = menu.addAction(_t("menu_columns_reset_default", "Ripristina Colonne Predefinite"))
        act_reset_def.triggered.connect(self._reset_default_columns)

        menu.exec(self.table_header.mapToGlobal(pos))

    def _apply_default_columns(self) -> None:
        """Applies clean default view: only essential DJ columns, hiding superfluous columns, with balanced widths."""
        visible_set = set(DEFAULT_VISIBLE_COLUMN_IDS)
        for idx, (_, col_id) in enumerate(TrackTableModel.COLUMNS):
            self.table_header.setSectionHidden(idx, col_id not in visible_set)
            default_w = DEFAULT_COLUMN_WIDTHS.get(col_id, 100)
            self.table_header.resizeSection(idx, default_w)

    def _save_table_header_state(self) -> None:
        """Saves header state (column visual order, hidden sections, widths) to configuration."""
        try:
            hex_state = bytes(self.table_header.saveState().toHex().data()).decode("ascii")
            self.settings_manager.set("ui.header_state", hex_state)
            self.settings_manager.save()
        except Exception as exc:
            MusicatLogger.debug("HEADER_STATE", f"Could not save header state: {exc}")

    def _on_table_section_moved(self, logical_index: int, old_visual_index: int, new_visual_index: int) -> None:
        """Persists reordered column layout when user drags and drops columns."""
        self._save_table_header_state()

    def _toggle_column_visibility(self, col_idx: int, col_id: str, visible: bool) -> None:
        """Toggles visibility of an individual table column and saves preference."""
        visible_count = sum(
            1 for i in range(self.table_header.count()) if not self.table_header.isSectionHidden(i)
        )
        if not visible and visible_count <= 1:
            return

        self.table_header.setSectionHidden(col_idx, not visible)
        self._custom_columns_active = True
        self.settings_manager.set("ui.custom_columns_active", True)
        self._save_current_column_visibility()
        self._save_table_header_state()

    def _show_all_columns(self) -> None:
        """Shows all columns and marks custom layout active."""
        for i in range(self.table_header.count()):
            self.table_header.setSectionHidden(i, False)
        self._custom_columns_active = True
        self.settings_manager.set("ui.custom_columns_active", True)
        self._save_current_column_visibility()
        self._save_table_header_state()

    def _reset_default_columns(self) -> None:
        """Resets column visual order, visibility and widths to essential DJ defaults."""
        self._custom_columns_active = False
        self._header_state_restored = False
        # Reset visual order to logical 0..N
        for logical_idx in range(self.table_header.count()):
            cur_vis = self.table_header.visualIndex(logical_idx)
            if cur_vis != logical_idx:
                self.table_header.moveSection(cur_vis, logical_idx)

        self._apply_default_columns()
        self.settings_manager.set("ui.custom_columns_active", False)
        self._save_table_header_state()

    def _save_current_column_visibility(self) -> None:
        """Saves currently visible column IDs to configuration."""
        visible_cols = [
            col_id
            for idx, (_, col_id) in enumerate(TrackTableModel.COLUMNS)
            if not self.table_header.isSectionHidden(idx)
        ]
        self.settings_manager.set("ui.visible_columns", visible_cols)
        self.settings_manager.save()

    def _apply_saved_column_visibility(self, saved_cols: List[str]) -> None:
        """Applies saved column visibility list from configuration."""
        saved_set = set(saved_cols)
        for idx, (_, col_id) in enumerate(TrackTableModel.COLUMNS):
            is_visible = col_id in saved_set
            self.table_header.setSectionHidden(idx, not is_visible)

    def _on_table_section_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        """Saves resized column widths into configuration and updates header state."""
        if logical_index < len(TrackTableModel.COLUMNS):
            _, col_id = TrackTableModel.COLUMNS[logical_index]
            widths = self.settings_manager.get("ui.column_widths", {})
            if not isinstance(widths, dict):
                widths = {}
            widths[col_id] = new_size
            self.settings_manager.set("ui.column_widths", widths)
        self._save_table_header_state()

    def _apply_saved_column_widths(self, saved_widths: Dict[str, int]) -> None:
        """Restores saved column widths from configuration."""
        if not isinstance(saved_widths, dict):
            return
        for idx, (_, col_id) in enumerate(TrackTableModel.COLUMNS):
            if col_id in saved_widths:
                w = saved_widths[col_id]
                if isinstance(w, int) and w > 20:
                    self.table_header.resizeSection(idx, w)

    def _on_table_context_menu(self, pos: QPoint) -> None:
        selected = self._get_selected_tracks()
        menu = QMenu(self)

        if selected:
            act_play = menu.addAction(_t("ctx_play", "▶ Riproduci nel Mini-Player"))
            act_similar = menu.addAction(_t("ctx_find_similar", "✨ Trova Tracce Simili (Cosine & Library)..."))
            menu.addSeparator()
            act_cut = menu.addAction(_t("ctx_cut", "✂️ Taglia Traccia(e) (Ctrl+X)"))
            act_copy = menu.addAction(_t("ctx_copy", "📋 Copia Traccia(e) (Ctrl+C)"))
            act_paste = menu.addAction(_t("ctx_paste", "📥 Incolla Traccia(e) Qui (Ctrl+V)"))
            menu.addSeparator()
            act_mp3tag = menu.addAction(_t("ctx_mp3tag", "🏷️ Spazio Mp3tag (Ctrl+T)..."))
            act_edit = menu.addAction(_t("ctx_edit_tags", "✏️ Modifica Tag (Batch)..."))
            act_reconcile = menu.addAction(_t("ctx_reconcile", "⚖️ Riconciliazione & Cover HD..."))
            act_convert = menu.addAction(_t("ctx_patterns", "🔀 Pattern Nome File <-> Tag..."))
            act_analyze = menu.addAction(_t("ctx_analyze", "🎵 Calcola BPM & Chiave Camelot"))
            act_quality = menu.addAction(_t("ctx_quality", "🔊 Diagnosi Qualità Audio & Normalizza..."))
            act_sorter = menu.addAction(_t("ctx_sorter", "📁 Smista & Sposta in Cartella..."))
            menu.addSeparator()
            act_folder = menu.addAction(_t("ctx_show_folder", "📂 Mostra nella cartella (Show in Folder)"))
        else:
            act_paste = menu.addAction(_t("ctx_paste", "📥 Incolla Traccia(e) Qui (Ctrl+V)"))
            act_play = act_similar = act_cut = act_copy = act_mp3tag = act_edit = act_reconcile = act_convert = act_analyze = act_quality = act_sorter = act_folder = None

        action = menu.exec(self.table_view.viewport().mapToGlobal(pos))
        if not action:
            return

        if action == act_play and selected:
            self.player_widget.load_track(selected[0])
            self.player_widget.play()
        elif action == act_similar and selected:
            self._on_home_find_similar(selected[0])
        elif action == act_cut:
            self._on_cut_tracks()
        elif action == act_copy:
            self._on_copy_tracks()
        elif action == act_paste:
            self._on_paste_tracks()
        elif action == act_mp3tag:
            self._on_open_mp3tag_workspace()
        elif action == act_edit:
            self._on_open_tag_editor()
        elif action == act_reconcile:
            self._on_open_reconciler()
        elif action == act_convert:
            self._on_open_pattern_converter()
        elif action == act_analyze:
            self._on_batch_acoustic_analysis()
        elif action == act_quality and selected:
            self._on_open_quality_diagnosis(selected[0])
        elif action == act_sorter:
            self._on_open_sorter()
        elif action == act_folder and selected:
            fp = selected[0].get("filepath", "")
            if fp:
                PathResolver.show_in_file_manager(fp)

    def _on_action_quality_diagnosis(self) -> None:
        """Opens audio quality diagnosis for selected track or currently playing deck."""
        selected = self._get_selected_tracks()
        if selected:
            self._on_open_quality_diagnosis(selected[0])
        elif self.player_widget.current_track:
            self._on_open_quality_diagnosis(self.player_widget.current_track)
        else:
            QMessageBox.information(
                self,
                "Qualità Audio & Normalizzazione",
                "Seleziona una traccia dalla tabella o carica un brano nel player per avviare la diagnostica.",
            )

    def _on_open_quality_diagnosis(self, track: Dict[str, Any]) -> None:
        """Opens modal audio quality diagnosis and loudnorm dialog for given track."""
        fp = track.get("filepath", "")
        if not fp or not Path(fp).exists():
            QMessageBox.warning(self, "File Non Trovato", f"Il file audio non esiste su disco:\n{fp}")
            return
        dlg = QualityDiagnosisDialog(fp, db=self.db, parent=self)
        dlg.normalization_applied.connect(lambda _: self._refresh_library())
        dlg.exec()

    def _switch_view(self, index: int) -> None:
        """Switches between 6 workspaces in the main view stack:
        0: Libreria
        1: Top Charts (Home Trends)
        2: Tag Editor (Mp3tag)
        3: Trova Simili
        4: Organizza File
        5: Smart Crates
        """
        selected = self._get_selected_tracks()

        # State synchronization before displaying workspace
        if index == 2 and hasattr(self, "mp3tag_view"):
            tracks = selected if selected else self.all_tracks
            self.mp3tag_view.load_tracks(tracks)
        elif index == 3 and hasattr(self, "similar_view"):
            if not getattr(self.similar_view, "reference_track", None):
                ref = selected[0] if selected else (self.player_widget.current_track or None)
                if ref:
                    self.similar_view.set_reference_track(ref)
        elif index == 4 and hasattr(self, "organizer_view"):
            self.organizer_view.set_selected_tracks(selected)
        elif index == 5 and hasattr(self, "crates_view"):
            self.crates_view.refresh_crates()

        self.view_stack.setCurrentIndex(index)
        self._update_nav_button_styles(index)

        if index == 1 and hasattr(self, "home_view"):
            if hasattr(self.home_view, "ensure_loaded"):
                self.home_view.ensure_loaded()
            self.home_view.refresh_library_status()
        elif index == 5 and hasattr(self, "crates_view"):
            self.crates_view.refresh_crates()

    def _update_nav_button_styles(self, active_index: int = 0) -> None:
        """Applies adaptive styling for active/inactive navigation buttons based on current theme."""
        theme_id = self.settings_manager.get("ui", "theme", "light")
        is_light = (theme_id == "light")

        if is_light:
            btn_active = """
                QPushButton {
                    background-color: #0d6efd;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 5px 14px;
                    border: 1px solid #0b5ed7;
                    border-radius: 4px;
                }
            """
            btn_inactive = """
                QPushButton {
                    background-color: #ffffff;
                    color: #495057;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 5px 14px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #f1f3f5;
                    color: #212529;
                    border-color: #0d6efd;
                }
            """
            nav_settings_style = """
                QPushButton {
                    background-color: #f8f9fa;
                    color: #212529;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 5px 14px;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    color: #0d6efd;
                    border-color: #0d6efd;
                }
            """
            self.nav_bar.setStyleSheet("""
                QFrame#topNavBar {
                    background-color: #ffffff;
                    border-bottom: 2px solid #dee2e6;
                    padding: 4px 10px;
                }
            """)
        else:
            btn_active = """
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 5px 14px;
                    border: 1px solid #38bdf8;
                    border-radius: 4px;
                }
            """
            btn_inactive = """
                QPushButton {
                    background-color: #171924;
                    color: #94a3b8;
                    font-size: 11px;
                    padding: 5px 14px;
                    border: 1px solid #282d3f;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #212536;
                    color: #e2e8f0;
                }
            """
            nav_settings_style = """
                QPushButton {
                    background-color: #1e2230;
                    color: #e2e8f0;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 5px 14px;
                    border: 1px solid #38bdf8;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #282e42;
                    color: #38bdf8;
                }
            """
            self.nav_bar.setStyleSheet("""
                QFrame#topNavBar {
                    background-color: #0e1017;
                    border-bottom: 2px solid #1e2232;
                    padding: 4px 10px;
                }
            """)

        # Set styles for all 6 workspace buttons
        nav_buttons = [
            getattr(self, "btn_nav_library", None),     # 0: Libreria
            getattr(self, "btn_nav_trends", None),      # 1: Top Charts
            getattr(self, "btn_nav_mp3tag", None),      # 2: Tag Editor (Mp3tag)
            getattr(self, "btn_nav_similar", None),     # 3: Trova Simili
            getattr(self, "btn_nav_organizer", None),   # 4: Organizza File
            getattr(self, "btn_nav_crates", None),      # 5: Smart Crates
        ]
        for idx, btn in enumerate(nav_buttons):
            if btn:
                btn.setStyleSheet(btn_active if active_index == idx else btn_inactive)

        if hasattr(self, "btn_nav_settings"):
            self.btn_nav_settings.setStyleSheet(nav_settings_style)
        if hasattr(self, "lbl_hw_monitor"):
            if is_light:
                self.lbl_hw_monitor.setStyleSheet(
                    "color: #495057; font-size: 11px; font-weight: 600; padding: 2px 10px; "
                    "background-color: #f1f3f5; border: 1px solid #dee2e6; border-radius: 4px; margin-right: 4px;"
                )
            else:
                self.lbl_hw_monitor.setStyleSheet(
                    "color: #94a3b8; font-size: 11px; font-weight: 600; padding: 2px 10px; "
                    "background-color: #12141c; border: 1px solid #232738; border-radius: 4px; margin-right: 4px;"
                )
        if hasattr(self, "_update_hardware_monitor"):
            self._update_hardware_monitor()

    def _on_home_play_track(self, track: Dict[str, Any]) -> None:
        """Plays a track requested from Home Trends view or discovery dialog."""
        self.player_widget.load_track(track)
        self.player_widget.play()

    def _on_home_find_similar(self, track: Dict[str, Any]) -> None:
        """Sets reference track strictly from chart item and switches to integrated Similar Tracks workspace."""
        if hasattr(self, "similar_view"):
            chart_ref = {
                "title": track.get("title", ""),
                "artist": track.get("artist", ""),
                "bpm": track.get("bpm"),
                "camelot_key": track.get("camelot_key") or track.get("musical_key"),
                "genre": track.get("genre", ""),
                "filepath": track.get("filepath", ""),
            }
            self.similar_view.set_reference_track(chart_ref)
        self._switch_view(3)

    def _on_action_find_similar(self) -> None:
        """Finds similar tracks for selected library track or currently playing deck."""
        selected = self._get_selected_tracks()
        ref = selected[0] if selected else (self.player_widget.current_track or None)
        if ref and hasattr(self, "similar_view"):
            self.similar_view.set_reference_track(ref)
        self._switch_view(3)

    def _on_home_genre_filter_requested(self, genre: str) -> None:
        """Handles genre filter requests originating from Home view or cards."""
        try:
            logger = MusicatLogger.get_logger()
            logger.info(f"[MAIN_VIEW:HOME_GENRE] Ricevuta richiesta filtro genere: {genre!r}")
            if not genre or not isinstance(genre, str):
                logger.warning(f"[MAIN_VIEW:HOME_GENRE] Genere non valido: {genre!r}")
                return

            if getattr(self, "_is_filtering_genre", False):
                logger.warning("[MAIN_VIEW:HOME_GENRE] Filtro genere già in corso, evento ignorato.")
                return
            self._is_filtering_genre = True

            def apply_filter() -> None:
                try:
                    if not self.all_tracks:
                        if self.isVisible():
                            QMessageBox.information(
                                self,
                                _t("home_empty_genre_title", "Libreria Vuota per questo Genere"),
                                _t(
                                    "home_empty_genre_msg",
                                    "La tua libreria locale non contiene brani corrispondenti al genere '{genre}'.\nImporta o scansiona nuove tracce per visualizzarle.",
                                    genre=genre,
                                ),
                            )
                        else:
                            self.status_bar.showMessage(
                                _t("home_empty_genre_status", "Libreria vuota: nessuna traccia disponibile per '{genre}'", genre=genre), 4000
                            )
                        return

                    self._switch_view(0)
                    if hasattr(self, "filter_bar") and hasattr(self.filter_bar, "genre_widget"):
                        self.filter_bar.genre_widget.set_genres([genre])
                    self.status_bar.showMessage(
                        _t("genre_filter_applied", "Filtro applicato per il genere: {genre}", genre=genre), 4000
                    )
                except Exception as exc:
                    MusicatLogger.get_logger().error(f"[MAIN_VIEW:HOME_GENRE] Errore applicazione filtro: {exc}", exc_info=True)
                finally:
                    self._is_filtering_genre = False

            QTimer.singleShot(0, apply_filter)
        except Exception as exc:
            self._is_filtering_genre = False
            MusicatLogger.get_logger().error(f"[MAIN_VIEW:HOME_GENRE] Errore gestito: {exc}", exc_info=True)

    def _on_breadcrumb_directory_selected(self, directory_path: str) -> None:
        """Filters library table to directory clicked in MiniPlayer breadcrumbs."""
        self._switch_view(0)
        self.filter_bar.set_folder_filter(directory_path)

    def _retranslate_ui(self) -> None:
        """Dynamically retranslates all top-level main window components."""
        self.setWindowTitle(_t("app_title", "Musicat — DJ Catalog & Smart Organizer"))
        if hasattr(self, "btn_nav_library"):
            self.btn_nav_library.setText(_t("nav_library", "📁  Libreria"))
        if hasattr(self, "btn_nav_trends"):
            self.btn_nav_trends.setText(_t("nav_top_charts", "🔥  Top Charts"))
        if hasattr(self, "btn_nav_mp3tag"):
            self.btn_nav_mp3tag.setText(_t("nav_mp3tag", "🏷️  Tag Editor (Mp3tag)"))
        if hasattr(self, "btn_nav_crates"):
            self.btn_nav_crates.setText(_t("nav_crates", "📦  Smart Crates"))
        if hasattr(self, "btn_nav_similar"):
            self.btn_nav_similar.setText(_t("nav_similar", "🔍  Trova Simili"))
        if hasattr(self, "btn_nav_organizer"):
            self.btn_nav_organizer.setText(_t("nav_organizer", "📂  Organizza File"))
        if hasattr(self, "btn_nav_settings"):
            self.btn_nav_settings.setText(_t("nav_settings", "⚙️  Impostazioni"))
        if hasattr(self, "sb_title"):
            self.sb_title.setText(_t("sidebar_folders", "📁 CARTELLE FILESYSTEM"))
        if hasattr(self, "crates_view"):
            self.crates_view._retranslate_ui()

        if hasattr(self, "act_toggle_sb"):
            self.act_toggle_sb.setText(_t("tb_sidebar", "📁 Barra laterale"))
        if hasattr(self, "act_scan"):
            self.act_scan.setText(_t("tb_scan", "📂 Scansiona cartella"))
        if hasattr(self, "act_refresh"):
            self.act_refresh.setText(_t("tb_refresh", "🔄 Aggiorna"))
        if hasattr(self, "act_mp3tag"):
            self.act_mp3tag.setText(_t("tb_mp3tag", "🏷️ Spazio Mp3tag"))
        if hasattr(self, "act_edit"):
            self.act_edit.setText(_t("tb_quick_tag", "✏️ Tag Rapidi"))
        if hasattr(self, "act_patterns"):
            self.act_patterns.setText(_t("tb_filename_tag", "🔀 Nome File <-> Tag"))
        if hasattr(self, "act_reconcile"):
            self.act_reconcile.setText(_t("tb_reconcile", "⚖️ Riconciliazione & Cover HD"))
        if hasattr(self, "act_acoustic"):
            self.act_acoustic.setText(_t("tb_analyze", "🎵 Analizza BPM & Key"))
        if hasattr(self, "act_quality"):
            self.act_quality.setText(_t("tb_audio_quality", "🔊 Qualità Audio"))
        if hasattr(self, "act_similar"):
            self.act_similar.setText(_t("tb_find_similar", "✨ Trova Simili"))
        if hasattr(self, "act_organize"):
            self.act_organize.setText(_t("tb_organizer", "📦 Organizzatore Smart"))
        if hasattr(self, "act_settings"):
            self.act_settings.setText(_t("tb_settings", "⚙️ Impostazioni"))
        if hasattr(self, "act_log"):
            self.act_log.setText(_t("tb_live_log", "📜 Log in Tempo Reale"))
        if hasattr(self, "act_stats"):
            self.act_stats.setText(_t("tb_stats", "📊 Statistiche"))

        if hasattr(self, "log_dock"):
            self.log_dock.setWindowTitle(_t("live_log_title", "Musicat — Console di Log Live & Diagnostica"))
        if hasattr(self, "btn_export_logs"):
            self.btn_export_logs.setText(_t("btn_export_support_logs", "📦 Esporta Log per Assistenza (.zip)"))
        if hasattr(self, "btn_clear_log"):
            self.btn_clear_log.setText(_t("btn_clear_log", "✕ Pulisci"))
        if hasattr(self, "chk_log_autoscroll"):
            self.chk_log_autoscroll.setText(_t("chk_auto_scroll", "Auto-scroll"))
        if hasattr(self, "lbl_hw_monitor"):
            self.lbl_hw_monitor.setToolTip(
                _t(
                    "status_hw_tooltip",
                    "Uso CPU e memoria RAM di Musicat rispetto alla RAM totale del sistema.\n"
                    "Processo a 64-bit: Musicat può utilizzare tutta la RAM disponibile nel sistema senza limitazioni."
                )
            )
        if hasattr(self, "bar_cpu"):
            self.bar_cpu.setToolTip(_t("status_cpu_tooltip", "Utilizzo complessivo CPU del sistema"))
        if hasattr(self, "bar_ram"):
            self.bar_ram.setToolTip(
                _t(
                    "status_hw_tooltip",
                    "Uso memoria RAM di sistema (Musicat a 64-bit può utilizzare tutta la memoria disponibile)."
                )
            )

    def cleanup(self) -> None:
        """Explicitly cleans up child components, stopping threads and audio engine."""
        if hasattr(self, "_hw_timer") and self._hw_timer.isActive():
            self._hw_timer.stop()
        if hasattr(self, "home_view") and hasattr(self.home_view, "cleanup"):
            self.home_view.cleanup()
        if hasattr(self, "crates_view") and hasattr(self.crates_view, "cleanup"):
            self.crates_view.cleanup()
        if hasattr(self, "similar_view") and hasattr(self.similar_view, "cleanup"):
            self.similar_view.cleanup()
        if hasattr(self, "player_widget") and hasattr(self.player_widget, "cleanup"):
            self.player_widget.cleanup()

    def closeEvent(self, event: Any) -> None:
        """Handles application window closing, safely stopping workers and player."""
        self.cleanup()
        super().closeEvent(event)


