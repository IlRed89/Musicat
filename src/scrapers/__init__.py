"""
Musicat Scrapers Module - Online metadata discovery from Beatport, AcoustID, MusicBrainz, and Discogs.
"""

from .beatport import BeatportScraper, ScrapedTrack
from .acoustid import AcoustIDMatcher, FingerprintMatch
from .musicbrainz import MusicBrainzClient
from .discogs import DiscogsClient

__all__ = [
    "BeatportScraper",
    "ScrapedTrack",
    "AcoustIDMatcher",
    "FingerprintMatch",
    "MusicBrainzClient",
    "DiscogsClient",
]
