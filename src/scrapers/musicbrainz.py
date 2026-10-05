"""
MusicBrainz Client for Musicat.
Retrieves canonical album releases, dates, labels, track numbers, and ISRCs.
"""

from typing import Any, Dict, List, Optional
import musicbrainzngs


musicbrainzngs.set_useragent("Musicat", "1.0.0", "https://github.com/IlRed89/Musicat")
# Set polite rate limit
musicbrainzngs.set_rate_limit(limit_or_interval=1.0, new_requests=1)


class MusicBrainzClient:
    """Wrapper around musicbrainzngs with DJ metadata parsing."""

    @classmethod
    def search_track(cls, title: str, artist: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """Searches MusicBrainz recordings."""
        results: List[Dict[str, Any]] = []
        if not title:
            return results

        try:
            query_parts = [f'recording:"{title}"']
            if artist:
                query_parts.append(f'artist:"{artist}"')
            query = " AND ".join(query_parts)

            response = musicbrainzngs.search_recordings(query=query, limit=limit)
            for rec in response.get("recording-list", []):
                rec_title = rec.get("title", "")
                artist_credit = ""
                if "artist-credit" in rec:
                    artists = []
                    for ac in rec["artist-credit"]:
                        if isinstance(ac, dict) and "artist" in ac:
                            artists.append(ac["artist"].get("name", ""))
                    artist_credit = ", ".join([a for a in artists if a])

                releases = rec.get("release-list", [])
                album_name = releases[0].get("title", "") if releases else ""
                year = None
                date_str = releases[0].get("date", "") if releases else ""
                if date_str and len(date_str) >= 4 and date_str[:4].isdigit():
                    year = int(date_str[:4])

                # Extract community style & genre tags
                tags = []
                for t in rec.get("tag-list", []):
                    if isinstance(t, dict) and t.get("name"):
                        tags.append(t.get("name").title())
                for rel in releases[:1]:
                    for t in rel.get("tag-list", []):
                        if isinstance(t, dict) and t.get("name"):
                            tname = t.get("name").title()
                            if tname not in tags:
                                tags.append(tname)
                genre_val = ", ".join(tags) if tags else ""

                results.append({
                    "source": "MusicBrainz",
                    "title": rec_title,
                    "artist": artist_credit,
                    "album": album_name,
                    "year": year,
                    "genre": genre_val,
                    "release_date": date_str,
                    "mbid": rec.get("id", ""),
                    "isrc": rec.get("isrc-list", [None])[0] if "isrc-list" in rec else None,
                })
        except Exception:
            pass

        return results
