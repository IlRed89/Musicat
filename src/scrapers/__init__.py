"""
Musicat Scrapers Module - Online metadata discovery and discrepancy reconciliation.
"""

from .beatport import BeatportScraper, ScrapedTrack
from .traxsource import TraxsourceScraper, TraxsourceTrack
from .acoustid import AcoustIDMatcher, FingerprintMatch
from .musicbrainz import MusicBrainzClient
from .discogs import DiscogsClient
from .social_remix import SocialRemixScraper, SocialTrackItem
from .artwork_hd import HDArtworkFinder, HDArtworkCandidate
from .reconciler import MetadataReconciler, DiscrepancyReport, FieldDiscrepancy

__all__ = [
    "BeatportScraper",
    "ScrapedTrack",
    "TraxsourceScraper",
    "TraxsourceTrack",
    "AcoustIDMatcher",
    "FingerprintMatch",
    "MusicBrainzClient",
    "DiscogsClient",
    "SocialRemixScraper",
    "SocialTrackItem",
    "HDArtworkFinder",
    "HDArtworkCandidate",
    "MetadataReconciler",
    "DiscrepancyReport",
    "FieldDiscrepancy",
]
