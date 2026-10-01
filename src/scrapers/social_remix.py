"""
Social, Web & DJ Remix Scraping Engine for Musicat.

Queries specialized remix and streaming platforms:
- SoundCloud (DJ edits, bootlegs, and live sets)
- YouTube Music (official audios, remixes, and extended versions)
- Hypeddit (free DJ promo downloads and club edits)
- Remix.audio (community DJ remixes with key/BPM tags)
- Music-Hit.com (club charts and radio mixes)
"""

import json
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

from ..core.logger import MusicatLogger


@dataclass
class SocialTrackItem:
    """Represents a track or remix found on social/web platforms."""

    source: str
    title: str
    artist: str
    remixer: str
    genre: str
    year: Optional[int]
    bpm: Optional[float]
    musical_key: str
    camelot_key: str
    artwork_url: str
    stream_url: str

    def to_dict(self) -> Dict[str, Any]:
        """Converts item to standard dictionary."""
        return {
            "source": self.source,
            "title": self.title,
            "artist": self.artist,
            "remixer": self.remixer,
            "genre": self.genre,
            "year": self.year,
            "bpm": self.bpm,
            "musical_key": self.musical_key,
            "camelot_key": self.camelot_key,
            "artwork_url": self.artwork_url,
            "stream_url": self.stream_url,
        }


class SocialRemixScraper:
    """Aggregates electronic bootlegs, edits, and remixes across web platforms."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    @classmethod
    def search_soundcloud(cls, query: str, limit: int = 5) -> List[SocialTrackItem]:
        """Searches SoundCloud for DJ tracks, bootlegs, and extended edits."""
        results: List[SocialTrackItem] = []
        if not query:
            return results

        encoded = urllib.parse.quote_plus(query.strip())
        url = f"https://soundcloud.com/search/sounds?q={encoded}"
        start_time = time.perf_counter()

        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=8)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            MusicatLogger.log_http("SoundCloud", url, resp.status_code, latency_ms, 0)

            if resp.status_code == 200:
                html = resp.text
                # Find track items in initial HTML hydration or schema.org
                matches = re.findall(r'<li[^>]*itemprop="itemListElement"[^>]*>.*?<a[^>]*itemprop="url"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html, re.DOTALL)
                for rel_url, title in matches[:limit]:
                    clean_title = title.strip()
                    # Parse Remix / Edit from title
                    remixer = ""
                    remix_match = re.search(r'\(([^)]+remix[^)]*)\)', clean_title, re.IGNORECASE)
                    if remix_match:
                        remixer = remix_match.group(1).strip()

                    results.append(
                        SocialTrackItem(
                            source="SoundCloud",
                            title=clean_title,
                            artist="SoundCloud Artist",
                            remixer=remixer,
                            genre="Electronic",
                            year=None,
                            bpm=None,
                            musical_key="",
                            camelot_key="",
                            artwork_url="",
                            stream_url=f"https://soundcloud.com{rel_url}",
                        )
                    )
        except Exception as e:
            MusicatLogger.get_logger().debug(f"[SOUNDCLOUD] Search failed: {e}")

        return results

    @classmethod
    def search_youtube_music(cls, query: str, limit: int = 5) -> List[SocialTrackItem]:
        """Searches YouTube Music for track audio and official remix releases."""
        results: List[SocialTrackItem] = []
        if not query:
            return results

        encoded = urllib.parse.quote_plus(f"{query} audio")
        url = f"https://www.youtube.com/results?search_query={encoded}"
        start_time = time.perf_counter()

        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=8)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            MusicatLogger.log_http("YouTubeMusic", url, resp.status_code, latency_ms, 0)

            if resp.status_code == 200:
                html = resp.text
                # Extract initial video titles and videoIds
                video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', html)

                seen = set()
                for i in range(min(len(video_ids), len(titles), limit * 2)):
                    vid = video_ids[i]
                    if vid in seen:
                        continue
                    seen.add(vid)

                    vtitle = titles[i]
                    # Parse Artist - Title if separated by dash
                    parts = vtitle.split(" - ", 1)
                    parsed_artist = parts[0] if len(parts) > 1 else "YouTube Audio"
                    parsed_title = parts[1] if len(parts) > 1 else vtitle

                    results.append(
                        SocialTrackItem(
                            source="YouTube Music",
                            title=parsed_title,
                            artist=parsed_artist,
                            remixer="",
                            genre="Club/Dance",
                            year=None,
                            bpm=None,
                            musical_key="",
                            camelot_key="",
                            artwork_url=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                            stream_url=f"https://www.youtube.com/watch?v={vid}",
                        )
                    )
                    if len(results) >= limit:
                        break
        except Exception as e:
            MusicatLogger.get_logger().debug(f"[YOUTUBE] Search failed: {e}")

        return results

    @classmethod
    def search_hypeddit(cls, query: str, limit: int = 5) -> List[SocialTrackItem]:
        """Searches Hypeddit for free DJ downloads, edits, and club promos."""
        results: List[SocialTrackItem] = []
        if not query:
            return results

        encoded = urllib.parse.quote_plus(query.strip())
        url = f"https://hypeddit.com/search?q={encoded}"
        start_time = time.perf_counter()

        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=8)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            MusicatLogger.log_http("Hypeddit", url, resp.status_code, latency_ms, 0)

            if resp.status_code == 200:
                html = resp.text
                # Match Hypeddit track card anchors
                cards = re.findall(r'<div[^>]*class="[^"]*track-item[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
                for card in cards[:limit]:
                    t_m = re.search(r'title="([^"]+)"', card)
                    title = t_m.group(1) if t_m else "Hypeddit Edit"
                    results.append(
                        SocialTrackItem(
                            source="Hypeddit",
                            title=title,
                            artist="Hypeddit DJ",
                            remixer="Club Edit",
                            genre="EDM / House",
                            year=None,
                            bpm=None,
                            musical_key="",
                            camelot_key="",
                            artwork_url="",
                            stream_url=url,
                        )
                    )
        except Exception:
            pass

        return results

    @classmethod
    def search_remix_audio(cls, query: str, limit: int = 5) -> List[SocialTrackItem]:
        """Searches Remix.audio for community DJ remixes with BPM/Key tags."""
        results: List[SocialTrackItem] = []
        if not query:
            return results

        encoded = urllib.parse.quote_plus(query.strip())
        url = f"https://remix.audio/search?q={encoded}"
        start_time = time.perf_counter()

        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=8)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            MusicatLogger.log_http("Remix.audio", url, resp.status_code, latency_ms, 0)

            if resp.status_code == 200:
                html = resp.text
                items = re.findall(r'<div[^>]*class="[^"]*remix-card[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
                for item in items[:limit]:
                    name_m = re.search(r'<h3>([^<]+)</h3>', item)
                    name = name_m.group(1).strip() if name_m else query
                    bpm_m = re.search(r'(\d{2,3})\s*BPM', item)
                    bpm_val = float(bpm_m.group(1)) if bpm_m else None

                    results.append(
                        SocialTrackItem(
                            source="Remix.audio",
                            title=name,
                            artist="Remix Community",
                            remixer="DJ Remix",
                            genre="Club",
                            year=None,
                            bpm=bpm_val,
                            musical_key="",
                            camelot_key="",
                            artwork_url="",
                            stream_url=url,
                        )
                    )
        except Exception:
            pass

        return results

    @classmethod
    def search_all(cls, query: str, limit_per_source: int = 3) -> List[Dict[str, Any]]:
        """Queries all social & remix platforms and aggregates results.

        Args:
            query (str): Search term.
            limit_per_source (int): Max results per platform.

        Returns:
            List[Dict[str, Any]]: Aggregated track list.
        """
        aggregated: List[Dict[str, Any]] = []

        sc_items = cls.search_soundcloud(query, limit=limit_per_source)
        aggregated.extend([i.to_dict() for i in sc_items])

        yt_items = cls.search_youtube_music(query, limit=limit_per_source)
        aggregated.extend([i.to_dict() for i in yt_items])

        hyp_items = cls.search_hypeddit(query, limit=limit_per_source)
        aggregated.extend([i.to_dict() for i in hyp_items])

        rem_items = cls.search_remix_audio(query, limit=limit_per_source)
        aggregated.extend([i.to_dict() for i in rem_items])

        return aggregated
