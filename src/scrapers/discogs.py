"""
Discogs Scraping and API Client for Musicat.
Provides vinyl and digital release details: Catalog Number, Record Label, Styles, Country.
"""

from typing import Any, Dict, List, Optional
import urllib.parse
import requests


class DiscogsClient:
    """Queries Discogs database for physical and digital electronic releases."""

    BASE_URL = "https://api.discogs.com/database/search"

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {
            "User-Agent": "Musicat/1.0.0 (https://github.com/IlRed89/Musicat)",
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
    ) -> List[Dict[str, Any]]:
        """Searches Discogs for matching releases."""
        results: List[Dict[str, Any]] = []
        params = {"per_page": limit, "type": "release"}

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
                    # Title on Discogs is often 'Artist - Title'
                    full_title = item.get("title", "")
                    art_parts = full_title.split(" - ", 1)
                    parsed_artist = art_parts[0] if len(art_parts) > 1 else ""
                    parsed_title = art_parts[1] if len(art_parts) > 1 else full_title

                    results.append({
                        "source": "Discogs",
                        "title": parsed_title,
                        "artist": parsed_artist,
                        "year": int(item.get("year")) if str(item.get("year", "")).isdigit() else None,
                        "label": item.get("label", [""])[0] if isinstance(item.get("label"), list) else "",
                        "catalog_number": item.get("catno", ""),
                        "genre": ", ".join(item.get("genre", [])),
                        "style": ", ".join(item.get("style", [])),
                        "artwork_url": item.get("cover_image") or item.get("thumb", ""),
                        "country": item.get("country", ""),
                        "format": ", ".join(item.get("format", [])),
                        "url": f"https://www.discogs.com{item.get('uri', '')}",
                    })
        except Exception:
            pass

        return results
