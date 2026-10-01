"""
Traxsource Scraping and Search Client for Musicat.

Specialized in House, Deep House, Tech House, Soulful House, and Techno.
Retrieves Track Title, Artists, Remixers, Record Label, Catalog Number,
Release Date, Genre, BPM, Key, and Album Artwork.
"""

import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

from ..core.logger import MusicatLogger
from ..audio.analyzer import key_to_camelot


@dataclass
class TraxsourceTrack:
    """Represents a track scraped from Traxsource."""

    source: str
    title: str
    mix_name: str
    artists: List[str]
    remixers: List[str]
    label: str
    release_date: str
    year: Optional[int]
    genre: str
    bpm: Optional[float]
    musical_key: str
    camelot_key: str
    catalog_number: str
    artwork_url: str
    url: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes track data to dictionary."""
        return {
            "source": self.source,
            "title": self.title,
            "mix_name": self.mix_name,
            "artist": ", ".join(self.artists),
            "remixer": ", ".join(self.remixers),
            "label": self.label,
            "release_date": self.release_date,
            "year": self.year,
            "genre": self.genre,
            "bpm": self.bpm,
            "musical_key": self.musical_key,
            "camelot_key": self.camelot_key,
            "catalog_number": self.catalog_number,
            "artwork_url": self.artwork_url,
            "url": self.url,
        }


class TraxsourceScraper:
    """Queries Traxsource search engine and parses electronic track metadata."""

    BASE_URL = "https://www.traxsource.com"
    SEARCH_URL = "https://www.traxsource.com/search/tracks"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    @classmethod
    def search_tracks(cls, query: str, limit: int = 10) -> List[TraxsourceTrack]:
        """Searches Traxsource for matching tracks.

        Args:
            query (str): Search term (e.g. 'Kerri Chandler You're In My System').
            limit (int): Maximum tracks to return.

        Returns:
            List[TraxsourceTrack]: Parsed tracks list.
        """
        results: List[TraxsourceTrack] = []
        if not query or not query.strip():
            return results

        clean_q = query.strip()
        encoded = urllib.parse.quote_plus(clean_q)
        target_url = f"{cls.SEARCH_URL}?term={encoded}"

        start_time = time.perf_counter()
        status_code = 0
        try:
            resp = requests.get(target_url, headers=cls.HEADERS, timeout=10)
            status_code = resp.status_code
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                MusicatLogger.log_http("Traxsource", target_url, status_code, latency_ms, 0)
                return results

            html = resp.text
            # Traxsource track rows: <div class="trk-row ...">
            rows = re.findall(r'<div[^>]*class="[^"]*trk-row[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
            if not rows:
                # Fallback broader pattern
                rows = re.findall(r'<div[^>]*class="[^"]*trk-cell[^"]*"[^>]*>.*?</div>', html, re.DOTALL)

            for block in rows[:limit]:
                track_item = cls._parse_html_row(block)
                if track_item:
                    results.append(track_item)

            MusicatLogger.log_http("Traxsource", target_url, status_code, latency_ms, len(results))
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            MusicatLogger.log_http("Traxsource", target_url, status_code, latency_ms, 0)
            MusicatLogger.get_logger().warning(f"[TRAXSOURCE] Search failed: {e}")

        return results

    @classmethod
    def _parse_html_row(cls, block: str) -> Optional[TraxsourceTrack]:
        """Parses individual track row HTML snippet."""
        try:
            # Title & Mix
            title_match = re.search(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</a>', block)
            title = title_match.group(1).strip() if title_match else ""
            if not title:
                return None

            version_match = re.search(r'<span[^>]*class="[^"]*version[^"]*"[^>]*>([^<]+)</span>', block)
            mix_name = version_match.group(1).strip() if version_match else "Original Mix"

            # Artists
            artists = re.findall(r'<a[^>]*href="/artist/[^"]*"[^>]*>([^<]+)</a>', block)
            artists = [a.strip() for a in artists if a.strip()]

            # Label
            label_match = re.search(r'<a[^>]*href="/label/[^"]*"[^>]*>([^<]+)</a>', block)
            label = label_match.group(1).strip() if label_match else ""

            # Genre
            genre_match = re.search(r'<a[^>]*href="/genre/[^"]*"[^>]*>([^<]+)</a>', block)
            genre = genre_match.group(1).strip() if genre_match else ""

            # BPM (Must be followed by BPM or inside a bpm class)
            bpm_match = re.search(r'\b(\d{2,3}(?:\.\d+)?)\s*BPM\b', block, re.IGNORECASE)
            if not bpm_match:
                bpm_match = re.search(r'class="[^"]*bpm[^"]*"[^>]*>(\d{2,3}(?:\.\d+)?)', block, re.IGNORECASE)
            bpm = float(bpm_match.group(1)) if bpm_match else None

            # Key
            key_match = re.search(r'\b([A-G][b#]?(?:m|maj|min)?)\b', block)
            musical_key = key_match.group(1) if key_match else ""
            camelot = key_to_camelot(musical_key)

            # Year / Date
            date_match = re.search(r'\b(\d{4})-\d{2}-\d{2}\b', block)
            rel_date = date_match.group(0) if date_match else ""
            year = int(date_match.group(1)) if date_match else None

            # Artwork
            art_match = re.search(r'<img[^>]*src="([^"]+)"', block)
            art_url = art_match.group(1) if art_match else ""
            if art_url and art_url.startswith("//"):
                art_url = f"https:{art_url}"

            return TraxsourceTrack(
                source="Traxsource",
                title=title,
                mix_name=mix_name,
                artists=artists if artists else ["Unknown Artist"],
                remixers=[],
                label=label,
                release_date=rel_date,
                year=year,
                genre=genre,
                bpm=bpm,
                musical_key=musical_key,
                camelot_key=camelot,
                catalog_number="",
                artwork_url=art_url,
                url=f"{cls.BASE_URL}/search",
            )
        except Exception:
            return None
