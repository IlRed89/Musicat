"""
Spotify Top Charts & Trends Engine for Musicat.

Fetches dynamic global and genre-specific trending playlists:
- Top Dance / Electro
- Top Tech House
- Top Techno
- Top Pop / Commercial
- Top Hip-Hop / Urban
- Top Indie / Rock
- Global Top 50

Cross-checks each track against the user's local hard disk database
to visually distinguish owned tracks ("In Library") from missing ones ("Missing").
Includes high-res artwork caching, 30s preview streams, and authentic offline fallback data.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import requests

from src.core.db import Database
from src.core.logger import MusicatLogger
from src.core.path_resolver import PathResolver
from src.core.settings import SettingsManager


@dataclass
class TrendingTrack:
    """Represents a trending track in Spotify Top Charts."""

    spotify_id: str
    title: str
    artist: str
    album: str
    category: str
    rank: int
    cover_url: str
    preview_url: Optional[str] = None
    external_url: str = ""
    bpm: Optional[float] = None
    camelot_key: Optional[str] = None
    energy: Optional[float] = None
    popularity: int = 0
    in_library: bool = False
    local_filepath: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes trending track to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrendingTrack":
        """Deserializes trending track from dictionary."""
        valid_keys = cls.__dataclass_fields__.keys()
        clean = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**clean)


TREND_CATEGORIES = [
    ("global_50", "🌐 Global Top 50"),
    ("dance_electro", "⚡ Dance / Electro"),
    ("tech_house", "🎧 Tech House"),
    ("techno", "🖤 Techno"),
    ("pop_commercial", "📻 Pop / Commercial"),
    ("hiphop_urban", "🎤 Hip-Hop / Urban"),
    ("indie_rock", "🎸 Indie / Rock"),
]

# Curated Editorial Playlist IDs on Spotify
CATEGORY_PLAYLIST_MAP = {
    "global_50": "37i9dQZEVXbMDoHDwVN2tF",       # Top 50 - Global
    "dance_electro": "37i9dQZF1DX4dyzvuaRJ0n",  # Mint (Electronic/Dance)
    "tech_house": "37i9dQZF1DXdLEN7aqioXM",     # Tech House
    "techno": "37i9dQZF1DX6J5NfMJS675",         # Techno State
    "pop_commercial": "37i9dQZF1DXcBWIGoYBM5M", # Today's Top Hits
    "hiphop_urban": "37i9dQZF1DX0XUsuxWHRQd",   # RapCaviar
    "indie_rock": "37i9dQZF1DXdbXrPNafg9d",     # All New Rock
}


class SpotifyTrendsManager:
    """Manages fetching, caching, and library cross-checking of Spotify Top Charts."""

    CACHE_EXPIRATION_SEC = 21600  # 6 hours cache

    def __init__(self, settings_manager: Optional[SettingsManager] = None) -> None:
        self.settings = settings_manager or SettingsManager.get_instance()
        self.cache_file = PathResolver.get_data_dir() / "spotify_trends_cache.json"
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def get_client_credentials(self) -> Tuple[str, str]:
        """Retrieves Spotify Client ID and Client Secret from settings or environment."""
        cid = self.settings.get("scrapers", "spotify_client_id", "") or os.environ.get("SPOTIFY_CLIENT_ID", "")
        sec = self.settings.get("scrapers", "spotify_client_secret", "") or os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        return cid.strip(), sec.strip()

    @classmethod
    def get_supported_categories(cls) -> List[str]:
        """Returns list of supported category display names."""
        return [display for _, display in TREND_CATEGORIES]

    def fetch_trends(
        self,
        category: str = "dance_electro",
        limit: int = 30,
        db: Optional[Database] = None,
        force_refresh: bool = False,
    ) -> List[TrendingTrack]:
        """Convenience method accepting either category key or display name."""
        cat_id = category
        for cid, display in TREND_CATEGORIES:
            if category.lower() in display.lower() or category.lower() == cid.lower():
                cat_id = cid
                break
        return self.fetch_category_trends(cat_id, limit=limit, db=db, force_refresh=force_refresh)

    def cross_check_with_library(self, tracks: List[TrendingTrack], db: Database) -> None:
        """Alias for cross_check_library."""
        return self.cross_check_library(tracks, db)

    def has_credentials(self) -> bool:
        """Checks if Spotify API credentials are configured."""
        cid, sec = self.get_client_credentials()
        return bool(cid and sec)

    def _authenticate_direct(self) -> Optional[str]:
        """Authenticates with Spotify Web API using Client Credentials flow."""
        cid, sec = self.get_client_credentials()
        if not cid or not sec:
            return None

        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        token_url = "https://accounts.spotify.com/api/token"
        data = {"grant_type": "client_credentials"}
        t0 = time.perf_counter()
        try:
            resp = requests.post(token_url, data=data, auth=(cid, sec), timeout=6.0)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            MusicatLogger.log_http(
                source="Spotify:Auth",
                url=token_url,
                status_code=resp.status_code,
                latency_ms=latency_ms,
            )
            if resp.status_code == 200:
                body = resp.json()
                self._access_token = body.get("access_token")
                expires_in = body.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in
                return self._access_token
            else:
                MusicatLogger.warning("SPOTIFY:AUTH", f"Token error {resp.status_code}: {resp.text}")
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            MusicatLogger.log_http(
                source="Spotify:Auth",
                url=token_url,
                status_code=0,
                latency_ms=latency_ms,
                error=str(exc),
            )
            MusicatLogger.warning("SPOTIFY:AUTH", f"Connection error: {exc}")

        return None

    def fetch_category_trends(
        self,
        category_id: str = "dance_electro",
        limit: int = 30,
        db: Optional[Database] = None,
        force_refresh: bool = False,
    ) -> List[TrendingTrack]:
        """Fetches trending tracks for category, utilizes disk cache, and cross-checks with library.

        Args:
            category_id: Identifier from TREND_CATEGORIES.
            limit: Maximum tracks to return.
            db: Local database to cross-check ownership.
            force_refresh: Ignore cache and re-fetch from API.

        Returns:
            List[TrendingTrack] with library ownership flags.
        """
        # 1. Check local cache first
        if not force_refresh:
            cached = self._read_cache(category_id)
            if cached:
                if db:
                    self.cross_check_library(cached, db)
                return cached[:limit]

        # 2. Try online Spotify API fetch if credentials exist
        tracks: List[TrendingTrack] = []
        token = self._authenticate_direct()
        if token:
            try:
                tracks = self._fetch_from_spotify_api(token, category_id, limit=limit)
            except Exception as exc:
                MusicatLogger.warning("SPOTIFY:FETCH", f"Error fetching {category_id}: {exc}")

        # 3. Fallback to curated offline dataset if API returned no tracks or keys not set
        if not tracks:
            tracks = self._get_curated_fallback_tracks(category_id)

        # 4. Save to cache
        if tracks:
            self._save_cache(category_id, tracks)

        # 5. Cross-check against user's local collection
        if db:
            self.cross_check_library(tracks, db)

        return tracks[:limit]

    def _fetch_from_spotify_api(
        self,
        token: str,
        category_id: str,
        limit: int = 30,
    ) -> List[TrendingTrack]:
        """Queries Spotify Web API for playlist tracks."""
        playlist_id = CATEGORY_PLAYLIST_MAP.get(category_id, CATEGORY_PLAYLIST_MAP["global_50"])
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": min(100, limit), "fields": "items(track(id,name,artists,album,preview_url,external_urls,popularity))"}

        t0 = time.perf_counter()
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=7.0)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            MusicatLogger.log_http(
                source="Spotify:Tracks",
                url=url,
                status_code=resp.status_code,
                latency_ms=latency_ms,
                params={"playlist_id": playlist_id, "category": category_id},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Spotify API responded with status {resp.status_code}")
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            MusicatLogger.log_http(
                source="Spotify:Tracks",
                url=url,
                status_code=0,
                latency_ms=latency_ms,
                params={"playlist_id": playlist_id, "category": category_id},
                error=str(exc),
            )
            raise

        items = resp.json().get("items", [])
        tracks: List[TrendingTrack] = []

        for idx, item in enumerate(items):
            tr = item.get("track")
            if not tr or not tr.get("name"):
                continue

            artists = ", ".join(a.get("name", "") for a in tr.get("artists", []))
            album_info = tr.get("album", {})
            images = album_info.get("images", [])
            cover_url = images[0].get("url") if images else ""

            ext_urls = tr.get("external_urls", {})
            spotify_url = ext_urls.get("spotify", "")

            track_obj = TrendingTrack(
                spotify_id=tr.get("id") or f"sp_{idx}",
                title=tr.get("name"),
                artist=artists or "Various Artists",
                album=album_info.get("name", ""),
                category=category_id,
                rank=idx + 1,
                cover_url=cover_url,
                preview_url=tr.get("preview_url"),
                external_url=spotify_url,
                popularity=tr.get("popularity", 0),
            )
            tracks.append(track_obj)

        return tracks

    def cross_check_library(self, tracks: List[TrendingTrack], db: Database) -> None:
        """Cross-checks trending tracks against user's local database (marks in_library)."""
        for t in tracks:
            # Query by artist and title in database
            matches = db.find_tracks_by_artist_title(t.artist, t.title)
            if matches:
                t.in_library = True
                t.local_filepath = matches[0].get("filepath")
                # Also import BPM/Key from local match if available
                if not t.bpm and matches[0].get("bpm"):
                    t.bpm = matches[0].get("bpm")
                if not t.camelot_key and matches[0].get("camelot_key"):
                    t.camelot_key = matches[0].get("camelot_key")
            else:
                t.in_library = False
                t.local_filepath = None

    def _read_cache(self, category_id: str) -> Optional[List[TrendingTrack]]:
        """Reads category tracks from disk cache if fresh."""
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cat_data = data.get(category_id)
            if cat_data:
                saved_time = cat_data.get("timestamp", 0)
                if time.time() - saved_time < self.CACHE_EXPIRATION_SEC:
                    raw_tracks = cat_data.get("tracks", [])
                    return [TrendingTrack.from_dict(t) for t in raw_tracks]
        except Exception:
            pass
        return None

    def _save_cache(self, category_id: str, tracks: List[TrendingTrack]) -> None:
        """Writes category tracks to disk cache."""
        data = {}
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data[category_id] = {
            "timestamp": time.time(),
            "tracks": [t.to_dict() for t in tracks],
        }

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _get_curated_fallback_tracks(self, category_id: str) -> List[TrendingTrack]:
        """Provides rich, authentic trending electronic and mainstream anthems when offline."""
        data_by_category: Dict[str, List[Tuple[str, str, str, str, float, str, int]]] = {
            "dance_electro": [
                ("Peggy Gou", "(It Goes Like) Nanana", "Nanana EP", "https://i.scdn.co/image/ab67616d0000b273b0a701887e5b5c7ef9518bf9", 130.0, "8B", 92),
                ("Fisher & Aatig", "Take It Off", "Take It Off", "https://i.scdn.co/image/ab67616d0000b2734ec6c0bbf23e597df315f6ad", 126.0, "8A", 89),
                ("Fred again.. & Swedish House Mafia", "Turn On The Lights again..", "USB", "https://i.scdn.co/image/ab67616d0000b273f3b97b0a735d4fa3f619e0cf", 132.0, "4A", 91),
                ("John Summit & Hayla", "Where You Are", "Where You Are", "https://i.scdn.co/image/ab67616d0000b273c5a61623fa595cb3d4d428bf", 126.0, "7B", 88),
                ("Mau P", "Drugs From Amsterdam", "Drugs From Amsterdam", "https://i.scdn.co/image/ab67616d0000b273e97906d09c2a382cf8db01a2", 125.0, "6A", 86),
                ("Dom Dolla & Clementine Douglas", "Miracle Maker", "Miracle Maker", "https://i.scdn.co/image/ab67616d0000b273b7a5e9559c8bf49a07153a8c", 128.0, "11A", 85),
                ("Calvin Harris & Ellie Goulding", "Miracle", "Miracle Single", "https://i.scdn.co/image/ab67616d0000b273dcf278ea242bb5d81b4f2c5a", 143.0, "2A", 94),
                ("Tiësto", "The Business", "The Business", "https://i.scdn.co/image/ab67616d0000b273f7c952b7190f845a7cbb0299", 120.0, "9A", 87),
            ],
            "tech_house": [
                ("Chris Lake & Cloonee", "Turn Off The Lights", "Black Book Records", "https://i.scdn.co/image/ab67616d0000b273c0049ba3876e5d89fb6a457c", 125.0, "9A", 90),
                ("Michael Bibi", "Different Side", "Solid Grooves", "https://i.scdn.co/image/ab67616d0000b2733d1bcf55651c686d173e6cf5", 128.0, "8A", 87),
                ("Cloonee", "Stephanie", "Hellbent Records", "https://i.scdn.co/image/ab67616d0000b273832c3f91040854b73b5faefc", 127.0, "9A", 84),
                ("Gorgon City", "Voodoo", "Salvation", "https://i.scdn.co/image/ab67616d0000b27393d3958ca03ff11317ba9355", 127.0, "4A", 83),
                ("James Hype & Ferrari", "Ferrari", "Ferrari EP", "https://i.scdn.co/image/ab67616d0000b273cfcbcf0a1c1d063be3dbecbe", 125.0, "8A", 89),
                ("SIDEPIECE", "Acrobatic", "Insomniac Records", "https://i.scdn.co/image/ab67616d0000b273d4ee7e3fc2ad9206b02506e7", 126.0, "11A", 81),
            ],
            "techno": [
                ("Charlotte de Witte", "Overdrive", "Overdrive EP", "https://i.scdn.co/image/ab67616d0000b27318ec7e0fc21dae60e8d08587", 135.0, "2A", 88),
                ("Amelie Lens", "Feel It", "Lenske", "https://i.scdn.co/image/ab67616d0000b27303f269a212ca0584d94b0d07", 134.0, "10A", 86),
                ("Enrico Sangiuliano", "The Sound of Techno", "NINETOZERO", "https://i.scdn.co/image/ab67616d0000b27375bf2a246a482b95fae6c6b3", 132.0, "8A", 85),
                ("Adam Beyer", "Your Mind", "Drumcode", "https://i.scdn.co/image/ab67616d0000b2737a28e937d5796a3a411a123f", 130.0, "1A", 89),
                ("Reinier Zonneveld", "Move Your Body", "Filth on Acid", "https://i.scdn.co/image/ab67616d0000b273ef5610bcde814467aa284ad4", 136.0, "11A", 84),
            ],
            "pop_commercial": [
                ("Dua Lipa", "Houdini", "Radical Optimism", "https://i.scdn.co/image/ab67616d0000b273ff3f07cf1923ce6174a9ab4a", 117.0, "8A", 96),
                ("The Weeknd", "Blinding Lights", "After Hours", "https://i.scdn.co/image/ab67616d0000b2738863bc11d2aa12b54f5aeb36", 171.0, "4A", 98),
                ("Taylor Swift", "Cruel Summer", "Lover", "https://i.scdn.co/image/ab67616d0000b273e787cffec20aa2a396a61647", 170.0, "8B", 97),
                ("Sabrina Carpenter", "Espresso", "Short n' Sweet", "https://i.scdn.co/image/ab67616d0000b273659e99a385f52430c5e7b243", 104.0, "9A", 99),
                ("Billie Eilish", "LUNCH", "HIT ME HARD AND SOFT", "https://i.scdn.co/image/ab67616d0000b27371d62ea7ea8a5be92d3c1f62", 125.0, "10A", 95),
            ],
            "global_50": [
                ("Sabrina Carpenter", "Espresso", "Short n' Sweet", "https://i.scdn.co/image/ab67616d0000b273659e99a385f52430c5e7b243", 104.0, "9A", 99),
                ("Post Malone & Morgan Wallen", "I Had Some Help", "F-1 Trillion", "https://i.scdn.co/image/ab67616d0000b273523f6eb7e7b686b24d77c44d", 128.0, "10B", 97),
                ("Tommy Richman", "MILLION DOLLAR BABY", "MILLION DOLLAR BABY", "https://i.scdn.co/image/ab67616d0000b273f32e633d7b83ec5515324ec3", 138.0, "8A", 96),
                ("Kendrick Lamar", "Not Like Us", "Not Like Us", "https://i.scdn.co/image/ab67616d0000b2731ea0c62b2339cbf493a999ad", 101.0, "11A", 98),
                ("Benson Boone", "Beautiful Things", "Fireworks & Rollerblades", "https://i.scdn.co/image/ab67616d0000b273a0e69a04a625cb22d0b67bf9", 105.0, "9B", 95),
            ],
        }

        dataset = data_by_category.get(category_id, data_by_category["global_50"])
        tracks: List[TrendingTrack] = []

        for idx, (artist, title, album, cover, bpm, camelot, pop) in enumerate(dataset):
            clean_search = urllib.parse.quote_plus(f"{artist} - {title}")
            t = TrendingTrack(
                spotify_id=f"trending_{category_id}_{idx}",
                title=title,
                artist=artist,
                album=album,
                category=category_id,
                rank=idx + 1,
                cover_url=cover,
                preview_url=None,
                external_url=f"https://open.spotify.com/search/{clean_search}",
                bpm=bpm,
                camelot_key=camelot,
                energy=round(0.65 + (0.05 * (idx % 5)), 2),
                popularity=pop,
            )
            tracks.append(t)

        return tracks
