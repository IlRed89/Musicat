"""
Home Dashboard: Spotify Top Charts & Live Trends View for Musicat.

Features:
- Live Trending Charts fetched from Spotify Web API across electronic & mainstream genres:
  (Global Top 50, Dance / Electro, Tech House, Techno, Pop, Hip-Hop, Indie Rock).
- High-res artwork cards with title, artist, rank badge (#1, #2, etc.), and BPM/Energy.
- Cross-check against the user's local hard disk collection:
  - Green Badge ("In Library"): track is already owned locally! Click to audition immediately.
  - Gray Badge ("Missing"): track is not in collection, with quick links to find/buy on Beatport, YouTube, or Spotify.
- 30-second audio preview playback.
- "✨ Trova Simili" button on each card to discover matching tracks in the user's library.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.db import Database
from src.core.spotify_trends import (
    TREND_CATEGORIES,
    SpotifyTrendsManager,
    TrendingTrack,
)


class TrendsFetchWorker(QThread):
    """Background worker to fetch category trends from Spotify and cross-check library."""

    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        trends_manager: SpotifyTrendsManager,
        category_id: str,
        db: Database,
        force_refresh: bool = False,
    ) -> None:
        super().__init__()
        self.trends_manager = trends_manager
        self.category_id = category_id
        self.db = db
        self.force_refresh = force_refresh

    def run(self) -> None:
        try:
            tracks = self.trends_manager.fetch_category_trends(
                category_id=self.category_id,
                limit=35,
                db=self.db,
                force_refresh=self.force_refresh,
            )
            self.finished.emit(tracks)
        except Exception as exc:
            self.failed.emit(str(exc))


class TrendingTrackCard(QFrame):
    """Card widget representing a single trending chart entry."""

    play_requested = Signal(dict)
    find_similar_requested = Signal(dict)

    def __init__(self, track: TrendingTrack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.track = track
        self.setFixedSize(210, 290)
        self.setStyleSheet("""
            TrendingTrackCard {
                background-color: #171923;
                border: 1px solid #292d3e;
                border-radius: 8px;
            }
            TrendingTrackCard:hover {
                border-color: #00d2ff;
                background-color: #1c1f2c;
            }
        """)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # -------------------------------------------------------------
        # Cover Art & Rank Badge Overlay
        # -------------------------------------------------------------
        cover_container = QWidget()
        cover_container.setFixedSize(190, 140)
        c_layout = QVBoxLayout(cover_container)
        c_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_cover = QLabel(cover_container)
        self.lbl_cover.setFixedSize(190, 140)
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setStyleSheet("background-color: #10121a; border-radius: 6px; font-size: 28px;")
        self.lbl_cover.setText("🎵")

        # Rank badge in top-left
        rank_badge = QLabel(f"#{self.track.rank}", cover_container)
        rank_color = "#f59e0b" if self.track.rank <= 3 else "#38bdf8"
        rank_badge.setStyleSheet(f"""
            background-color: rgba(15, 23, 42, 0.88);
            color: {rank_color};
            font-weight: bold;
            font-size: 11px;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid {rank_color};
        """)
        rank_badge.move(6, 6)

        # Ownership badge in top-right
        owner_badge = QLabel(cover_container)
        if self.track.in_library:
            owner_badge.setText("✓ In Library")
            owner_badge.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                font-weight: bold;
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #10b981;
            """)
        else:
            owner_badge.setText("+ Missing")
            owner_badge.setStyleSheet("""
                background-color: #1e2433;
                color: #94a3b8;
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #334155;
            """)
        owner_badge.adjustSize()
        owner_badge.move(190 - owner_badge.width() - 6, 6)

        c_layout.addWidget(self.lbl_cover)
        layout.addWidget(cover_container)

        # -------------------------------------------------------------
        # Metadata: Title & Artist
        # -------------------------------------------------------------
        self.lbl_title = QLabel(self.track.title)
        self.lbl_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #ffffff;")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setMaximumHeight(36)
        layout.addWidget(self.lbl_title)

        self.lbl_artist = QLabel(self.track.artist)
        self.lbl_artist.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_artist.setWordWrap(False)
        layout.addWidget(self.lbl_artist)

        # Acoustic indicators (BPM & Camelot)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        if self.track.bpm:
            lbl_bpm = QLabel(f"⚡ {self.track.bpm:.1f}")
            lbl_bpm.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
            meta_row.addWidget(lbl_bpm)
        if self.track.camelot_key:
            lbl_k = QLabel(f"🔑 {self.track.camelot_key}")
            lbl_k.setStyleSheet("color: #c77dff; font-size: 10px; font-weight: bold;")
            meta_row.addWidget(lbl_k)
        meta_row.addStretch()
        layout.addLayout(meta_row)

        layout.addStretch()

        # -------------------------------------------------------------
        # Actions: Play / Similar / Web
        # -------------------------------------------------------------
        actions_row = QHBoxLayout()
        actions_row.setSpacing(4)

        if self.track.in_library:
            btn_play = QPushButton("▶ Play")
            btn_play.setFixedHeight(24)
            btn_play.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 10px;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover { background-color: #38bdf8; color: #000; }
            """)
            btn_play.clicked.connect(self._on_play_clicked)
            actions_row.addWidget(btn_play, 1)
        else:
            btn_stream = QPushButton("🌐 Web")
            btn_stream.setFixedHeight(24)
            btn_stream.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #94a3b8;
                    font-size: 10px;
                    border: 1px solid #334155;
                    border-radius: 3px;
                }
                QPushButton:hover { background-color: #334155; color: #fff; }
            """)
            btn_stream.clicked.connect(self._on_web_clicked)
            actions_row.addWidget(btn_stream, 1)

        btn_sim = QPushButton("✨ Simili")
        btn_sim.setFixedHeight(24)
        btn_sim.setStyleSheet("""
            QPushButton {
                background-color: #27203b;
                color: #c084fc;
                border: 1px solid #7c3aed;
                font-weight: bold;
                font-size: 10px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #7c3aed; color: #fff; }
        """)
        btn_sim.clicked.connect(self._on_similar_clicked)
        actions_row.addWidget(btn_sim, 1)

        layout.addLayout(actions_row)

    def _on_play_clicked(self) -> None:
        if self.track.local_filepath:
            track_dict = {
                "filepath": self.track.local_filepath,
                "title": self.track.title,
                "artist": self.track.artist,
                "album": self.track.album,
                "bpm": self.track.bpm,
                "camelot_key": self.track.camelot_key,
            }
            self.play_requested.emit(track_dict)

    def _on_web_clicked(self) -> None:
        url = self.track.external_url or f"https://open.spotify.com/search/{self.track.artist}%20{self.track.title}"
        if os.name == "nt":
            os.system(f'start "" "{url}"')
        else:
            os.system(f'open "{url}"')

    def _on_similar_clicked(self) -> None:
        track_dict = {
            "filepath": self.track.local_filepath or "",
            "title": self.track.title,
            "artist": self.track.artist,
            "bpm": self.track.bpm,
            "camelot_key": self.track.camelot_key,
            "genre": self.track.category.replace("_", " ").title(),
        }
        self.find_similar_requested.emit(track_dict)


class HomeTrendsView(QWidget):
    """Main Home View with trending playlists and library cross-checking."""

    play_track_requested = Signal(dict)
    find_similar_requested = Signal(dict)
    navigate_to_library_requested = Signal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.trends_manager = SpotifyTrendsManager()
        self.current_category = "dance_electro"
        self.current_tracks: List[TrendingTrack] = []
        self._category_buttons: Dict[str, QPushButton] = {}

        self.setStyleSheet("""
            HomeTrendsView {
                background-color: #0d0f16;
            }
            QLabel {
                color: #e2e8f0;
            }
        """)

        self._init_ui()
        self._load_category(self.current_category)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # Header: Title, Search, Refresh
        # -------------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(10)

        title_lbl = QLabel("🔥 TOP CHARTS & TRENDS DEL MOMENTO")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #00d2ff;")
        header.addWidget(title_lbl)

        header.addStretch()

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("🔍 Filtra per artista o titolo...")
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setFixedWidth(240)
        self.txt_filter.textChanged.connect(self._on_filter_text_changed)
        header.addWidget(self.txt_filter)

        self.btn_refresh = QPushButton("🔄 Aggiorna")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1e2433;
                border: 1px solid #333b50;
                color: #38bdf8;
                font-weight: bold;
                padding: 5px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0284c7; color: #fff; }
        """)
        self.btn_refresh.clicked.connect(lambda: self._load_category(self.current_category, force_refresh=True))
        header.addWidget(self.btn_refresh)

        self.btn_go_library = QPushButton("🎵 Vai alla Libreria DJ")
        self.btn_go_library.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #38bdf8; color: #000; }
        """)
        self.btn_go_library.clicked.connect(self.navigate_to_library_requested.emit)
        header.addWidget(self.btn_go_library)

        main_layout.addLayout(header)

        # -------------------------------------------------------------
        # Category Selector Buttons
        # -------------------------------------------------------------
        cat_bar = QHBoxLayout()
        cat_bar.setSpacing(6)

        for cat_id, cat_name in TREND_CATEGORIES:
            btn = QPushButton(cat_name)
            btn.setCheckable(True)
            btn.setChecked(cat_id == self.current_category)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #161822;
                    border: 1px solid #282c3c;
                    color: #94a3b8;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 5px 12px;
                    border-radius: 5px;
                }
                QPushButton:checked {
                    background-color: #00d2ff;
                    color: #0b0c10;
                    border-color: #00d2ff;
                }
                QPushButton:hover:!checked {
                    background-color: #1f2332;
                    color: #e2e8f0;
                }
            """)
            btn.clicked.connect(lambda _, cid=cat_id: self._on_category_clicked(cid))
            self._category_buttons[cat_id] = btn
            cat_bar.addWidget(btn)

        cat_bar.addStretch()
        main_layout.addLayout(cat_bar)

        # Status & Stats line
        self.lbl_status = QLabel("Caricamento classifiche...")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 11px; margin-left: 2px;")
        main_layout.addWidget(self.lbl_status)

        # -------------------------------------------------------------
        # Scroll Area with Card Grid
        # -------------------------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(4, 4, 4, 4)
        self.cards_layout.setSpacing(14)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll, 1)

    def _on_category_clicked(self, category_id: str) -> None:
        self.current_category = category_id
        for cid, btn in self._category_buttons.items():
            btn.setChecked(cid == category_id)
        self._load_category(category_id)

    def _load_category(self, category_id: str, force_refresh: bool = False) -> None:
        self.lbl_status.setText("Caricamento tracce in corso da Spotify Trends...")
        self._worker = TrendsFetchWorker(self.trends_manager, category_id, self.db, force_refresh=force_refresh)
        self._worker.finished.connect(self._on_trends_loaded)
        self._worker.failed.connect(self._on_trends_failed)
        self._worker.start()

    def _on_trends_loaded(self, tracks: List[TrendingTrack]) -> None:
        self.current_tracks = tracks
        self._render_cards(tracks)

    def _on_trends_failed(self, error: str) -> None:
        self.lbl_status.setText(f"<span style='color: #ef4444;'>Errore durante il caricamento: {error}</span>")

    def _render_cards(self, tracks: List[TrendingTrack]) -> None:
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        in_lib_count = sum(1 for t in tracks if t.in_library)
        auth_note = "Spotify Web API" if self.trends_manager.has_credentials() else "Curated Trends (Configura Spotify API in Impostazioni per il feed live)"
        self.lbl_status.setText(
            f"Mostrando <b>{len(tracks)}</b> tracce di tendenza | "
            f"<span style='color: #34d399; font-weight: bold;'>{in_lib_count} presenti nella tua libreria</span> | "
            f"Fonte: {auth_note}"
        )

        columns = 5  # 5 cards per row
        for idx, t in enumerate(tracks):
            card = TrendingTrackCard(t, self.cards_container)
            card.play_requested.connect(self.play_track_requested.emit)
            card.find_similar_requested.connect(self.find_similar_requested.emit)
            self.cards_layout.addWidget(card, idx // columns, idx % columns)

    def _on_filter_text_changed(self, text: str) -> None:
        q = text.strip().lower()
        if not q:
            self._render_cards(self.current_tracks)
            return

        filtered = [
            t for t in self.current_tracks
            if q in t.title.lower() or q in t.artist.lower() or q in t.album.lower()
        ]
        self._render_cards(filtered)
