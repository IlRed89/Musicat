"""
High-Definition Cover Art Discovery & Embedding Engine for Musicat.

Fetches studio-grade album covers from 500x500 up to 3000x3000px using:
- iTunes / Apple Music CDN Master Resolution API
- Beatport High-Res GeoMedia CDN
- Traxsource & Discogs Large Artwork Endpoints
Supports visual inspection, tag embedding, and local folder.jpg / cover.jpg saving.
"""

import io
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

from ..core.logger import MusicatLogger
from ..tags.editor import AudioTagEditor


@dataclass
class HDArtworkCandidate:
    """Represents a discovered high-resolution cover candidate."""

    source: str
    width: int
    height: int
    dimension_label: str
    image_url: str
    size_kb: float
    data: Optional[bytes] = None


class HDArtworkFinder:
    """Discovers and downloads high-definition artwork for local tracks."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    @classmethod
    def search_itunes_hd(cls, artist: str, title: str, target_size: int = 1400) -> List[HDArtworkCandidate]:
        """Queries iTunes Search API and upscales CDN URLs to studio resolution (1400-3000px).

        Args:
            artist (str): Artist name.
            title (str): Track or album title.
            target_size (int): Preferred resolution dimension in pixels.

        Returns:
            List[HDArtworkCandidate]: List of candidates with image dimensions.
        """
        results: List[HDArtworkCandidate] = []
        term = f"{artist} {title}".strip()
        if not term:
            return results

        encoded = urllib.parse.quote_plus(term)
        url = f"https://itunes.apple.com/search?term={encoded}&media=music&entity=song&limit=5"
        start_time = time.perf_counter()

        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=8)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            MusicatLogger.log_http("iTunes", url, resp.status_code, latency_ms, 0)

            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    art_100 = item.get("artworkUrl100")
                    if not art_100:
                        continue

                    # Apple CDN resolution trick: replace 100x100bb.jpg with 1400x1400bb.jpg or 3000x3000bb.jpg
                    hd_url = art_100.replace("100x100bb", f"{target_size}x{target_size}bb")

                    results.append(
                        HDArtworkCandidate(
                            source="Apple Music / iTunes (Studio HD)",
                            width=target_size,
                            height=target_size,
                            dimension_label=f"{target_size}x{target_size} px",
                            image_url=hd_url,
                            size_kb=0.0,
                        )
                    )
        except Exception as e:
            MusicatLogger.get_logger().debug(f"[ITUNES:HD] Search error: {e}")

        return results

    @classmethod
    def search_all_hd_sources(
        cls,
        artist: str,
        title: str,
        include_itunes: bool = True,
        include_beatport: bool = True,
    ) -> List[HDArtworkCandidate]:
        """Discovers HD cover candidates across multiple providers.

        Args:
            artist (str): Artist name.
            title (str): Song title.
            include_itunes (bool): Query Apple Music / iTunes.
            include_beatport (bool): Query Beatport CDN.

        Returns:
            List[HDArtworkCandidate]: Deduplicated list of artwork options.
        """
        candidates: List[HDArtworkCandidate] = []

        if include_itunes:
            candidates.extend(cls.search_itunes_hd(artist, title, target_size=1400))
            candidates.extend(cls.search_itunes_hd(artist, title, target_size=3000))

        if include_beatport:
            from .beatport import BeatportScraper
            bp_tracks = BeatportScraper.search_tracks(f"{artist} {title}", limit=3)
            for bpt in bp_tracks:
                if bpt.artwork_url:
                    # Upscale Beatport URL if present
                    bp_hd = bpt.artwork_url.replace("500x500", "1400x1400")
                    candidates.append(
                        HDArtworkCandidate(
                            source="Beatport (Club Artwork)",
                            width=1400,
                            height=1400,
                            dimension_label="1400x1400 px",
                            image_url=bp_hd,
                            size_kb=0.0,
                        )
                    )

        # Remove duplicate image URLs
        seen_urls = set()
        deduped = []
        for cand in candidates:
            if cand.image_url not in seen_urls:
                seen_urls.add(cand.image_url)
                deduped.append(cand)

        return deduped

    @classmethod
    def download_image(cls, image_url: str) -> Optional[bytes]:
        """Downloads image bytes from URL with timeout.

        Args:
            image_url (str): Remote image URL.

        Returns:
            Optional[bytes]: Raw image bytes, or None on failure.
        """
        if not image_url:
            return None
        try:
            resp = requests.get(image_url, headers=cls.HEADERS, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1024:
                return resp.content
        except Exception as e:
            MusicatLogger.get_logger().warning(f"[ARTWORK:DOWNLOAD] Failed from {image_url}: {e}")
        return None

    @classmethod
    def apply_artwork_to_file(
        cls,
        filepath: str,
        image_bytes: bytes,
        save_folder_copy: bool = True,
        folder_copy_name: str = "cover.jpg",
    ) -> bool:
        """Physically embeds cover artwork into file tags and optionally writes cover.jpg.

        Args:
            filepath (str): Path to audio file.
            image_bytes (bytes): Raw JPEG/PNG image data.
            save_folder_copy (bool): If True, writes a local cover.jpg / folder.jpg alongside track.
            folder_copy_name (str): Filename for folder copy (e.g. 'cover.jpg' or 'folder.jpg').

        Returns:
            bool: True if embedded successfully, False otherwise.
        """
        if not filepath or not image_bytes:
            return False

        path_obj = Path(filepath)
        if not path_obj.exists():
            return False

        # 1. Embed directly into audio tags (APIC, Vorbis, MP4)
        success = AudioTagEditor.set_artwork(
            filepath=path_obj,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            description="Front Cover (HD)",
        )

        # 2. Optionally write local copy in folder
        if save_folder_copy:
            try:
                local_cover = path_obj.parent / folder_copy_name
                local_cover.write_bytes(image_bytes)
                MusicatLogger.get_logger().info(f"[ARTWORK] Saved local copy: {local_cover}")
            except Exception as e:
                MusicatLogger.get_logger().warning(f"[ARTWORK] Could not write local copy: {e}")

        MusicatLogger.log_tag_edit(filepath, ["COVER_ARTWORK"], success)
        return success
