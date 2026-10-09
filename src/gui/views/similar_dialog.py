"""
Similar Tracks & Music Discovery Dialog for Musicat.

Displays:
1. Local Library Matches: ranked by acoustic affinity (Camelot Key, BPM pitch range, Genre, Energy).
2. Web Discovery Panel: recommendations from Cosine.club, Chosic, and Spotify with quick external search links.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.db import Database
from src.core.path_resolver import PathResolver
from src.scrapers.similarity_engine import (
    SimilarTrackRecommendation,
    SimilarityEngine,
    SimilarityResult,
)


class SimilarSearchWorker(QThread):
    """Background worker thread to calculate local affinity and fetch web discoveries."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        reference_track: Dict[str, Any],
        db: Database,
        min_affinity_score: float = 35.0,
    ) -> None:
        super().__init__()
        self.reference_track = reference_track
        self.db = db
        self.min_affinity_score = min_affinity_score

    def run(self) -> None:
        try:
            result = SimilarityEngine.find_all_similar(
                self.reference_track,
                self.db,
                min_affinity_score=self.min_affinity_score,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class AffinityBadgeWidget(QWidget):
    """Visual affinity progress badge (e.g. 95% Green, 75% Blue)."""

    def __init__(self, score_pct: float, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.score_pct = score_pct
        self.setFixedHeight(22)
        self.setMinimumWidth(80)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Background capsule
        bg_color = QColor("#1a1d26")
        painter.fillRect(0, 0, w, h, bg_color)

        # Bar fill
        fill_w = int((self.score_pct / 100.0) * (w - 2))
        fill_color = QColor("#10b981") if self.score_pct >= 80 else (QColor("#00d2ff") if self.score_pct >= 60 else QColor("#eab308"))
        painter.fillRect(1, 1, fill_w, h - 2, fill_color)

        # Text
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#ffffff") if self.score_pct < 60 else QColor("#000000"))
        painter.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, f"{self.score_pct:.1f}%")


class SimilarTracksDialog(QDialog):
    """Dialog for inspecting similar tracks in the local collection and online discovery."""

    play_track_requested = Signal(dict)
    crate_export_requested = Signal(list)
    play_requested = play_track_requested

    def __init__(
        self,
        reference_track: Dict[str, Any],
        db: Database,
        parent: Optional[QWidget] = None,
        auto_start: bool = True,
    ) -> None:
        super().__init__(parent)
        self.reference_track = reference_track
        self.db = db
        self.similarity_result: Optional[SimilarityResult] = None
        self._worker: Optional[SimilarSearchWorker] = None

        title = reference_track.get("title") or Path(reference_track.get("filepath", "")).stem
        artist = reference_track.get("artist") or "Unknown Artist"

        self.setWindowTitle(f"✨ Tracce Simili — {artist} - {title}")
        self.resize(980, 620)
        self.setStyleSheet("""
            QDialog { background-color: #111318; color: #cbd5e1; }
            QLabel { color: #cbd5e1; font-size: 12px; }
            QTabWidget::pane { border: 1px solid #232838; background-color: #141720; }
            QTabBar::tab {
                background: #1a1e2b;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
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
                font-size: 11px;
                padding: 4px;
                border: 1px solid #232838;
            }
            QPushButton {
                background-color: #1e2433;
                border: 1px solid #333b50;
                color: #e2e8f0;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00d2ff;
                color: #000;
            }
        """)

        self._init_ui()
        if auto_start:
            self._start_search()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # -------------------------------------------------------------
        # Header: Reference Track Profile
        # -------------------------------------------------------------
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #181b26;
                border: 1px solid #282e42;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 6, 10, 6)
        h_layout.setSpacing(12)

        icon_lbl = QLabel("🎯")
        icon_lbl.setStyleSheet("font-size: 26px;")
        h_layout.addWidget(icon_lbl)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)

        t_title = self.reference_track.get("title") or Path(self.reference_track.get("filepath", "")).stem
        t_artist = self.reference_track.get("artist") or "Unknown Artist"
        lbl_main = QLabel(f"<b>Traccia di Riferimento:</b> <span style='color: #00d2ff;'>{t_artist} — {t_title}</span>")
        lbl_main.setStyleSheet("font-size: 13px; color: #ffffff;")
        info_box.addWidget(lbl_main)

        # Badges line
        badges_line = QHBoxLayout()
        badges_line.setSpacing(8)

        bpm = self.reference_track.get("bpm")
        bpm_str = f"⚡ {bpm:.1f} BPM" if bpm else "⚡ -- BPM"
        lbl_bpm = QLabel(bpm_str)
        lbl_bpm.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        badges_line.addWidget(lbl_bpm)

        k_cam = self.reference_track.get("camelot_key") or self.reference_track.get("musical_key") or "--"
        lbl_key = QLabel(f"🔑 {k_cam}")
        key_color = "#c77dff" if str(k_cam).endswith("A") else "#00d2ff"
        lbl_key.setStyleSheet(f"color: {key_color}; font-weight: bold; font-size: 11px;")
        badges_line.addWidget(lbl_key)

        genre = self.reference_track.get("genre") or "Electronic"
        lbl_genre = QLabel(f"🏷️ {genre}")
        lbl_genre.setStyleSheet("color: #94a3b8; font-size: 11px;")
        badges_line.addWidget(lbl_genre)

        badges_line.addStretch()
        info_box.addLayout(badges_line)
        h_layout.addLayout(info_box)

        # Loading Indicator
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(14)
        self.loading_bar.setFixedWidth(160)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet("QProgressBar::chunk { background-color: #00d2ff; }")
        h_layout.addWidget(self.loading_bar)

        layout.addWidget(header_frame)

        # -------------------------------------------------------------
        # Tabs: Local Matches vs Online Discovery
        # -------------------------------------------------------------
        self.tabs = QTabWidget()

        # Tab 1: Local Library Matches
        self.tab_local = QWidget()
        local_layout = QVBoxLayout(self.tab_local)
        local_layout.setContentsMargins(8, 8, 8, 8)

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

        # Local Actions bar
        local_actions = QHBoxLayout()
        self.lbl_local_count = QLabel("Scansione libreria in corso...")
        local_actions.addWidget(self.lbl_local_count)
        local_actions.addStretch()

        self.btn_export_crate = QPushButton("💾 Salva come Smart Crate")
        self.btn_export_crate.clicked.connect(self._on_export_smart_crate)
        local_actions.addWidget(self.btn_export_crate)

        local_layout.addLayout(local_actions)
        self.tabs.addTab(self.tab_local, "📁 Simili nella tua Libreria (0)")

        # Tab 2: Online Discovery (Missing Tracks)
        self.tab_online = QWidget()
        online_layout = QVBoxLayout(self.tab_online)
        online_layout.setContentsMargins(8, 8, 8, 8)

        self.table_online = QTableWidget()
        self.table_online.setColumnCount(6)
        self.table_online.setHorizontalHeaderLabels([
            "Fonte", "Affinità", "Titolo", "Artista", "Stato", "Ascolta Online"
        ])
        self.table_online.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_online.horizontalHeader().setStretchLastSection(True)
        self.table_online.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        online_layout.addWidget(self.table_online)

        self.lbl_online_count = QLabel("Interrogazione Cosine.club & Chosic...")
        online_layout.addWidget(self.lbl_online_count)

        self.tabs.addTab(self.tab_online, "🌐 Discovery Online & Tracce Mancanti (0)")

        layout.addWidget(self.tabs, 1)

        # Bottom Close Button
        bottom_box = QHBoxLayout()
        bottom_box.addStretch()
        btn_close = QPushButton("Chiudi")
        btn_close.clicked.connect(self.accept)
        bottom_box.addWidget(btn_close)
        layout.addLayout(bottom_box)

    def _start_search(self) -> None:
        """Launches asynchronous search across local library and web APIs."""
        self._worker = SimilarSearchWorker(self.reference_track, self.db)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.start()

    def _on_search_finished(self, result: SimilarityResult) -> None:
        """Populates tables with calculated matches."""
        self.loading_bar.setVisible(False)
        self.similarity_result = result

        # 1. Populate Local Table
        local_tracks = result.local_similar_tracks
        self.tabs.setTabText(0, f"📁 Simili nella tua Libreria ({len(local_tracks)})")
        self.lbl_local_count.setText(f"Trovate <b>{len(local_tracks)}</b> tracce affini su {result.total_scanned:,} file scansionati.")

        self.table_local.setRowCount(len(local_tracks))
        for row, rec in enumerate(local_tracks):
            # Index
            self.table_local.setItem(row, 0, QTableWidgetItem(str(row + 1)))

            # Affinity Badge
            badge = AffinityBadgeWidget(rec.similarity_pct, self)
            self.table_local.setCellWidget(row, 1, badge)

            # Metadata
            self.table_local.setItem(row, 2, QTableWidgetItem(rec.title))
            self.table_local.setItem(row, 3, QTableWidgetItem(rec.artist))
            self.table_local.setItem(row, 4, QTableWidgetItem(f"{rec.bpm:.1f}" if rec.bpm else "--"))

            cam_item = QTableWidgetItem(rec.camelot_key or "--")
            if rec.camelot_key and rec.camelot_key.endswith("A"):
                cam_item.setForeground(QColor("#c77dff"))
            elif rec.camelot_key and rec.camelot_key.endswith("B"):
                cam_item.setForeground(QColor("#00d2ff"))
            self.table_local.setItem(row, 5, cam_item)

            self.table_local.setItem(row, 6, QTableWidgetItem(rec.genre))

            # Reasons
            reasons_str = " • ".join(rec.affinity_reasons) if rec.affinity_reasons else "Compatibilità generale"
            self.table_local.setItem(row, 7, QTableWidgetItem(reasons_str))

        # 2. Populate Online Discovery Table
        disc_tracks = result.discovery_tracks
        self.tabs.setTabText(1, f"🌐 Discovery Online & Tracce Mancanti ({len(disc_tracks)})")
        self.lbl_online_count.setText(f"Suggerite <b>{len(disc_tracks)}</b> tracce dal web (Cosine.club / Chosic / Spotify).")

        self.table_online.setRowCount(len(disc_tracks))
        for row, rec in enumerate(disc_tracks):
            self.table_online.setItem(row, 0, QTableWidgetItem(rec.source))

            badge = AffinityBadgeWidget(rec.similarity_pct, self)
            self.table_online.setCellWidget(row, 1, badge)

            self.table_online.setItem(row, 2, QTableWidgetItem(rec.title))
            self.table_online.setItem(row, 3, QTableWidgetItem(rec.artist))

            # Status Badge
            status_item = QTableWidgetItem("✓ In Libreria" if rec.in_library else "+ Mancante")
            status_item.setForeground(QColor("#10b981") if rec.in_library else QColor("#94a3b8"))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_online.setItem(row, 4, status_item)

            # Quick Link Buttons Widget
            links_widget = QWidget()
            l_layout = QHBoxLayout(links_widget)
            l_layout.setContentsMargins(2, 2, 2, 2)
            l_layout.setSpacing(4)

            for plat, url in rec.external_urls.items():
                btn_url = QPushButton(plat.capitalize())
                btn_url.setFixedHeight(20)
                btn_url.setStyleSheet("""
                    QPushButton {
                        padding: 1px 6px;
                        font-size: 10px;
                        background-color: #1a2234;
                        border: 1px solid #0284c7;
                        color: #38bdf8;
                    }
                    QPushButton:hover {
                        background-color: #0284c7;
                        color: #ffffff;
                    }
                """)
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
        """Saves current similar matches as a new Smart Crate."""
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
        QMessageBox.information(
            self,
            "Smart Crate Salvato",
            f"Il crate '{crate_name}' con {len(self.similarity_result.local_similar_tracks)} tracce simili è stato aggiunto alla tua libreria!",
        )

    def cleanup(self) -> None:
        """Safely stops background worker thread to prevent QThread destruction errors."""
        if hasattr(self, "_worker") and self._worker:
            if self._worker.isRunning():
                self._worker.requestInterruption()
                self._worker.wait(300)

    def closeEvent(self, event: Any) -> None:
        """Handles dialog close event, ensuring worker thread termination."""
        self.cleanup()
        super().closeEvent(event)

