"""
Web & YouTube Scraping Fallback Enricher for Musicat.
Executes targeted web and YouTube queries ("Artist - Title genre year") to retrieve
canonical release year and musical genre when primary DJ databases have no matches.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List, Optional
import requests

from ..core.logger import MusicatLogger
from ..core.settings import SettingsManager


KNOWN_ELECTRONIC_SUBGENRES = [
    "Tech House", "Melodic Techno", "Afro House", "Deep House", "Progressive House",
    "Peak Time Techno", "Hard Techno", "Minimal / Deep Tech", "Minimal Techno",
    "Nu Disco", "Disco", "Drum & Bass", "Liquid Drum & Bass", "Trance", "Psy-Trance",
    "Uplifting Trance", "Indie Dance", "Electro House", "Bass House", "Future House",
    "Future Rave", "Organic House", "Downtempo", "Melodic House", "UK Garage", "Speed Garage",
    "Hardstyle", "Hardcore", "Dubstep", "Trap", "Acapella", "Synthwave", "Italo-Disco",
    "House", "Techno", "Dance", "Electronic", "EDM", "Pop", "Hip Hop", "R&B", "Rock"
]


class WebEnricher:
    """Fallback web & YouTube scraper for genre and release year metadata enrichment."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    @classmethod
    def search_genre_and_year(cls, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """Executes a cascading web search fallback query '[Artist] - [Title] genre year'.

        Tries:
        1. Wikipedia Music Knowledge Graph API (accurate release year & infobox genre)
        2. YouTube Music / YouTube video metadata parsing (auto-generated audio release date & description)
        3. Web snippet heuristic parsing

        Returns:
            Dictionary with parsed metadata or None if nothing found.
        """
        clean_artist = (artist or "").strip()
        clean_title = (title or "").strip()
        if not clean_title:
            return None

        # 1. Wikipedia Knowledge Graph Search
        wiki_result = cls._search_wikipedia(clean_artist, clean_title)
        if wiki_result and (wiki_result.get("year") or wiki_result.get("genre")):
            return wiki_result

        # 2. YouTube Search & Metadata
        yt_result = cls._search_youtube(clean_artist, clean_title)
        if yt_result and (yt_result.get("year") or yt_result.get("genre")):
            return yt_result

        return None

    @classmethod
    def _search_wikipedia(cls, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """Queries Wikipedia API for track infoboxes and lead paragraphs."""
        try:
            search_query = f"{artist} {title} song" if artist else f"{title} song"
            encoded_query = urllib.parse.quote_plus(search_query)
            search_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&list=search"
                f"&srsearch={encoded_query}&format=json&srlimit=2"
            )

            resp = requests.get(search_url, headers=cls.HEADERS, timeout=6)
            if resp.status_code != 200:
                return None

            data = resp.json()
            search_items = data.get("query", {}).get("search", [])
            if not search_items:
                return None

            page_title = search_items[0].get("title", "")
            if not page_title:
                return None

            # Fetch page wikitext content and intro extract
            encoded_title = urllib.parse.quote_plus(page_title)
            content_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&prop=revisions|extracts"
                f"&rvprop=content&rvslots=main&exintro=1&explaintext=1&titles={encoded_title}&format=json"
            )

            c_resp = requests.get(content_url, headers=cls.HEADERS, timeout=6)
            if c_resp.status_code != 200:
                return None

            pages = c_resp.json().get("query", {}).get("pages", {})
            if not pages:
                return None

            page_data = list(pages.values())[0]
            wikitext = str(page_data)

            # 1. Parse Year
            found_year: Optional[int] = None
            year_match = re.search(r'released\s*=\s*.*?((?:19|20)\d{2})', wikitext, re.IGNORECASE)
            if year_match:
                found_year = int(year_match.group(1))
            else:
                extract = page_data.get("extract", "")
                rel_match = re.search(r'released (?:on |in )?(?:[0-9]{1,2} [A-Za-z]+ )?((?:19|20)\d{2})', extract, re.IGNORECASE)
                if rel_match:
                    found_year = int(rel_match.group(1))

            # 2. Parse Genre from infobox
            found_genre: Optional[str] = None
            genre_match = re.search(r'genre\s*=\s*(?:\[\[)?([^\]\n\|]+)(?:\]\])?', wikitext, re.IGNORECASE)
            if genre_match:
                raw_g = genre_match.group(1).strip()
                # Clean up wikitext syntax
                raw_g = re.sub(r'\[\[|\]\]|\{\{|\}\}', '', raw_g).strip()
                if raw_g and len(raw_g) > 2:
                    found_genre = raw_g.title()

            # If no infobox genre, check if known electronic subgenres appear in extract
            if not found_genre:
                extract = page_data.get("extract", "")
                for subg in KNOWN_ELECTRONIC_SUBGENRES:
                    if re.search(rf'\b{re.escape(subg)}\b', extract, re.IGNORECASE):
                        found_genre = subg
                        break

            # 3. Parse Label
            found_label: Optional[str] = None
            label_match = re.search(r'label\s*=\s*(?:\[\[)?([^\]\n\|]+)(?:\]\])?', wikitext, re.IGNORECASE)
            if label_match:
                found_label = re.sub(r'\[\[|\]\]|\{\{|\}\}', '', label_match.group(1)).strip()

            if found_year or found_genre:
                return {
                    "source": "Web/YouTube",
                    "title": title,
                    "artist": artist,
                    "year": found_year,
                    "genre": found_genre or "",
                    "label": found_label or "",
                }
        except Exception as exc:
            MusicatLogger.debug("WEB_ENRICHER:WIKI", f"Wikipedia lookup error for '{artist} - {title}': {exc}")

        return None

    @classmethod
    def _search_youtube(cls, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """Queries YouTube search results page to parse official audio release dates and descriptions."""
        try:
            query = f"{artist} - {title} audio" if artist else f"{title} audio"
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://www.youtube.com/results?search_query={encoded_query}"

            resp = requests.get(url, headers=cls.HEADERS, timeout=7)
            if resp.status_code != 200:
                return None

            html = resp.text

            # Parse release dates or publication year
            found_year: Optional[int] = None
            # Check copyright symbols or "Released on" strings commonly found in YouTube Music descriptions
            year_matches = re.findall(r'(?:Released on: |℗\s*|©\s*)((?:19|20)\d{2})', html)
            if year_matches:
                found_year = int(year_matches[0])
            else:
                # Video upload year fallback
                date_match = re.search(r'"publishDate":"((?:19|20)\d{2})-\d{2}-\d{2}"', html)
                if date_match:
                    found_year = int(date_match.group(1))

            # Scan for known electronic genres in titles / description snippets
            found_genre: Optional[str] = None
            for subg in KNOWN_ELECTRONIC_SUBGENRES:
                if re.search(rf'\b{re.escape(subg)}\b', html[:40000], re.IGNORECASE):
                    found_genre = subg
                    break

            if found_year or found_genre:
                return {
                    "source": "Web/YouTube",
                    "title": title,
                    "artist": artist,
                    "year": found_year,
                    "genre": found_genre or "",
                }
        except Exception as exc:
            MusicatLogger.debug("WEB_ENRICHER:YT", f"YouTube fallback error: {exc}")

        return None
