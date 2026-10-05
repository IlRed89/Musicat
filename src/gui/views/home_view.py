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
- Direct Genre Filtering: clicking any genre category routes to DJ Library filtering.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, QRect, QSemaphore, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QImage, QPainter, QPixmap
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

import requests
from src.core.db import Database
from src.core.i18n import _t, I18n
from src.core.logger import MusicatLogger
from src.core.spotify_trends import (
    TREND_PLATFORMS,
    PLATFORM_CATEGORIES,
    TREND_CATEGORIES,
    SpotifyTrendsManager,
    TrendingTrack,
)

# Mapping between Trend category keys and library genre tags
CATEGORY_TO_GENRE: Dict[str, str] = {
    # Spotify
    "global_50": "",
    "dance_electro": "Dance",
    "tech_house": "Tech House",
    "techno": "Techno",
    "pop_commercial": "Pop",
    "hiphop_urban": "Hip-Hop",
    "indie_rock": "Rock",
    # SoundCloud
    "sc_trending_all": "",
    "sc_remix_hype": "Dance",
    "sc_electronic": "Electronic",
    "sc_house_tech": "Tech House",
    "sc_underground_hiphop": "Hip-Hop",
    # Beatport
    "bp_top_100": "",
    "bp_tech_house": "Tech House",
    "bp_techno_peak": "Techno",
    "bp_melodic_house": "Melodic Techno",
    "bp_house": "House",
    "bp_drum_and_bass": "Drum & Bass",
}


class AsyncThumbnailLoader(QThread):
    """Asynchronously loads cover art thumbnails with in-memory caching and bounded thread concurrency."""

    loaded = Signal(str, QPixmap)  # url, pixmap
    _cache: Dict[str, QPixmap] = {}
    _semaphore = QSemaphore(6)

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def run(self) -> None:
        if not self.url or self.isInterruptionRequested():
            return
        if self.url in self._cache:
            if not self.isInterruptionRequested():
                self.loaded.emit(self.url, self._cache[self.url])
            return

        self._semaphore.acquire()
        try:
            if self.isInterruptionRequested():
                return
            pix = QPixmap()
            try:
                if self.url.startswith("http://") or self.url.startswith("https://"):
                    resp = requests.get(self.url, timeout=3.5)
                    if self.isInterruptionRequested():
                        return
                    if resp.status_code == 200:
                        pix.loadFromData(resp.content)
                elif os.path.exists(self.url):
                    pix.load(self.url)
            except Exception:
                pass

            if not pix.isNull() and not self.isInterruptionRequested():
                self._cache[self.url] = pix
                self.loaded.emit(self.url, pix)
        finally:
            self._semaphore.release()


class TrendsFetchWorker(QThread):
    """Background worker to fetch category trends from Spotify, SoundCloud, or Beatport and cross-check library."""

    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        trends_manager: SpotifyTrendsManager,
        category_id: str,
        db: Database,
        platform: str = "spotify",
        force_refresh: bool = False,
    ) -> None:
        super().__init__()
        self.trends_manager = trends_manager
        self.category_id = category_id
        self.db = db
        self.platform = platform
        self.force_refresh = force_refresh

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            tracks = self.trends_manager.fetch_category_trends(
                category_id=self.category_id,
                platform=self.platform,
                limit=100,
                db=self.db,
                force_refresh=self.force_refresh,
            )
            if not self.isInterruptionRequested():
                self.finished.emit(tracks)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


class TrendingTrackCard(QFrame):
    """Card widget representing a single trending chart entry with adaptive Light/Dark styling."""

    play_requested = Signal(dict)
    find_similar_requested = Signal(dict)
    filter_genre_requested = Signal(str)

    def __init__(self, track: TrendingTrack, parent: Optional[QWidget] = None, theme_id: str = "light") -> None:
        super().__init__(parent)
        self.track = track
        self.theme_id = theme_id
        self.setFixedSize(215, 305)

        self._thumb_loader: Optional[AsyncThumbnailLoader] = None
        self._init_ui()
        self.update_theme(self.theme_id)

        if self.track.cover_url:
            cached_pix = AsyncThumbnailLoader._cache.get(self.track.cover_url)
            if cached_pix and not cached_pix.isNull():
                self._on_thumbnail_loaded(self.track.cover_url, cached_pix)
            else:
                self._thumb_loader = AsyncThumbnailLoader(self.track.cover_url)
                self._thumb_loader.loaded.connect(self._on_thumbnail_loaded)
                self._thumb_loader.start()

    def cleanup(self) -> None:
        """Safely stops the thumbnail loader thread before widget deletion to prevent C++ crashes."""
        if self._thumb_loader:
            try:
                self._thumb_loader.loaded.disconnect()
            except Exception:
                pass
            if self._thumb_loader.isRunning():
                self._thumb_loader.requestInterruption()
                if not self._thumb_loader.wait(200):
                    self._thumb_loader.terminate()
                    self._thumb_loader.wait(100)
            self._thumb_loader = None

    def _on_thumbnail_loaded(self, url: str, pixmap: QPixmap) -> None:
        if url == self.track.cover_url and not pixmap.isNull():
            scaled = pixmap.scaled(
                195, 140,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.lbl_cover.setPixmap(scaled)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # -------------------------------------------------------------
        # Cover Art & Rank Badge Overlay
        # -------------------------------------------------------------
        cover_container = QWidget()
        cover_container.setFixedSize(195, 140)
        c_layout = QVBoxLayout(cover_container)
        c_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_cover = QLabel(cover_container)
        self.lbl_cover.setFixedSize(195, 140)
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setText("🎵")

        # Rank badge in top-left
        self.rank_badge = QLabel(f"#{self.track.rank}", cover_container)
        rank_color = "#d97706" if self.track.rank <= 3 else "#0284c7"
        self.rank_badge.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 0.92);
            color: {rank_color};
            font-weight: bold;
            font-size: 11px;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid {rank_color};
        """)
        self.rank_badge.move(6, 6)

        # Ownership badge in top-right
        self.owner_badge = QLabel(cover_container)
        if self.track.in_library:
            self.owner_badge.setText(_t("home_card_in_library", "✓ In Libreria"))
            self.owner_badge.setStyleSheet("""
                background-color: #d1e7dd;
                color: #0f5132;
                font-weight: bold;
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #badbcc;
            """)
        else:
            self.owner_badge.setText(_t("home_card_missing", "+ Mancante"))
            self.owner_badge.setStyleSheet("""
                background-color: #f8f9fa;
                color: #6c757d;
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid #dee2e6;
            """)
        self.owner_badge.adjustSize()
        self.owner_badge.move(195 - self.owner_badge.width() - 6, 6)

        c_layout.addWidget(self.lbl_cover)
        layout.addWidget(cover_container)

        # -------------------------------------------------------------
        # Metadata: Title & Artist
        # -------------------------------------------------------------
        self.lbl_title = QLabel(self.track.title)
        self.lbl_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setMaximumHeight(36)
        layout.addWidget(self.lbl_title)

        self.lbl_artist = QLabel(self.track.artist)
        self.lbl_artist.setWordWrap(False)
        layout.addWidget(self.lbl_artist)

        # Acoustic indicators (BPM & Camelot)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        if self.track.bpm:
            lbl_bpm = QLabel(f"⚡ {self.track.bpm:.1f}")
            lbl_bpm.setStyleSheet("color: #0284c7; font-size: 10px; font-weight: bold;")
            meta_row.addWidget(lbl_bpm)
        if self.track.camelot_key:
            lbl_k = QLabel(f"🔑 {self.track.camelot_key}")
            lbl_k.setStyleSheet("color: #7c3aed; font-size: 10px; font-weight: bold;")
            meta_row.addWidget(lbl_k)
        meta_row.addStretch()
        layout.addLayout(meta_row)

        layout.addStretch()

        # -------------------------------------------------------------
        # Actions: Play / Similar / Web / Filter Genre
        # -------------------------------------------------------------
        actions_row = QHBoxLayout()
        actions_row.setSpacing(4)

        if self.track.in_library:
            self.btn_play = QPushButton(_t("home_card_play", "▶ Play"))
            self.btn_play.setFixedHeight(24)
            self.btn_play.clicked.connect(self._on_play_clicked)
            actions_row.addWidget(self.btn_play, 1)
        else:
            self.btn_stream = QPushButton(_t("home_card_web", "🌐 Web"))
            self.btn_stream.setFixedHeight(24)
            self.btn_stream.clicked.connect(self._on_web_clicked)
            actions_row.addWidget(self.btn_stream, 1)

        self.btn_sim = QPushButton(_t("home_card_similar", "✨ Simili"))
        self.btn_sim.setFixedHeight(24)
        self.btn_sim.clicked.connect(self._on_similar_clicked)
        actions_row.addWidget(self.btn_sim, 1)

        layout.addLayout(actions_row)

    def update_theme(self, theme_id: str = "light") -> None:
        """Applies high-contrast white card styling for Light Theme or dark console for Dark Theme."""
        self.theme_id = theme_id
        is_light = (theme_id == "light")

        if is_light:
            self.setStyleSheet("""
                TrendingTrackCard {
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 8px;
                }
                TrendingTrackCard:hover {
                    background-color: #f8f9fa;
                    border-color: #0d6efd;
                }
            """)
            self.lbl_cover.setStyleSheet("background-color: #f1f3f5; border: 1px solid #dee2e6; border-radius: 6px; font-size: 28px;")
            self.lbl_title.setStyleSheet("color: #212529;")
            self.lbl_artist.setStyleSheet("color: #495057; font-size: 11px;")
            if hasattr(self, "btn_play"):
                self.btn_play.setStyleSheet("""
                    QPushButton {
                        background-color: #0d6efd;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 10px;
                        border: none;
                        border-radius: 4px;
                    }
                    QPushButton:hover { background-color: #0b5ed7; }
                """)
            if hasattr(self, "btn_stream"):
                self.btn_stream.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #495057;
                        border: 1px solid #ced4da;
                        font-size: 10px;
                        border-radius: 4px;
                    }
                    QPushButton:hover { background-color: #e9ecef; color: #212529; }
                """)
            if hasattr(self, "btn_sim"):
                self.btn_sim.setStyleSheet("""
                    QPushButton {
                        background-color: #f3e8ff;
                        color: #7e22ce;
                        border: 1px solid #d8b4fe;
                        font-weight: bold;
                        font-size: 10px;
                        border-radius: 4px;
                    }
                    QPushButton:hover { background-color: #e9d5ff; color: #6b21a8; }
                """)
        else:
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
            self.lbl_cover.setStyleSheet("background-color: #10121a; border-radius: 6px; font-size: 28px;")
            self.lbl_title.setStyleSheet("color: #ffffff;")
            self.lbl_artist.setStyleSheet("color: #94a3b8; font-size: 11px;")
            if hasattr(self, "btn_play"):
                self.btn_play.setStyleSheet("""
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
            if hasattr(self, "btn_stream"):
                self.btn_stream.setStyleSheet("""
                    QPushButton {
                        background-color: #1e293b;
                        color: #94a3b8;
                        font-size: 10px;
                        border: 1px solid #334155;
                        border-radius: 3px;
                    }
                    QPushButton:hover { background-color: #334155; color: #fff; }
                """)
            if hasattr(self, "btn_sim"):
                self.btn_sim.setStyleSheet("""
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
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
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
    """Main Home View with trending playlists, clean Light Theme cards, and safe genre filtering."""

    play_track_requested = Signal(dict)
    find_similar_requested = Signal(dict)
    navigate_to_library_requested = Signal()
    filter_genre_requested = Signal(str)

    def __init__(self, db: Database, parent: Optional[QWidget] = None, auto_load: bool = False) -> None:
        super().__init__(parent)
        self.db = db
        self.trends_manager = SpotifyTrendsManager()
        self.current_platform = "spotify"
        self.current_category = "dance_electro"
        self.current_tracks: List[TrendingTrack] = []
        self._platform_buttons: Dict[str, QPushButton] = {}
        self._category_buttons: Dict[str, QPushButton] = {}
        self._has_loaded = False
        self._worker: Optional[TrendsFetchWorker] = None
        self.current_theme = "light"

        self._init_ui()
        self.update_theme("light")

        if auto_load:
            self.ensure_loaded()

    def ensure_loaded(self) -> None:
        """Lazily triggers initial category loading on first view activation."""
        if not self._has_loaded:
            self._has_loaded = True
            self._load_category(self.current_category)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # Header: Title, Search, Refresh, Library Link
        # -------------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(10)

        self.title_lbl = QLabel(_t("home_title", "🔥 TOP CHARTS & TRENDS DEL MOMENTO"))
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #0d6efd;")
        header.addWidget(self.title_lbl)

        header.addStretch()

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText(_t("home_filter_placeholder", "🔍 Filtra per artista o titolo..."))
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setFixedWidth(240)
        self.txt_filter.textChanged.connect(self._on_filter_text_changed)
        header.addWidget(self.txt_filter)

        self.btn_refresh = QPushButton(_t("home_btn_refresh", "🔄 Aggiorna"))
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(lambda: self._load_category(self.current_category, force_refresh=True))
        header.addWidget(self.btn_refresh)

        self.btn_go_library = QPushButton(_t("home_btn_go_library", "🎵 Vai alla Libreria DJ"))
        self.btn_go_library.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go_library.clicked.connect(self._on_go_library_clicked)
        header.addWidget(self.btn_go_library)

        main_layout.addLayout(header)

        # -------------------------------------------------------------
        # Platform Selector Bar (Spotify, SoundCloud, Beatport)
        # -------------------------------------------------------------
        self.plat_bar_layout = QHBoxLayout()
        self.plat_bar_layout.setSpacing(8)

        for plat_id, plat_name in TREND_PLATFORMS:
            btn = QPushButton(plat_name)
            btn.setCheckable(True)
            btn.setChecked(plat_id == self.current_platform)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, pid=plat_id: self.on_platform_clicked(pid))
            self._platform_buttons[plat_id] = btn
            self.plat_bar_layout.addWidget(btn)

        self.plat_bar_layout.addStretch()
        main_layout.addLayout(self.plat_bar_layout)

        # -------------------------------------------------------------
        # Category Selector Buttons (Generi Musicali Dinamici)
        # -------------------------------------------------------------
        self.cat_bar_layout = QHBoxLayout()
        self.cat_bar_layout.setSpacing(6)
        main_layout.addLayout(self.cat_bar_layout)
        self._rebuild_category_buttons()

        # Status & Stats line
        self.lbl_status = QLabel(_t("home_status_loading", "Caricamento classifiche..."))
        self.lbl_status.setStyleSheet("color: #6c757d; font-size: 11px; margin-left: 2px;")
        main_layout.addWidget(self.lbl_status)

        # -------------------------------------------------------------
        # Scroll Area with Smooth Pixel Scrolling and Card Grid
        # -------------------------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.verticalScrollBar().setSingleStep(16)
        self.scroll.horizontalScrollBar().setSingleStep(16)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(4, 4, 4, 4)
        self.cards_layout.setSpacing(14)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll, 1)

    def on_platform_clicked(self, platform_id: str) -> None:
        """Handles platform switch (Spotify, SoundCloud, Beatport)."""
        if platform_id == self.current_platform:
            for pid, btn in self._platform_buttons.items():
                btn.setChecked(pid == self.current_platform)
            return

        self.current_platform = platform_id
        for pid, btn in self._platform_buttons.items():
            btn.setChecked(pid == platform_id)

        self._rebuild_category_buttons()
        self._load_category(self.current_category)

    def _rebuild_category_buttons(self) -> None:
        """Dynamically populates the category buttons corresponding to active platform."""
        while self.cat_bar_layout.count():
            item = self.cat_bar_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._category_buttons.clear()

        categories = PLATFORM_CATEGORIES.get(self.current_platform, PLATFORM_CATEGORIES["spotify"])
        valid_cids = [c[0] for c in categories]
        if self.current_category not in valid_cids:
            self.current_category = valid_cids[0]

        for cat_id, cat_name in categories:
            btn = QPushButton(cat_name)
            btn.setCheckable(True)
            btn.setChecked(cat_id == self.current_category)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, cid=cat_id: self.on_genre_clicked(cid))
            self._category_buttons[cat_id] = btn
            self.cat_bar_layout.addWidget(btn)

        self.cat_bar_layout.addStretch()
        self._apply_button_styles()

    def _apply_button_styles(self) -> None:
        """Applies theme styling to platform and category buttons."""
        is_light = (self.current_theme == "light")

        if is_light:
            plat_style = """
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    color: #212529;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background-color: #e7f1ff;
                    border-color: #0d6efd;
                    color: #0d6efd;
                }
                QPushButton:checked {
                    background-color: #0d6efd;
                    color: #ffffff;
                    border-color: #0b5ed7;
                    font-weight: bold;
                }
            """
            cat_style = """
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    color: #495057;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 5px 12px;
                }
                QPushButton:hover {
                    background-color: #f8f9fa;
                    border-color: #0d6efd;
                    color: #0d6efd;
                }
                QPushButton:checked {
                    background-color: #212529;
                    color: #ffffff;
                    border-color: #212529;
                    font-weight: bold;
                }
            """
        else:
            plat_style = """
                QPushButton {
                    background-color: #1a1e2b;
                    border: 1px solid #2d3345;
                    border-radius: 6px;
                    color: #94a3b8;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background-color: #242a3d;
                    color: #e2e8f0;
                }
                QPushButton:checked {
                    background-color: #00d2ff;
                    color: #0b0c10;
                    border-color: #00d2ff;
                }
            """
            cat_style = """
                QPushButton {
                    background-color: #161822;
                    border: 1px solid #282c3c;
                    color: #94a3b8;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 5px 12px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #1f2332;
                    color: #e2e8f0;
                }
                QPushButton:checked {
                    background-color: #38bdf8;
                    color: #0b0c10;
                    border-color: #38bdf8;
                    font-weight: bold;
                }
            """

        for btn in self._platform_buttons.values():
            btn.setStyleSheet(plat_style)
        for btn in self._category_buttons.values():
            btn.setStyleSheet(cat_style)

    def update_theme(self, theme_id: str = "light") -> None:
        """Adapts container, platform buttons, category buttons, and child cards to active Light/Dark theme."""
        self.current_theme = theme_id
        is_light = (theme_id == "light")

        if is_light:
            self.setStyleSheet("""
                HomeTrendsView {
                    background-color: #f8f9fa;
                }
                QLabel {
                    color: #212529;
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #0d6efd;")
            self.lbl_status.setStyleSheet("color: #6c757d; font-size: 11px; margin-left: 2px;")
            self.txt_filter.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #212529;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 5px 8px;
                }
                QLineEdit:focus {
                    border-color: #0d6efd;
                }
            """)
            self.btn_refresh.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    color: #0d6efd;
                    font-weight: 600;
                    padding: 5px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e7f1ff;
                    border-color: #0d6efd;
                }
            """)
            self.btn_go_library.setStyleSheet("""
                QPushButton {
                    background-color: #0d6efd;
                    color: #ffffff;
                    font-weight: bold;
                    padding: 5px 14px;
                    border-radius: 4px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #0b5ed7;
                }
            """)
        else:
            self.setStyleSheet("""
                HomeTrendsView {
                    background-color: #0d0f16;
                }
                QLabel {
                    color: #e2e8f0;
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #00d2ff;")
            self.lbl_status.setStyleSheet("color: #64748b; font-size: 11px; margin-left: 2px;")
            self.txt_filter.setStyleSheet("""
                QLineEdit {
                    background-color: #161822;
                    color: #e0e2ec;
                    border: 1px solid #282c3c;
                    border-radius: 4px;
                    padding: 5px 8px;
                }
            """)
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

        self._apply_button_styles()

        # Update cards
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), "update_theme"):
                item.widget().update_theme(theme_id)

    def _on_go_library_clicked(self) -> None:
        """Navigates to the DJ Library, applying the active category's genre filter if available."""
        target_genre = CATEGORY_TO_GENRE.get(self.current_category, "")
        if target_genre:
            self.filter_genre_requested.emit(target_genre)
        else:
            self.navigate_to_library_requested.emit()

    def on_genre_clicked(self, category_or_genre: Any) -> None:
        """Safely handles genre button clicks with exhaustive logging, recursion protection, and crash prevention."""
        try:
            logger = MusicatLogger.get_logger()
            cat_str = str(category_or_genre).strip() if category_or_genre is not None else ""
            logger.info(f"[HOME_VIEW:GENRE_CLICK] Cliccato genere/categoria: {cat_str!r} (Piattaforma: {self.current_platform})")

            if not cat_str or cat_str in ("False", "True"):
                logger.warning(f"[HOME_VIEW:GENRE_CLICK] Categoria non valida: {category_or_genre!r}")
                return

            if getattr(self, "_is_handling_genre_click", False):
                logger.warning("[HOME_VIEW:GENRE_CLICK] Operazione già in corso, evento ignorato per evitare ricorsione.")
                return
            self._is_handling_genre_click = True

            # Determine category key from active platform's categories
            platform_cats = PLATFORM_CATEGORIES.get(self.current_platform, PLATFORM_CATEGORIES["spotify"])
            valid_cids = [c[0] for c in platform_cats]
            target_cid = cat_str
            if target_cid not in valid_cids:
                matched = False
                for cid, cname in platform_cats:
                    if cat_str.lower() in cname.lower() or cat_str.lower() in cid.lower():
                        target_cid = cid
                        matched = True
                        break
                if not matched:
                    logger.warning(f"[HOME_VIEW:GENRE_CLICK] Categoria {cat_str!r} non presente tra le categorie valide: {valid_cids}")
                    self._is_handling_genre_click = False
                    return

            self.current_category = target_cid
            for cid, btn in self._category_buttons.items():
                btn.setChecked(cid == target_cid)

            # Defer update safely via QTimer to avoid Qt mouse event race conditions
            def do_load() -> None:
                try:
                    self._load_category(target_cid)
                finally:
                    self._is_handling_genre_click = False

            QTimer.singleShot(0, do_load)

        except Exception as exc:
            self._is_handling_genre_click = False
            MusicatLogger.get_logger().error(
                f"[HOME_VIEW:GENRE_CLICK] Errore gestito al click del genere {category_or_genre!r}: {exc}",
                exc_info=True,
            )

    def _load_category(self, category_id: str, force_refresh: bool = False) -> None:
        """Loads category trending tracks from background worker, stopping existing worker safely."""
        try:
            MusicatLogger.get_logger().info(f"[HOME_VIEW] Caricamento categoria: {category_id!r} (platform={self.current_platform}, force_refresh={force_refresh})")
            self.lbl_status.setText(_t("home_status_loading", "Caricamento tracce in corso da {platform} Trends...", platform=self.current_platform.capitalize()))

            # Safely stop active worker to avoid C++ QThread destruction crashes
            if hasattr(self, "_worker") and self._worker:
                if self._worker.isRunning():
                    MusicatLogger.get_logger().debug("[HOME_VIEW] Interruzione thread precedente...")
                    self._worker.requestInterruption()
                    if not self._worker.wait(300):
                        self._worker.terminate()
                        self._worker.wait(100)

            self._worker = TrendsFetchWorker(
                self.trends_manager,
                category_id,
                self.db,
                platform=self.current_platform,
                force_refresh=force_refresh,
            )
            self._worker.finished.connect(self._on_trends_loaded)
            self._worker.failed.connect(self._on_trends_failed)
            self._worker.start()

        except Exception as exc:
            MusicatLogger.get_logger().error(f"[HOME_VIEW] Errore in _load_category({category_id}): {exc}\n{traceback.format_exc()}")

    def _on_trends_loaded(self, tracks: List[TrendingTrack]) -> None:
        self.current_tracks = tracks or []
        self._render_cards(self.current_tracks)

    def _on_trends_failed(self, error: str) -> None:
        self.lbl_status.setText(f"<span style='color: #ef4444;'>{_t('home_status_error', 'Errore durante il caricamento: {error}', error=error)}</span>")

    def _render_cards(self, tracks: List[TrendingTrack]) -> None:
        """Renders track cards safely, stopping any pending thumbnail loaders before destroying cards."""
        try:
            # 1. Cleanly stop thumbnail loaders of all existing cards before removal
            while self.cards_layout.count():
                item = self.cards_layout.takeAt(0)
                if item and item.widget():
                    w = item.widget()
                    if hasattr(w, "cleanup"):
                        w.cleanup()
                    w.deleteLater()

            if not tracks:
                self.lbl_status.setText("Nessuna traccia trovata per questa categoria.")
                return

            in_lib_count = sum(1 for t in tracks if t.in_library)
            plat_display = dict(TREND_PLATFORMS).get(self.current_platform, self.current_platform.upper())
            auth_note = "API Online" if (self.current_platform == "spotify" and self.trends_manager.has_credentials()) else "Curated Trends Feed"
            self.lbl_status.setText(
                f"Piattaforma: <b>{plat_display}</b> | Mostrando <b>{len(tracks)}</b> tracce di tendenza | "
                f"<span style='color: #198754; font-weight: bold;'>{in_lib_count} presenti nella tua libreria</span> | "
                f"Fonte: {auth_note}"
            )

            viewport_w = self.scroll.viewport().width()
            columns = max(3, min(8, viewport_w // 230)) if viewport_w > 200 else 5
            self._last_cols = columns

            for idx, t in enumerate(tracks):
                card = TrendingTrackCard(t, self.cards_container, theme_id=self.current_theme)
                card.play_requested.connect(self.play_track_requested.emit)
                card.find_similar_requested.connect(self.find_similar_requested.emit)
                card.filter_genre_requested.connect(self.filter_genre_requested.emit)
                self.cards_layout.addWidget(card, idx // columns, idx % columns)

        except Exception as exc:
            MusicatLogger.get_logger().error(f"[HOME_VIEW] Errore in _render_cards: {exc}\n{traceback.format_exc()}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.current_tracks:
            viewport_w = self.scroll.viewport().width()
            new_cols = max(3, min(8, viewport_w // 230)) if viewport_w > 200 else 5
            if getattr(self, "_last_cols", 0) != new_cols:
                self._render_cards(self.current_tracks)

    def refresh_library_status(self) -> None:
        """Re-evaluates whether displayed tracks exist in the local database library."""
        if not self.current_tracks:
            return
        for t in self.current_tracks:
            matches = self.db.find_tracks_by_artist_title(t.artist, t.title)
            t.in_library = bool(matches)
            if matches and isinstance(matches, list) and len(matches) > 0 and isinstance(matches[0], dict):
                t.local_filepath = matches[0].get("filepath")
        self._render_cards(self.current_tracks)

    def _on_filter_text_changed(self, text: str) -> None:
        q = text.strip().lower()
        if not q:
            self._render_cards(self.current_tracks)
            return

        filtered = [
            t for t in self.current_tracks
            if q in (t.title or "").lower() or q in (t.artist or "").lower() or q in (t.album or "").lower()
        ]
        self._render_cards(filtered)

    def cleanup(self) -> None:
        """Safely stops background worker thread and child card loaders to prevent QThread crashes."""
        if hasattr(self, "_worker") and self._worker:
            if self._worker.isRunning():
                self._worker.requestInterruption()
                if not self._worker.wait(300):
                    self._worker.terminate()
                    self._worker.wait(100)
            self._worker = None

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                if hasattr(w, "cleanup"):
                    w.cleanup()
                w.deleteLater()

    def closeEvent(self, event: Any) -> None:
        """Handles close event, safely shutting down background workers."""
        self.cleanup()
        super().closeEvent(event)
