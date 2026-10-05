"""
Discogs Scraping and API Client for Musicat.
Provides vinyl and digital release details: Catalog Number, Record Label, Styles, Country, Formats, and Credits.
Treats Discogs as primary authority for original release year, record label, catalog number, artist credits, and release formats.
"""

from typing import Any, Dict, List, Optional
import urllib.parse
import requests

from ..core.logger import MusicatLogger
from ..core.settings import SettingsManager


class DiscogsClient:
    """Queries Discogs database for physical and digital electronic releases."""

    BASE_URL = "https://api.discogs.com/database/search"
    RELEASE_URL = "https://api.discogs.com/releases"

    def __init__(self, token: Optional[str] = None):
        if not token:
            try:
                token = SettingsManager.get_instance().get("scrapers", "discogs_token", "")
            except Exception:
                token = ""
        self.token = token.strip() if token else ""
        self.headers = {
            "User-Agent": "Musicat/1.1.0 (+https://github.com/IlRed89/Musicat)",
            "Accept": "application/json",
        }
        if self.token:
            self.headers["Authorization"] = f"Discogs token={self.token}"

    def search_releases(
        self,
        query: str,
        artist: str = "",
        label: str = "",
        catno: str = "",
        limit: int = 5,
        fetch_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """Searches Discogs for matching releases with priority for physical/digital vinyl & club formats.

        Args:
            query: Free-text search query.
            artist: Filter by artist name.
            label: Filter by label name.
            catno: Filter by catalog number.
            limit: Maximum results to return.
            fetch_details: Whether to fetch full release record for the top result.

        Returns:
            List of normalized release dictionaries.
        """
        results: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {"per_page": limit, "type": "release"}

        if query:
            params["q"] = query
        if artist:
            params["artist"] = artist
        if label:
            params["label"] = label
        if catno:
            params["catno"] = catno

        try:
            resp = requests.get(self.BASE_URL, headers=self.headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    # Title on Discogs search result is commonly formatted as 'Artist - Title'
                    full_title = item.get("title", "")
                    art_parts = full_title.split(" - ", 1)
                    parsed_artist = art_parts[0].strip() if len(art_parts) > 1 else ""
                    parsed_title = art_parts[1].strip() if len(art_parts) > 1 else full_title.strip()

                    # Label & Catalog Number
                    labels_list = item.get("label", [])
                    main_label = labels_list[0] if isinstance(labels_list, list) and labels_list else str(labels_list)
                    cat_num = item.get("catno", "")

                    # Formats description (e.g. '12", 33 ⅓ RPM, Vinyl, Maxi-Single')
                    raw_formats = item.get("format", [])
                    format_str = ", ".join(raw_formats) if isinstance(raw_formats, list) else str(raw_formats)

                    # Year
                    year_val = None
                    raw_year = item.get("year")
                    if raw_year and str(raw_year).isdigit():
                        year_val = int(raw_year)

                    rel_id = item.get("id")

                    styles_list = item.get("style", [])
                    genres_list = item.get("genre", [])
                    # Specific electronic style takes precedence over broad genre
                    discogs_genre = ", ".join(styles_list) if styles_list else ", ".join(genres_list)

                    res_dict = {
                        "source": "Discogs",
                        "discogs_id": rel_id,
                        "title": parsed_title,
                        "artist": parsed_artist or artist,
                        "year": year_val,
                        "label": main_label,
                        "catalog_number": cat_num,
                        "genre": discogs_genre,
                        "style": ", ".join(styles_list),
                        "artwork_url": item.get("cover_image") or item.get("thumb", ""),
                        "country": item.get("country", ""),
                        "format": format_str,
                        "url": f"https://www.discogs.com{item.get('uri', '')}",
                    }

                    results.append(res_dict)

                # If details requested and top result exists, enrich with accurate tracklist & credits
                if fetch_details and results and results[0].get("discogs_id"):
                    details = self.get_release_details(results[0]["discogs_id"])
                    if details:
                        results[0].update(details)

        except Exception as exc:
            MusicatLogger.get_logger().warning(f"[DISCOGS] Query search error for '{query}': {exc}")

        return results

    def get_release_details(self, release_id: int) -> Dict[str, Any]:
        """Fetches detailed release profile directly from Discogs /releases/{id}."""
        out: Dict[str, Any] = {}
        try:
            url = f"{self.RELEASE_URL}/{release_id}"
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()

                # Detailed year / released date
                released_str = data.get("released", "") or data.get("released_formatted", "")
                year_candidate = None
                if released_str and len(released_str) >= 4 and released_str[:4].isdigit():
                    year_candidate = int(released_str[:4])
                elif data.get("year"):
                    year_candidate = int(data["year"])

                if year_candidate:
                    out["year"] = year_candidate

                # Detailed labels & catno
                labels = data.get("labels", [])
                if labels and isinstance(labels, list):
                    l0 = labels[0]
                    if l0.get("name"):
                        out["label"] = l0.get("name")
                    if l0.get("catno"):
                        out["catalog_number"] = l0.get("catno")

                # Detailed formats (Vinyl 12", 45 RPM, Maxi-Single, FLAC, etc.)
                formats = data.get("formats", [])
                if formats and isinstance(formats, list):
                    f_parts = []
                    for f in formats:
                        name = f.get("name", "")
                        descriptions = f.get("descriptions", [])
                        desc_str = ", ".join(descriptions) if descriptions else ""
                        f_parts.append(f"{name} ({desc_str})" if desc_str else name)
                    if f_parts:
                        out["format"] = "; ".join(f_parts)

                # Detailed Artist credits
                artists = data.get("artists", [])
                if artists and isinstance(artists, list):
                    art_names = [a.get("name", "") for a in artists if a.get("name")]
                    if art_names:
                        out["artist"] = ", ".join(art_names)

                # Extra artists (Remixers, producers, feat)
                if remixers:
                    out["remixer"] = ", ".join(remixers)

                # Detailed Genre & Style (Style prioritized for subgenres)
                styles = data.get("styles", []) or data.get("style", [])
                genres = data.get("genres", []) or data.get("genre", [])
                primary_genre = ", ".join(styles) if styles else ", ".join(genres)
                if primary_genre:
                    out["genre"] = primary_genre
                if styles:
                    out["style"] = ", ".join(styles)

        except Exception as exc:
            MusicatLogger.get_logger().debug(f"[DISCOGS] Could not fetch details for release {release_id}: {exc}")

        return out
