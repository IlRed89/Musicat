"""
Beatport Scraping and API Client for Musicat.
Extracts dance/electronic metadata tailored for DJs:
Mix Name, Artists, Remixer, Label, Official BPM, Key, Subgenre, Release Date, High-Res Cover.
"""

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests


@dataclass
class ScrapedTrack:
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


class BeatportScraper:
    """Queries Beatport search and catalogs electronic track metadata."""

    BASE_URL = "https://www.beatport.com"
    SEARCH_URL = "https://www.beatport.com/search/tracks"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    @classmethod
    def search_tracks(cls, query: str, limit: int = 10) -> List[ScrapedTrack]:
        """
        Searches Beatport for matching tracks.
        Query can be 'Artist - Title' or general text.
        """
        results: List[ScrapedTrack] = []
        if not query or not query.strip():
            return results

        encoded_q = urllib.parse.quote_plus(query.strip())
        target_url = f"{cls.SEARCH_URL}?q={encoded_q}"

        try:
            resp = requests.get(target_url, headers=cls.HEADERS, timeout=10)
            if resp.status_code != 200:
                return results

            html = resp.text

            # Look for Next.js hydration __NEXT_DATA__ JSON script
            next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
            if next_data_match:
                try:
                    payload = json.loads(next_data_match.group(1))
                    props = payload.get("props", {}).get("pageProps", {})
                    # Tracks can be in props['tracks']['data'] or props['dehydratedState']['queries']
                    tracks_data = props.get("tracks", {}).get("data", [])
                    if not tracks_data:
                        # Inspect dehydrated state
                        queries = props.get("dehydratedState", {}).get("queries", [])
                        for q in queries:
                            data = q.get("state", {}).get("data", {})
                            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                                tracks_data = data["data"]
                                break

                    for item in tracks_data[:limit]:
                        track_obj = cls._parse_beatport_json_item(item)
                        if track_obj:
                            results.append(track_obj)
                    if results:
                        return results
                except Exception:
                    pass

            # Fallback: HTML Scraping with Regex
            results = cls._parse_beatport_html(html, limit)

        except Exception:
            pass

        return results

    @classmethod
    def _parse_beatport_json_item(cls, item: Dict[str, Any]) -> Optional[ScrapedTrack]:
        """Parses a track entry from Beatport internal API JSON."""
        from ..audio.analyzer import key_to_camelot

        try:
            name = item.get("name") or item.get("track_name", "")
            mix = item.get("mix_name") or item.get("mix", "")
            artists = [a.get("name") for a in item.get("artists", []) if a.get("name")]
            remixers = [r.get("name") for r in item.get("remixers", []) if r.get("name")]

            release = item.get("release", {})
            label_obj = release.get("label") or item.get("label", {})
            label = label_obj.get("name") if isinstance(label_obj, dict) else str(label_obj)

            rel_date = item.get("publish_date") or release.get("publish_date") or ""
            year = int(rel_date[:4]) if rel_date and rel_date[:4].isdigit() else None

            genre_obj = item.get("genre")
            genre = genre_obj.get("name") if isinstance(genre_obj, dict) else ""

            bpm = float(item.get("bpm")) if item.get("bpm") else None
            key_obj = item.get("key")
            key_name = key_obj.get("name") if isinstance(key_obj, dict) else (str(key_obj) if key_obj else "")
            camelot = key_to_camelot(key_name) if key_name else ""

            # Artwork: image.uri or release.image.uri
            image_obj = item.get("image") or release.get("image", {})
            art_url = image_obj.get("uri") or ""
            if art_url and not art_url.startswith("http"):
                art_url = f"https://geo-media.beatport.com/image_size/500x500/{art_url.lstrip('/')}"

            slug = item.get("slug", "")
            track_id = item.get("id", "")
            track_url = f"{cls.BASE_URL}/track/{slug}/{track_id}" if slug and track_id else ""

            return ScrapedTrack(
                source="Beatport",
                title=name,
                mix_name=mix,
                artists=artists if artists else ["Unknown Artist"],
                remixers=remixers,
                label=label,
                release_date=rel_date,
                year=year,
                genre=genre,
                bpm=bpm,
                musical_key=key_name,
                camelot_key=camelot,
                catalog_number=release.get("catalog_number", ""),
                artwork_url=art_url,
                url=track_url,
            )
        except Exception:
            return None

    @classmethod
    def _parse_beatport_html(cls, html: str, limit: int) -> List[ScrapedTrack]:
        """Fallback regex parser for Beatport track table."""
        from ..audio.analyzer import key_to_camelot
        results: List[ScrapedTrack] = []

        # Find track rows or card blocks
        blocks = re.findall(r'<div[^>]*data-testid="track-item"[^>]*>.*?</div>\s*</div>\s*</div>', html, re.DOTALL)
        if not blocks:
            # Try alternate pattern
            blocks = re.findall(r'<li[^>]*class="[^"]*bucket-item[^"]*"[^>]*>.*?</li>', html, re.DOTALL)

        for block in blocks[:limit]:
            try:
                title_m = re.search(r'title="([^"]+)"', block)
                title = title_m.group(1) if title_m else "Unknown"

                bpm_m = re.search(r'(\d{2,3})\s*BPM', block, re.IGNORECASE)
                bpm = float(bpm_m.group(1)) if bpm_m else None

                key_m = re.search(r'\b([A-G][b#]?(?:m|maj|min)?)\b', block)
                musical_key = key_m.group(1) if key_m else ""
                camelot = key_to_camelot(musical_key)

                results.append(
                    ScrapedTrack(
                        source="Beatport",
                        title=title,
                        mix_name="Original Mix",
                        artists=["Unknown Artist"],
                        remixers=[],
                        label="",
                        release_date="",
                        year=None,
                        genre="",
                        bpm=bpm,
                        musical_key=musical_key,
                        camelot_key=camelot,
                        catalog_number="",
                        artwork_url="",
                        url="",
                    )
                )
            except Exception:
                continue

        return results

    @classmethod
    def download_artwork(cls, image_url: str) -> Optional[bytes]:
        """Downloads high resolution artwork bytes."""
        if not image_url:
            return None
        try:
            resp = requests.get(image_url, headers=cls.HEADERS, timeout=10)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None
