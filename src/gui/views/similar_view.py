"""
Embedded Similar Tracks Workspace View for Musicat.
Provides real-time local acoustic affinity matching and online discovery,
embedded directly into the main window QStackedWidget without modal popups.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QPoint, QRect, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.db import Database
from ...core.i18n import _t
from ...core.path_resolver import PathResolver
from ...scrapers.similarity_engine import (
    LocalAffinityCalculator,
    SimilarityEngine,
    SimilarityResult,
    SimilarTrackRecommendation,
)
from .similar_dialog import AffinityBadgeWidget, SimilarSearchWorker


class SimilarTracksView(QWidget):
    """Integrated Similar Tracks Workspace View for Musicat."""

    play_track_requested = Signal(dict)
    navigate_to_library_requested = Signal()
    crates_updated = Signal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.reference_track: Optional[Dict[str, Any]] = None
        self.similarity_result: Optional[SimilarityResult] = None
        self._worker: Optional[SimilarSearchWorker] = None
        self.current_theme = "light"

        self._init_ui()
        self.update_theme("light")

    def _init_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. Empty State Banner (Shown when no track is selected yet)
        # -------------------------------------------------------------
        self.empty_card = QFrame()
        self.empty_card.setObjectName("similarEmptyCard")
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setContentsMargins(30, 40, 30, 40)
        empty_layout.setSpacing(14)

        icon_empty = QLabel("🎯")
        icon_empty.setStyleSheet("font-size: 48px;")
        icon_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_empty)

        title_empty = QLabel(_t("similar_empty_title", "Trova Tracce Simili (Mix Armonico & Affinità Acustica)"))
        title_empty.setStyleSheet("font-size: 16px; font-weight: bold; color: #0d6efd;")
        title_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title_empty)

        desc_empty = QLabel(
            _t(
                "similar_empty_desc",
                "Seleziona un brano dalla Libreria o avvia la riproduzione nel deck.\n"
                "Musicat cercherà istantaneamente tracce compatibili per BPM, Ruota Camelot e affinità timbrica "
                "nella tua collezione locale e su Cosine.club."
            )
        )
        desc_empty.setStyleSheet("color: #6c757d; font-size: 12px;")
        desc_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(desc_empty)

        btn_row_empty = QHBoxLayout()
        btn_row_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row_empty.setSpacing(10)

        self.btn_empty_go_lib = QPushButton(_t("similar_btn_go_lib", "📁 Scegli dalla Libreria"))
        self.btn_empty_go_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_empty_go_lib.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: #ffffff;
                font-weight: bold;
                padding: 7px 18px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover { background-color: #0b5ed7; }
        """)
        self.btn_empty_go_lib.clicked.connect(self.navigate_to_library_requested.emit)
        btn_row_empty.addWidget(self.btn_empty_go_lib)

        empty_layout.addLayout(btn_row_empty)
        self.main_layout.addWidget(self.empty_card)

        # -------------------------------------------------------------
        # 2. Results Container (Shown when a reference track is loaded)
        # -------------------------------------------------------------
        self.results_container = QWidget()
        results_layout = QVBoxLayout(self.results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(10)

        # Header Frame: Active Reference Track Information
        self.header_frame = QFrame()
        self.header_frame.setObjectName("similarHeaderFrame")
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(12)

        icon_target = QLabel("🎯")
        icon_target.setStyleSheet("font-size: 28px;")
        h_layout.addWidget(icon_target)

        info_box = QVBoxLayout()
        info_box.setSpacing(3)

        self.lbl_target_title = QLabel("Traccia di Riferimento")
        self.lbl_target_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #0d6efd;")
        info_box.addWidget(self.lbl_target_title)

        badges_line = QHBoxLayout()
        badges_line.setSpacing(10)
        self.lbl_badge_bpm = QLabel("⚡ -- BPM")
        self.lbl_badge_bpm.setStyleSheet("font-weight: bold; font-size: 11px; color: #0284c7;")
        self.lbl_badge_key = QLabel("🔑 --")
        self.lbl_badge_key.setStyleSheet("font-weight: bold; font-size: 11px; color: #7c3aed;")
        self.lbl_badge_genre = QLabel("🏷️ --")
        self.lbl_badge_genre.setStyleSheet("font-size: 11px; color: #495057;")

        badges_line.addWidget(self.lbl_badge_bpm)
        badges_line.addWidget(self.lbl_badge_key)
        badges_line.addWidget(self.lbl_badge_genre)
        badges_line.addStretch()
        info_box.addLayout(badges_line)
        h_layout.addLayout(info_box, 1)

        # Loading Progress Bar
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(12)
        self.loading_bar.setFixedWidth(160)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setVisible(False)
        h_layout.addWidget(self.loading_bar)

        self.btn_change_track = QPushButton(_t("similar_btn_change", "🔄 Cambia Traccia"))
        self.btn_change_track.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change_track.clicked.connect(self.navigate_to_library_requested.emit)
        h_layout.addWidget(self.btn_change_track)

        results_layout.addWidget(self.header_frame)

        # Tabs: Local Matches vs Online Discovery
        self.tabs = QTabWidget()

        # Tab 1: Local Library Matches
        self.tab_local = QWidget()
        local_layout = QVBoxLayout(self.tab_local)
        local_layout.setContentsMargins(8, 8, 8, 8)
        local_layout.setSpacing(8)

        self.table_local = QTableWidget()
        self.table_local.setColumnCount(8)
        self.table_local.setHorizontalHeaderLabels([
            "#", "Affinità", "Titolo", "Artista", "BPM", "Camelot", "Genere", "Motivo Affinità"
        ])
        self.table_local.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_local.horizontalHeader().setStretchLastSection(True)
        self.table_local.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_local.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_local.customContextMenuRequested.connect(self._on_local_context_menu)
        self.table_local.doubleClicked.connect(self._on_local_double_clicked)
        local_layout.addWidget(self.table_local)

        local_bottom = QHBoxLayout()
        self.lbl_local_count = QLabel("Caricamento tracce...")
        self.lbl_local_count.setStyleSheet("color: #6c757d; font-size: 11px;")
        local_bottom.addWidget(self.lbl_local_count)
        local_bottom.addStretch()

        self.btn_export_crate = QPushButton("💾 Salva come Smart Crate")
        self.btn_export_crate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_crate.clicked.connect(self._on_export_smart_crate)
        local_bottom.addWidget(self.btn_export_crate)

        local_layout.addLayout(local_bottom)
        self.tabs.addTab(self.tab_local, "📁 Simili nella tua Libreria (0)")

        # Tab 2: Online Discovery
        self.tab_online = QWidget()
        online_layout = QVBoxLayout(self.tab_online)
        online_layout.setContentsMargins(8, 8, 8, 8)
        online_layout.setSpacing(8)

        self.table_online = QTableWidget()
        self.table_online.setColumnCount(6)
        self.table_online.setHorizontalHeaderLabels([
            "Fonte", "Affinità", "Titolo", "Artista", "Stato", "Ascolta Online"
        ])
        self.table_online.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_online.horizontalHeader().setStretchLastSection(True)
        self.table_online.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        online_layout.addWidget(self.table_online)

        online_bottom = QHBoxLayout()
        self.lbl_online_count = QLabel("Interrogazione Cosine.club & Chosic...")
        self.lbl_online_count.setStyleSheet("color: #6c757d; font-size: 11px;")
        online_bottom.addWidget(self.lbl_online_count)
        online_bottom.addStretch()
        online_layout.addLayout(online_bottom)

        self.tabs.addTab(self.tab_online, "🌐 Discovery Online (0)")

        results_layout.addWidget(self.tabs, 1)
        self.main_layout.addWidget(self.results_container, 1)

        self.results_container.setVisible(False)

    def set_reference_track(self, track: Optional[Dict[str, Any]]) -> None:
        """Sets target track and triggers asynchronous affinity calculation."""
        if not track:
            self.empty_card.setVisible(True)
            self.results_container.setVisible(False)
            return

        self.reference_track = dict(track)
        self.empty_card.setVisible(False)
        self.results_container.setVisible(True)

        t_title = self.reference_track.get("title") or Path(self.reference_track.get("filepath", "")).stem
        t_artist = self.reference_track.get("artist") or "Artista Sconosciuto"
        self.lbl_target_title.setText(f"{t_artist} — {t_title}")

        bpm = self.reference_track.get("bpm")
        self.lbl_badge_bpm.setText(f"⚡ {bpm:.1f} BPM" if bpm else "⚡ -- BPM")

        k_cam = self.reference_track.get("camelot_key") or self.reference_track.get("musical_key") or "--"
        self.lbl_badge_key.setText(f"🔑 {k_cam}")

        genre = self.reference_track.get("genre") or "Electronic"
        self.lbl_badge_genre.setText(f"🏷️ {genre}")

        self._start_search()

    def _start_search(self) -> None:
        if not self.reference_track:
            return

        self.cleanup()
        self.loading_bar.setVisible(True)
        self.lbl_local_count.setText("Analisi vettoriale e affinità locale in corso...")
        self.lbl_online_count.setText("Interrogazione Discovery Web in corso...")

        self._worker = SimilarSearchWorker(self.reference_track, self.db)
        self._worker.finished.connect(self._on_search_completed)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.start()

    def _on_search_completed(self, result: SimilarityResult) -> None:
        self.loading_bar.setVisible(False)
        self.similarity_result = result
        self._populate_local_table(result.local_similar_tracks)
        self._populate_online_table(result.discovery_tracks)

    def _populate_local_table(self, items: List[SimilarTrackRecommendation]) -> None:
        self.table_local.setRowCount(len(items))
        self.tabs.setTabText(0, f"📁 Simili nella tua Libreria ({len(items)})")
        self.lbl_local_count.setText(f"Trovate {len(items)} tracce acusticamente e armonicamente compatibili.")

        for row, rec in enumerate(items):
            self.table_local.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table_local.setCellWidget(row, 1, AffinityBadgeWidget(rec.similarity_pct))
            self.table_local.setItem(row, 2, QTableWidgetItem(rec.title))
            self.table_local.setItem(row, 3, QTableWidgetItem(rec.artist))

            bpm_str = f"{rec.bpm:.1f}" if rec.bpm else "--"
            self.table_local.setItem(row, 4, QTableWidgetItem(bpm_str))
            self.table_local.setItem(row, 5, QTableWidgetItem(rec.camelot_key or "--"))
            self.table_local.setItem(row, 6, QTableWidgetItem(rec.genre or "--"))
            reasons_str = " • ".join(rec.affinity_reasons) if rec.affinity_reasons else "Compatibilità generale"
            self.table_local.setItem(row, 7, QTableWidgetItem(reasons_str))

    def _populate_online_table(self, items: List[SimilarTrackRecommendation]) -> None:
        import os
        self.table_online.setRowCount(len(items))
        self.tabs.setTabText(1, f"🌐 Discovery Online ({len(items)})")
        self.lbl_online_count.setText(f"Trovate {len(items)} tracce consigliate tramite vettori Web.")

        for row, rec in enumerate(items):
            self.table_online.setItem(row, 0, QTableWidgetItem(rec.source.capitalize()))
            self.table_online.setCellWidget(row, 1, AffinityBadgeWidget(rec.similarity_pct))
            self.table_online.setItem(row, 2, QTableWidgetItem(rec.title))
            self.table_online.setItem(row, 3, QTableWidgetItem(rec.artist))

            in_lib_str = "✓ Presente in Libreria" if rec.in_library else "Mancante"
            item_status = QTableWidgetItem(in_lib_str)
            if rec.in_library:
                item_status.setForeground(QColor("#198754"))
            self.table_online.setItem(row, 4, item_status)

            # Web link button
            links_widget = QWidget()
            l_layout = QHBoxLayout(links_widget)
            l_layout.setContentsMargins(4, 2, 4, 2)
            if rec.external_urls:
                for platform_name, url in rec.external_urls.items():
                    btn_url = QPushButton(f"🌐 {platform_name.capitalize()}")
                    btn_url.setFixedHeight(22)
                    btn_url.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_url.clicked.connect(lambda _, u=url: os.system(f'start "" "{u}"' if os.name == 'nt' else f'open "{u}"'))
                    l_layout.addWidget(btn_url)
            l_layout.addStretch()
            self.table_online.setCellWidget(row, 5, links_widget)

    def _on_search_failed(self, error_msg: str) -> None:
        self.loading_bar.setVisible(False)
        self.lbl_local_count.setText(f"<span style='color: #ef4444;'>Errore durante la ricerca: {error_msg}</span>")

    def _on_local_context_menu(self, pos: QPoint) -> None:
        row = self.table_local.currentRow()
        if row < 0 or not self.similarity_result or row >= len(self.similarity_result.local_similar_tracks):
            return

        rec = self.similarity_result.local_similar_tracks[row]
        menu = QMenu(self)
        act_play = menu.addAction("▶ Play in Mini-Player")
        act_folder = menu.addAction("📂 Mostra nella cartella (Show in Folder)")

        action = menu.exec(self.table_local.viewport().mapToGlobal(pos))
        if action == act_play:
            self._play_track(rec)
        elif action == act_folder:
            if rec.local_filepath:
                PathResolver.show_in_file_manager(rec.local_filepath)

    def _on_local_double_clicked(self) -> None:
        row = self.table_local.currentRow()
        if row >= 0 and self.similarity_result and row < len(self.similarity_result.local_similar_tracks):
            rec = self.similarity_result.local_similar_tracks[row]
            self._play_track(rec)

    def _play_track(self, rec: SimilarTrackRecommendation) -> None:
        if rec.local_filepath and Path(rec.local_filepath).exists():
            track_dict = {
                "filepath": rec.local_filepath,
                "title": rec.title,
                "artist": rec.artist,
                "bpm": rec.bpm,
                "camelot_key": rec.camelot_key,
                "genre": rec.genre,
            }
            self.play_track_requested.emit(track_dict)

    def _on_export_smart_crate(self) -> None:
        if not self.similarity_result or not self.similarity_result.local_similar_tracks:
            QMessageBox.information(self, "Esporta Crate", "Nessuna traccia affine trovata da salvare.")
            return

        ref_title = self.reference_track.get("title") or "Track"
        crate_name = f"Simili a {ref_title[:24]}"
        rules = {
            "similar_to": ref_title,
            "target_bpm": self.reference_track.get("bpm"),
            "camelot_key": self.reference_track.get("camelot_key"),
            "genre": self.reference_track.get("genre"),
        }
        self.db.create_smart_crate(crate_name, rules)
        self.crates_updated.emit()
        QMessageBox.information(
            self,
            "Smart Crate Salvato",
            f"Il crate '{crate_name}' con {len(self.similarity_result.local_similar_tracks)} tracce simili è stato aggiunto alla tua libreria!",
        )

    def update_theme(self, theme_id: str = "light") -> None:
        """Adapts styling for Light or Dark mode."""
        self.current_theme = theme_id
        is_light = (theme_id == "light")

        if is_light:
            self.setStyleSheet("""
                QFrame#similarEmptyCard, QFrame#similarHeaderFrame {
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 8px;
                }
                QTabWidget::pane {
                    border: 1px solid #dee2e6;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background: #f8f9fa;
                    color: #495057;
                    padding: 8px 16px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    border: 1px solid #dee2e6;
                    font-weight: 600;
                    font-size: 11px;
                }
                QTabBar::tab:selected {
                    background: #ffffff;
                    color: #0d6efd;
                    border-bottom-color: #ffffff;
                }
                QTableWidget {
                    background-color: #ffffff;
                    border: 1px solid #dee2e6;
                    gridline-color: #f1f3f5;
                    color: #212529;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    color: #212529;
                    font-weight: 600;
                    padding: 4px;
                    border: 1px solid #dee2e6;
                }
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    color: #212529;
                    padding: 5px 12px;
                    border-radius: 4px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    border-color: #0d6efd;
                    color: #0d6efd;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#similarEmptyCard, QFrame#similarHeaderFrame {
                    background-color: #181b26;
                    border: 1px solid #282e42;
                    border-radius: 8px;
                }
                QTabWidget::pane {
                    border: 1px solid #232838;
                    background-color: #141720;
                }
                QTabBar::tab {
                    background: #1a1e2b;
                    color: #94a3b8;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QTabBar::tab:selected {
                    background: #00d2ff;
                    color: #0b0c10;
                }
                QTableWidget {
                    background-color: #14161f;
                    border: 1px solid #232838;
                    gridline-color: #1f2330;
                    color: #e2e8f0;
                }
                QHeaderView::section {
                    background-color: #1b1e2a;
                    color: #94a3b8;
                    font-weight: bold;
                    padding: 4px;
                    border: 1px solid #232838;
                }
                QPushButton {
                    background-color: #1e2433;
                    border: 1px solid #333b50;
                    color: #e2e8f0;
                    padding: 5px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #00d2ff;
                    color: #000000;
                }
            """)

    def cleanup(self) -> None:
        """Stops background search worker safely."""
        if hasattr(self, "_worker") and self._worker:
            if self._worker.isRunning():
                self._worker.requestInterruption()
                self._worker.wait(300)
            self._worker = None


__all__ = ["SimilarTracksView"]
