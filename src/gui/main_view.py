"""
Main Window for Musicat.

Central DJ Console integrating virtual track library, instant multi-attribute filters,
Voidtools Everything MFT instant search, live logging console, multi-source metadata
reconciliation, and libVLC mini-player.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QDir, QModelIndex, QPoint, Qt, QThread, QTimer, Signal
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
from .scraper_dialog import ScraperDialog
from .reconciler_dialog import ReconcilerDialog
from .analysis_dialog import AcousticAnalysisDialog
from .settings_dialog import SettingsDialog
from .mp3tag_workspace import Mp3tagWorkspaceWindow
from .views import HomeTrendsView, QualityDiagnosisDialog, SimilarTracksDialog, SmartCratesView
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
        # [Analisi / Home], [Libreria], [Tag Editor (Mp3tag)], [Smart Crates], [Trova Simili], [Organizza File], [Impostazioni]
        self.btn_nav_trends = QPushButton(_t("nav_analysis", "Analisi / Home"))
        self.btn_nav_trends.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_trends.clicked.connect(lambda: self._switch_view(1))

        self.btn_nav_library = QPushButton(_t("nav_library", "Libreria"))
        self.btn_nav_library.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_library.clicked.connect(lambda: self._switch_view(0))

        self.btn_nav_mp3tag = QPushButton(_t("nav_mp3tag", "Tag Editor (Mp3tag)"))
        self.btn_nav_mp3tag.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_mp3tag.clicked.connect(self._on_open_mp3tag_workspace)

        self.btn_nav_crates = QPushButton(_t("nav_crates", "Smart Crates"))
        self.btn_nav_crates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_crates.clicked.connect(lambda: self._switch_view(2))

        self.btn_nav_similar = QPushButton(_t("nav_similar", "Trova Simili"))
        self.btn_nav_similar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_similar.clicked.connect(self._on_action_find_similar)

        self.btn_nav_organizer = QPushButton(_t("nav_organizer", "Organizza File"))
        self.btn_nav_organizer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_organizer.clicked.connect(self._on_open_sorter)

        nav_layout.addWidget(self.btn_nav_trends)
        nav_layout.addWidget(self.btn_nav_library)
        nav_layout.addWidget(self.btn_nav_mp3tag)
        nav_layout.addWidget(self.btn_nav_crates)
        nav_layout.addWidget(self.btn_nav_similar)
        nav_layout.addWidget(self.btn_nav_organizer)
        nav_layout.addStretch()

        # Dedicated Settings button in top-right corner
        self.btn_nav_settings = QPushButton(_t("nav_settings", "Impostazioni"))
        self.btn_nav_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_settings.clicked.connect(self._on_open_settings)
        nav_layout.addWidget(self.btn_nav_settings)

        main_layout.addWidget(self.nav_bar)

        # 2. Central View Stack (0: DJ Library Track Analysis, 1: Home Trends)
        self.view_stack = QStackedWidget(self)

        # Page 0: DJ Library Container (Filter Bar + Table View + Dynamic Right Sidebar)
        self.library_container = QWidget(self)
        lib_layout = QVBoxLayout(self.library_container)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        lib_layout.setSpacing(0)

        # High-Performance Live DJ Filter Bar & Crate Builder
        self.filter_bar = LiveFilterBar(self.db, self)
        self.filter_bar.filter_changed.connect(self._on_live_filter_changed)
        self.filter_bar.export_playlist_requested.connect(self._on_export_current_crate)
        lib_layout.addWidget(self.filter_bar)

        # Horizontal Splitter: Table View on left, Dynamic Sidebar on right
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Virtual Table View (Left)
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

        # Dynamic Collapsible Right Sidebar (Dedicated Folder Tree / Filesystem Navigator)
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
        self.btn_collapse_sidebar = QPushButton("▶")
        self.btn_collapse_sidebar.setFixedSize(22, 22)
        self.btn_collapse_sidebar.setStyleSheet("padding: 0; font-size: 10px; font-weight: bold;")
        self.btn_collapse_sidebar.clicked.connect(self._toggle_sidebar)
        sb_header.addWidget(self.sb_title)
        sb_header.addStretch()
        sb_header.addWidget(btn_clear_folder)
        sb_header.addWidget(self.btn_collapse_sidebar)
        sb_layout.addLayout(sb_header)

        self.folder_model = QFileSystemModel(self)
        self.folder_model.setRootPath(QDir.rootPath())
        self.folder_model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)

        self.folder_tree = QTreeView(self.sidebar_widget)
        self.folder_tree.setModel(self.folder_model)
        self.folder_tree.setRootIndex(self.folder_model.index(QDir.rootPath()))
        self.folder_tree.setHeaderHidden(True)
        for col in range(1, 4):
            self.folder_tree.setColumnHidden(col, True)
        self.folder_tree.clicked.connect(self._on_folder_tree_clicked)
        sb_layout.addWidget(self.folder_tree, 1)

        self.sidebar_widget.setMinimumWidth(180)
        self.sidebar_widget.setMaximumWidth(360)
        self.main_splitter.addWidget(self.sidebar_widget)

        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 1)

        lib_layout.addWidget(self.main_splitter, 1)
        self.view_stack.addWidget(self.library_container)

        # Page 1: Home Trends Dashboard
        self.home_view = HomeTrendsView(self.db, self)
        self.home_view.play_track_requested.connect(self._on_home_play_track)
        self.home_view.find_similar_requested.connect(self._on_home_find_similar)
        self.home_view.navigate_to_library_requested.connect(lambda: self._switch_view(0))
        self.view_stack.addWidget(self.home_view)

        # Page 2: Dedicated Smart Crates Workbench
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

        # Start up strictly on View 0: Track Analysis / DJ Library
        self._switch_view(0)

        # Status Bar with Hardware Resource Monitor
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.lbl_hw_monitor = QLabel()
        self.lbl_hw_monitor.setStyleSheet(
            "color: #94a3b8; font-size: 11px; font-weight: 600; padding: 2px 10px; "
            "background-color: #12141c; border: 1px solid #232738; border-radius: 4px; margin-right: 4px;"
        )
        self.status_bar.addPermanentWidget(self.lbl_hw_monitor)
        self.status_bar.showMessage(_t("ready", "Pronto"))

        self._hw_timer = QTimer(self)
        self._hw_timer.setInterval(1800)
        self._hw_timer.timeout.connect(self._update_hardware_monitor)
        self._hw_timer.start()
        self._update_hardware_monitor()

    def _update_hardware_monitor(self) -> None:
        """Refreshes hardware telemetry metrics asynchronously."""
        cache_mb = self.settings_manager.get("performance", "ram_cache_mb", 512)
        disp_cache = max(2048, cache_mb)
        self.lbl_hw_monitor.setText(HardwareMonitor.get_status_text(disp_cache))

    def _on_folder_tree_clicked(self, index: QModelIndex) -> None:
        """Filters library to filesystem folder clicked in the sidebar folder tree."""
        if not hasattr(self, "folder_model"):
            return
        folder_path = self.folder_model.filePath(index)
        if folder_path and os.path.exists(folder_path):
            self.filter_bar.set_folder_filter(folder_path)

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
            self.filter_bar.lbl_search_engine.setText(engine_name)
            self.table_model.set_tracks(results)
            self.status_bar.showMessage(
                _t("found_tracks", "Trovate {count} tracce tramite {engine}",
                   count=f"{len(results):,}", engine=engine_name)
            )
        else:
            # Complex DJ multi-attribute filter (<15ms latency in RAM)
            self.filter_bar.lbl_search_engine.setText("Live RAM Index (<15ms)")
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
        """Toggles visibility of the right sidebar."""
        new_vis = self.sidebar_widget.isHidden()
        self.sidebar_widget.setVisible(new_vis)
        self.btn_collapse_sidebar.setText("▶" if new_vis else "◀")

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
        if not hasattr(self, "sidebar_tree"):
            return
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
            idx = self.filter_bar.cmb_crates.findData(val)
            if idx < 0:
                idx = self.filter_bar.cmb_crates.findText(val)
            if idx >= 0:
                self.filter_bar.cmb_crates.setCurrentIndex(idx)
        elif itype == "camelot" and val:
            idx = self.filter_bar.cmb_camelot.findData(val)
            if idx >= 0:
                self.filter_bar.cmb_camelot.setCurrentIndex(idx)
            else:
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
        theme_id = ui_settings.get("theme", "light")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_theme_stylesheet(theme_id))
        self._update_nav_button_styles(self.view_stack.currentIndex())
        if hasattr(self, "player_widget"):
            self.player_widget.update_theme(theme_id)
        self.status_bar.showMessage(f"Applied settings: Theme '{theme_id}'")

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
        """Switches between DJ Library (0), Home Trends (1), and Smart Crates (2)."""
        self.view_stack.setCurrentIndex(index)
        self._update_nav_button_styles(index)
        if index == 1 and hasattr(self, "home_view"):
            self.home_view.refresh_library_status()
        elif index == 2 and hasattr(self, "crates_view"):
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
            nav_action_style = """
                QPushButton {
                    background-color: #ffffff;
                    color: #212529;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 5px 12px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #f1f3f5;
                    color: #0d6efd;
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
            nav_action_style = """
                QPushButton {
                    background-color: #161822;
                    color: #cbd5e1;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 5px 12px;
                    border: 1px solid #282d3f;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #212536;
                    color: #ffffff;
                    border-color: #38bdf8;
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

        # Set styles for view buttons
        if hasattr(self, "btn_nav_library"):
            self.btn_nav_library.setStyleSheet(btn_active if active_index == 0 else btn_inactive)
        if hasattr(self, "btn_nav_trends"):
            self.btn_nav_trends.setStyleSheet(btn_active if active_index == 1 else btn_inactive)
        if hasattr(self, "btn_nav_crates"):
            self.btn_nav_crates.setStyleSheet(btn_active if active_index == 2 else btn_inactive)

        # Set styles for macro actions
        if hasattr(self, "btn_nav_mp3tag"):
            self.btn_nav_mp3tag.setStyleSheet(nav_action_style)
        if hasattr(self, "btn_nav_similar"):
            self.btn_nav_similar.setStyleSheet(nav_action_style)
        if hasattr(self, "btn_nav_organizer"):
            self.btn_nav_organizer.setStyleSheet(nav_action_style)
        if hasattr(self, "btn_nav_settings"):
            self.btn_nav_settings.setStyleSheet(nav_settings_style)

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

    def _retranslate_ui(self) -> None:
        """Dynamically retranslates all top-level main window components."""
        self.setWindowTitle(_t("app_title", "Musicat — DJ Catalog & Smart Organizer"))
        if hasattr(self, "btn_nav_trends"):
            self.btn_nav_trends.setText(_t("nav_analysis", "⚡ Analisi / Home"))
        if hasattr(self, "btn_nav_library"):
            self.btn_nav_library.setText(_t("nav_library", "🎵 Libreria"))
        if hasattr(self, "btn_nav_mp3tag"):
            self.btn_nav_mp3tag.setText(_t("nav_mp3tag", "🏷️ Tag Editor (Mp3tag)"))
        if hasattr(self, "btn_nav_crates"):
            self.btn_nav_crates.setText(_t("nav_crates", "🎛️ Smart Crates"))
        if hasattr(self, "btn_nav_similar"):
            self.btn_nav_similar.setText(_t("nav_similar", "✨ Trova Simili"))
        if hasattr(self, "btn_nav_organizer"):
            self.btn_nav_organizer.setText(_t("nav_organizer", "📦 Organizza File"))
        if hasattr(self, "btn_nav_settings"):
            self.btn_nav_settings.setText(_t("nav_settings", "⚙️ Impostazioni"))
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
