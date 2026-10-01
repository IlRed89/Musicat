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
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QShortcut
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
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..core.db import Database
from ..core.path_resolver import PathResolver
from ..core.scanner import LibraryScanner
from ..core.logger import MusicatLogger
from ..core.everything_search import EverythingSearchEngine
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
        self.filter_engine = LiveFilterEngine(self.db)
        self.table_model = TrackTableModel()
        self.all_tracks: List[Dict[str, Any]] = []

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

        # High-Performance Live DJ Filter Bar & Crate Builder
        self.filter_bar = LiveFilterBar(self.db, self)
        self.filter_bar.filter_changed.connect(self._on_live_filter_changed)
        self.filter_bar.export_playlist_requested.connect(self._on_export_current_crate)
        main_layout.addWidget(self.filter_bar)

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

        main_layout.addWidget(self.table_view, 1)

        # Bottom Mini-Player
        self.player_widget = MiniPlayerWidget(self)
        main_layout.addWidget(self.player_widget)

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

        # Tag Editor
        act_edit = QAction("🏷️ Tag Editor", self)
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

        tb.addSeparator()

        # Smart Organizer
        act_organize = QAction("📁 Smart Organizer", self)
        act_organize.setShortcut(QKeySequence("Ctrl+S"))
        act_organize.triggered.connect(self._on_open_sorter)
        tb.addAction(act_organize)

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
        self.filter_bar.genre_widget._refresh_completer()
        self.filter_bar.genre_widget._build_menu()

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
            # Pure text search: route via Everything MFT / SQLite FTS
            results, engine_name = EverythingSearchEngine.unified_search(criteria.query_text, self.db, limit=100000)
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
            QMessageBox.information(self, "Empty", "No tracks available to analyze.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Acoustic Analysis",
            f"Run BPM & Camelot Key detection on {len(tracks_to_analyze)} tracks?\nThis will analyze audio envelopes and save BPM & Key to file tags.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(tracks_to_analyze))
        self.progress_bar.setValue(0)

        self.analysis_worker = BackgroundAnalysisWorker(tracks_to_analyze, self.db)
        self.analysis_worker.progress.connect(
            lambda cur, tot, name: [self.progress_bar.setValue(cur), self.status_bar.showMessage(f"Analyzing ({cur}/{tot}): {name}")]
        )
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.start()

    def _on_analysis_finished(self, success_count: int) -> None:
        self.progress_bar.setVisible(False)
        self._refresh_library()
        QMessageBox.information(self, "Analysis Finished", f"Acoustic analysis complete!\nAnalyzed: {success_count} tracks.")

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

    def _on_table_context_menu(self, pos: QPoint) -> None:
        selected = self._get_selected_tracks()
        if not selected:
            return

        menu = QMenu(self)
        act_play = menu.addAction("▶ Play in Mini-Player")
        act_edit = menu.addAction("🏷️ Edit Tags (Batch)...")
        act_reconcile = menu.addAction("⚖️ Reconcile Multi-Source Metadata & HD Cover...")
        act_convert = menu.addAction("🔀 Filename <-> Tag Patterns...")
        act_analyze = menu.addAction("🎵 Calculate BPM & Camelot Key")
        act_sorter = menu.addAction("📁 Organize & Dispatch to Folder...")
        menu.addSeparator()
        act_folder = menu.addAction("📂 Open in Windows Explorer")

        action = menu.exec(self.table_view.viewport().mapToGlobal(pos))
        if action == act_play:
            self.player_widget.load_track(selected[0])
            self.player_widget.play()
        elif action == act_edit:
            self._on_open_tag_editor()
        elif action == act_reconcile:
            self._on_open_reconciler()
        elif action == act_convert:
            self._on_open_pattern_converter()
        elif action == act_analyze:
            self._on_batch_acoustic_analysis()
        elif action == act_sorter:
            self._on_open_sorter()
        elif action == act_folder:
            fp = selected[0].get("filepath", "")
            if fp and Path(fp).exists():
                os.system(f'explorer /select,"{os.path.normpath(fp)}"')
