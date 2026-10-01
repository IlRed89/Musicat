"""
Main Window for Musicat.

Central DJ Console integrating virtual track library, instant multi-attribute filters,
Voidtools Everything MFT instant search, live logging console, multi-source metadata
reconciliation, and libVLC mini-player.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
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
from ..core.search_factory import SearchEngine, EverythingSearchEngine
from ..core.filter_engine import FilterCriteria, LiveFilterEngine
from ..audio.analyzer import AcousticAnalyzer
from .table_model import TrackTableModel
from .player_widget import MiniPlayerWidget
from .live_filters import LiveFilterBar, CamelotWheelDialog
from .tag_editor_dialog import TagEditorDialog
from .sorter_dialog import SorterDialog
from .pattern_dialog import PatternDialog
from .scraper_dialog import ScraperDialog
from .reconciler_dialog import ReconcilerDialog
from .analysis_dialog import AcousticAnalysisDialog
from .settings_dialog import SettingsDialog
from .mp3tag_workspace import Mp3tagWorkspaceWindow
from .views import HomeTrendsView, QualityDiagnosisDialog, SimilarTracksDialog
from .styles import get_theme_stylesheet


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


class BackgroundAnalysisWorker(QThread):
    """Background worker thread for bulk acoustic analysis (BPM & Camelot Key)."""

    progress = Signal(int, int, str)
    finished = Signal(int)

    def __init__(self, tracks: List[Dict[str, Any]], db: Database) -> None:
        super().__init__()
        self.tracks = tracks
        self.db = db
        self._is_cancelled = False

    def run(self) -> None:
        total = len(self.tracks)
        success = 0
        from ..tags.editor import AudioTagEditor

        for idx, tr in enumerate(self.tracks):
            if self._is_cancelled:
                break
            fp = tr.get("filepath", "")
            self.progress.emit(idx + 1, total, Path(fp).name)
            try:
                profile = AcousticAnalyzer.analyze_file(fp)
                updates = {
                    "bpm": profile.bpm,
                    "musical_key": profile.musical_key,
                    "camelot_key": profile.camelot_key,
                }
                # Write to physical tags
                AudioTagEditor.write_metadata(fp, updates)
                # Write to SQLite
                self.db.update_track_tags(fp, updates)
                success += 1
            except Exception:
                pass

        self.finished.emit(success)

    def cancel(self) -> None:
        self._is_cancelled = True


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

        self.setWindowTitle("Musicat - DJ Catalog & Smart Organizer")
        self.resize(1300, 820)

        self._init_ui()
        self._init_shortcuts()
        self._init_menu_and_toolbar()
        self._init_live_log_dock()
        self._refresh_library()

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top View Navigation Bar (Home Trends vs DJ Library)
        self.nav_bar = QFrame(self)
        self.nav_bar.setStyleSheet("""
            QFrame {
                background-color: #0d0f16;
                border-bottom: 2px solid #1e2232;
                padding: 4px 10px;
            }
        """)
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(10, 4, 10, 4)
        nav_layout.setSpacing(8)

        self.btn_nav_library = QPushButton("🎵 DJ Library & Crates")
        self.btn_nav_library.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_library.clicked.connect(lambda: self._switch_view(0))

        self.btn_nav_trends = QPushButton("🏠 Home Trends & Top Charts")
        self.btn_nav_trends.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_trends.clicked.connect(lambda: self._switch_view(1))

        nav_layout.addWidget(self.btn_nav_library)
        nav_layout.addWidget(self.btn_nav_trends)
        nav_layout.addStretch()

        main_layout.addWidget(self.nav_bar)

        # 2. Central View Stack (0: DJ Library, 1: Home Trends)
        self.view_stack = QStackedWidget(self)

        # Page 0: DJ Library Container (Filter Bar + Sidebar + Table View)
        self.library_container = QWidget(self)
        lib_layout = QVBoxLayout(self.library_container)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        lib_layout.setSpacing(0)

        # High-Performance Live DJ Filter Bar & Crate Builder
        self.filter_bar = LiveFilterBar(self.db, self)
        self.filter_bar.filter_changed.connect(self._on_live_filter_changed)
        self.filter_bar.export_playlist_requested.connect(self._on_export_current_crate)
        lib_layout.addWidget(self.filter_bar)

        # Horizontal Splitter for Collapsible Sidebar + Table View
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Collapsible Left Sidebar (Folders & Crates Tree)
        self.sidebar_widget = QWidget(self)
        sb_layout = QVBoxLayout(self.sidebar_widget)
        sb_layout.setContentsMargins(6, 4, 4, 4)
        sb_layout.setSpacing(4)

        sb_header = QHBoxLayout()
        sb_title = QLabel("📁 LIBRERIA & CRATES")
        sb_title.setStyleSheet("font-weight: bold; color: #00d2ff; font-size: 11px;")
        self.btn_collapse_sidebar = QPushButton("◀")
        self.btn_collapse_sidebar.setFixedSize(22, 22)
        self.btn_collapse_sidebar.setStyleSheet("padding: 0; font-size: 10px;")
        self.btn_collapse_sidebar.clicked.connect(self._toggle_sidebar)
        sb_header.addWidget(sb_title)
        sb_header.addStretch()
        sb_header.addWidget(self.btn_collapse_sidebar)
        sb_layout.addLayout(sb_header)

        self.sidebar_tree = QTreeWidget(self)
        self.sidebar_tree.setHeaderHidden(True)
        self.sidebar_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #14161f;
                border: 1px solid #282c3c;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 4px 6px;
                color: #cbd5e1;
            }
            QTreeWidget::item:selected {
                background-color: #00d2ff;
                color: #0b0c10;
                font-weight: bold;
            }
        """)
        self.sidebar_tree.itemClicked.connect(self._on_sidebar_item_clicked)
        sb_layout.addWidget(self.sidebar_tree)

        self.sidebar_widget.setMinimumWidth(160)
        self.sidebar_widget.setMaximumWidth(320)
        self.main_splitter.addWidget(self.sidebar_widget)

        # Virtual Table View
        self.table_view = QTableView(self)
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.activated.connect(self._on_row_double_clicked)  # Enter key loads/plays track!

        self.main_splitter.addWidget(self.table_view)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 5)

        lib_layout.addWidget(self.main_splitter, 1)
        self.view_stack.addWidget(self.library_container)

        # Page 1: Home Trends Dashboard
        self.home_view = HomeTrendsView(self.db, self)
        self.home_view.play_track_requested.connect(self._on_home_play_track)
        self.home_view.find_similar_requested.connect(self._on_home_find_similar)
        self.view_stack.addWidget(self.home_view)

        main_layout.addWidget(self.view_stack, 1)

        # Bottom Mini-Player
        self.player_widget = MiniPlayerWidget(self)
        self.player_widget.track_normalized.connect(lambda _: self._refresh_library())
        self.player_widget.directory_selected.connect(self._on_breadcrumb_directory_selected)
        main_layout.addWidget(self.player_widget)

        self._switch_view(0)

        # Status Bar
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.showMessage("Ready")

    def _init_menu_and_toolbar(self) -> None:
        tb = self.addToolBar("Main Controls")
        tb.setMovable(False)

        # Sidebar Toggle
        self.act_toggle_sb = QAction("📁 Sidebar", self)
        self.act_toggle_sb.setShortcut(QKeySequence("F9"))
        self.act_toggle_sb.triggered.connect(self._toggle_sidebar)
        tb.addAction(self.act_toggle_sb)

        # Scan Folder
        act_scan = QAction("📂 Scan Folder", self)
        act_scan.setShortcut(QKeySequence("Ctrl+O"))
        act_scan.triggered.connect(self._on_scan_folder)
        tb.addAction(act_scan)

        # Refresh
        act_refresh = QAction("🔄 Refresh", self)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self._refresh_library)
        tb.addAction(act_refresh)

        tb.addSeparator()

        # Dedicated Mp3tag Workspace
        act_mp3tag = QAction("🏷️ Mp3tag Workspace", self)
        act_mp3tag.setShortcut(QKeySequence("Ctrl+T"))
        act_mp3tag.triggered.connect(self._on_open_mp3tag_workspace)
        tb.addAction(act_mp3tag)

        # Quick Tag Editor Dialog
        act_edit = QAction("✏️ Quick Tag", self)
        act_edit.setShortcut(QKeySequence("Ctrl+E"))
        act_edit.triggered.connect(self._on_open_tag_editor)
        tb.addAction(act_edit)

        # Pattern Converter
        act_patterns = QAction("🔀 Filename <-> Tag", self)
        act_patterns.setShortcut(QKeySequence("Ctrl+K"))
        act_patterns.triggered.connect(self._on_open_pattern_converter)
        tb.addAction(act_patterns)

        # Multi-Source Reconciler
        act_reconcile = QAction("⚖️ Reconciler & HD Cover", self)
        act_reconcile.setShortcut(QKeySequence("Ctrl+R"))
        act_reconcile.triggered.connect(self._on_open_reconciler)
        tb.addAction(act_reconcile)

        # Acoustic Batch Analyzer
        act_acoustic = QAction("🎵 Analyze BPM & Key", self)
        act_acoustic.setShortcut(QKeySequence("Ctrl+A"))
        act_acoustic.triggered.connect(self._on_batch_acoustic_analysis)
        tb.addAction(act_acoustic)

        # Audio Quality Diagnosis & Loudnorm
        act_quality = QAction("🔊 Audio Quality", self)
        act_quality.setShortcut(QKeySequence("Ctrl+Q"))
        act_quality.triggered.connect(self._on_action_quality_diagnosis)
        tb.addAction(act_quality)

        # Smart Recommendations (Similar Tracks)
        act_similar = QAction("✨ Trova Simili", self)
        act_similar.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_similar.setToolTip("Cerca tracce simili per affinità armonica, BPM e genere online e locale")
        act_similar.triggered.connect(self._on_action_find_similar)
        tb.addAction(act_similar)

        tb.addSeparator()

        # Smart Organizer
        act_organize = QAction("📦 Smart Organizer", self)
        act_organize.setShortcut(QKeySequence("Ctrl+S"))
        act_organize.triggered.connect(self._on_open_sorter)
        tb.addAction(act_organize)

        # Settings
        act_settings = QAction("⚙️ Impostazioni", self)
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self._on_open_settings)
        tb.addAction(act_settings)

        # Toggle Live Log
        act_log = QAction("📜 Live Log", self)
        act_log.setShortcut(QKeySequence("Ctrl+L"))
        act_log.triggered.connect(self._toggle_log_dock)
        tb.addAction(act_log)

        # Stats
        act_stats = QAction("📊 Stats", self)
        act_stats.triggered.connect(self._on_show_stats)
        tb.addAction(act_stats)

    def _init_live_log_dock(self) -> None:
        """Initializes collapsible live logging dock at the bottom."""
        self.log_dock = QDockWidget("Musicat Live System Log", self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)

        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(6, 4, 6, 4)
        dock_layout.setSpacing(4)

        toolbar_row = QHBoxLayout()
        btn_clear = QPushButton("Clear Log")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(lambda: self.log_console.clear())
        toolbar_row.addWidget(btn_clear)
        toolbar_row.addStretch()

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        self.log_console.setFont(QFont("Consolas", 10))
        self.log_console.setStyleSheet("background-color: #0e0f12; color: #a0a5b8; border: 1px solid #232631;")

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
        color = "#a0a5b8"
        if levelno >= 40:  # ERROR
            color = "#ff4d4f"
        elif levelno >= 30:  # WARNING
            color = "#faad14"
        elif levelno >= 20:  # INFO
            color = "#00d2ff"

        html_line = f'<span style="color: #636878;">[{time_str}]</span> <span style="color: {color};">{message}</span>'
        self.log_console.appendHtml(html_line)

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
        self._populate_sidebar_tree()
        if hasattr(self, "home_view"):
            self.home_view.refresh_library_status()

        total_dur = sum(t.get("duration") or 0.0 for t in self.all_tracks)
        hours = int(total_dur // 3600)
        mins = int((total_dur % 3600) // 60)
        self.status_bar.showMessage(
            f"Library: {len(self.all_tracks):,} tracks ({hours}h {mins}m) | Database: {Path(self.db.db_path).name}"
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
            self.filter_bar.lbl_search_engine.setText(engine_name)
            self.table_model.set_tracks(results)
            self.status_bar.showMessage(f"Found {len(results):,} tracks via {engine_name}")
        else:
            # Complex DJ multi-attribute filter (<15ms latency in RAM)
            self.filter_bar.lbl_search_engine.setText("Live RAM Index (<15ms)")
            filtered = self.filter_engine.query(criteria, prefer_ram=True)
            self.table_model.set_tracks(filtered)
            self.status_bar.showMessage(f"Showing {len(filtered):,} of {len(self.all_tracks):,} tracks")

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
            QMessageBox.information(self, "Selection", "Please select a track to reconcile.")
            return

        dlg = ReconcilerDialog(selected[0], self)
        dlg.metadata_reconciled.connect(lambda updated: [self.db.update_track_tags(updated["filepath"], updated), self._refresh_library()])
        dlg.exec()

    def _on_open_sorter(self) -> None:
        selected = self._get_selected_tracks()
        dlg = SorterDialog(selected, self)
        dlg.operation_completed.connect(self._refresh_library)
        dlg.exec()

    def _on_batch_acoustic_analysis(self) -> None:
        selected = self._get_selected_tracks()
        tracks_to_analyze = selected if selected else self.all_tracks

        if not tracks_to_analyze:
            QMessageBox.information(self, "Libreria Vuota", "Nessuna traccia disponibile da analizzare.")
            return

        dlg = AcousticAnalysisDialog(tracks_to_analyze, self.db, self)
        dlg.exec()
        self._refresh_library()

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
        """Adapts table column visibility dynamically based on viewport width."""
        header = self.table_view.horizontalHeader()
        if width < 1100:
            # Compact view (< 1100px): hide secondary columns (Remixer, Key, Label, Bitrate, Energy, LUFS, True Peak, Path)
            for col_idx in [4, 7, 11, 13, 14, 15, 16, 18]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, True)
            for col_idx in [0, 1, 2, 3, 5, 6, 8, 9, 10, 12, 17]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, False)
        elif width < 1350:
            # Medium view: hide Remixer, Musical Key, and Path
            for col_idx in [4, 7, 18]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, True)
            for col_idx in [0, 1, 2, 3, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]:
                if col_idx < header.count():
                    header.setSectionHidden(col_idx, False)
        else:
            # Wide view: show all columns
            for col_idx in range(header.count()):
                header.setSectionHidden(col_idx, False)

    def _toggle_sidebar(self) -> None:
        """Toggles visibility of the left sidebar."""
        new_vis = not self.sidebar_widget.isVisible()
        self.sidebar_widget.setVisible(new_vis)
        self.btn_collapse_sidebar.setText("◀" if new_vis else "▶")
        self.act_toggle_sb.setText("📁 Sidebar [Show]" if not new_vis else "📁 Sidebar [Hide]")

    def _populate_sidebar_tree(self) -> None:
        """Populates hierarchical tree in the collapsible sidebar."""
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
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        itype = data.get("type")
        val = data.get("value")

        if itype == "all":
            self.filter_bar.reset_filters()
        elif itype == "genre" and val:
            self.filter_bar.genre_widget.set_selected_genres([val])
        elif itype == "crate" and val:
            idx = self.filter_bar.cb_crates.findText(val)
            if idx >= 0:
                self.filter_bar.cb_crates.setCurrentIndex(idx)
        elif itype == "camelot" and val:
            self.filter_bar.btn_camelot.setText(f"🔑 Key: {val}")
            crit = self.filter_bar.get_current_criteria()
            crit.camelot_key = val
            self.filter_bar.filter_changed.emit(crit)

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
        """Launches dedicated Mp3tag Workbench workspace window."""
        selected = self._get_selected_tracks()
        tracks_to_edit = selected if selected else self.all_tracks
        self._mp3tag_window = Mp3tagWorkspaceWindow(self.db, tracks_to_edit, parent=self)
        self._mp3tag_window.workspace_saved.connect(self._refresh_library)
        self._mp3tag_window.show()

    def _on_open_settings(self) -> None:
        """Opens modular Preferences and Settings dialog."""
        dlg = SettingsDialog(self.settings_manager, parent=self)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.exec()

    def _on_settings_applied(self, ui_settings: Dict[str, Any]) -> None:
        """Applies updated UI configuration immediately."""
        theme_id = ui_settings.get("theme", "dark_dj")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_theme_stylesheet(theme_id))
        self.status_bar.showMessage(f"Applied settings: Theme '{theme_id}'")

    def _on_table_context_menu(self, pos: QPoint) -> None:
        selected = self._get_selected_tracks()
        menu = QMenu(self)

        if selected:
            act_play = menu.addAction("▶ Play in Mini-Player")
            act_similar = menu.addAction("✨ Trova Tracce Simili (Cosine & Library)...")
            menu.addSeparator()
            act_cut = menu.addAction("✂️ Cut Track(s) (Ctrl+X)")
            act_copy = menu.addAction("📋 Copy Track(s) (Ctrl+C)")
            act_paste = menu.addAction("📥 Paste Track(s) Here (Ctrl+V)")
            menu.addSeparator()
            act_mp3tag = menu.addAction("🏷️ Open in Mp3tag Workbench (Ctrl+T)...")
            act_edit = menu.addAction("✏️ Edit Tags (Batch)...")
            act_reconcile = menu.addAction("⚖️ Reconcile Multi-Source Metadata & HD Cover...")
            act_convert = menu.addAction("🔀 Filename <-> Tag Patterns...")
            act_analyze = menu.addAction("🎵 Calculate BPM & Camelot Key")
            act_quality = menu.addAction("🔊 Diagnosi Qualità Audio & Normalizza...")
            act_sorter = menu.addAction("📁 Organize & Dispatch to Folder...")
            menu.addSeparator()
            act_folder = menu.addAction("📂 Mostra nella cartella (Show in Folder)")
        else:
            act_paste = menu.addAction("📥 Paste Track(s) Here (Ctrl+V)")
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
        """Switches between DJ Library (0) and Home Trends (1)."""
        self.view_stack.setCurrentIndex(index)
        btn_active = """
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 14px;
                border: 1px solid #38bdf8;
                border-radius: 4px;
            }
        """
        btn_inactive = """
            QPushButton {
                background-color: #171924;
                color: #94a3b8;
                font-size: 11px;
                padding: 4px 14px;
                border: 1px solid #282d3f;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #212536;
                color: #e2e8f0;
            }
        """
        if index == 0:
            self.btn_nav_library.setStyleSheet(btn_active)
            self.btn_nav_trends.setStyleSheet(btn_inactive)
        else:
            self.btn_nav_library.setStyleSheet(btn_inactive)
            self.btn_nav_trends.setStyleSheet(btn_active)
            if hasattr(self, "home_view"):
                self.home_view.refresh_library_status()

    def _on_home_play_track(self, track: Dict[str, Any]) -> None:
        """Plays a track requested from Home Trends view or discovery dialog."""
        self.player_widget.load_track(track)
        self.player_widget.play()

    def _on_home_find_similar(self, track: Dict[str, Any]) -> None:
        """Opens Similar Tracks recommendation dialog for track."""
        dlg = SimilarTracksDialog(track, db=self.db, parent=self)
        dlg.play_requested.connect(self._on_home_play_track)
        dlg.exec()

    def _on_action_find_similar(self) -> None:
        """Finds similar tracks for selected library track or currently playing deck."""
        selected = self._get_selected_tracks()
        if selected:
            self._on_home_find_similar(selected[0])
        elif self.player_widget.current_track:
            self._on_home_find_similar(self.player_widget.current_track)
        else:
            QMessageBox.information(
                self,
                "Trova Tracce Simili",
                "Seleziona una traccia dalla tabella o carica un brano nel player per cercare tracce simili.",
            )

    def _on_breadcrumb_directory_selected(self, directory_path: str) -> None:
        """Filters library table to directory clicked in MiniPlayer breadcrumbs."""
        self._switch_view(0)
        self.filter_bar.set_folder_filter(directory_path)
