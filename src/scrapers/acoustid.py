"""
AcoustID & Chromaprint Acoustic Fingerprint Engine for Musicat.
Identifies untagged tracks or tracks with mangled filenames via acoustic fingerprinting.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import acoustid


# Default Musicat client key registered for AcoustID lookup
DEFAULT_ACOUSTID_API_KEY = "cSpUJKpD"  # Official pyacoustid public demo key or user key


@dataclass
class FingerprintMatch:
    score: float
    title: str
    artist: str
    album: str
    musicbrainz_id: str
    year: Optional[int] = None


class AcoustIDMatcher:
    """Computes Chromaprint fingerprints and queries AcoustID / MusicBrainz."""

    def __init__(self, api_key: str = DEFAULT_ACOUSTID_API_KEY):
        self.api_key = api_key

    def identify_track(self, filepath: Union[str, Path]) -> List[FingerprintMatch]:
        """
        Calculates fingerprint and queries the AcoustID database.
        Returns sorted list of matches by confidence score.
        """
        path_str = str(filepath)
        results: List[FingerprintMatch] = []

        try:
            # acoustid.match returns generator of (score, recording_id, title, artist)
            for score, recording_id, title, artist in acoustid.match(self.api_key, path_str):
                results.append(
                    FingerprintMatch(
                        score=round(float(score), 2),
                        title=title or "Unknown",
                        artist=artist or "Unknown",
                        album="",
                        musicbrainz_id=recording_id or "",
                    )
                )
        except acoustid.NoBackendError:
            # fpcalc binary not found on system PATH
            pass
        except Exception:
            pass

        return results
