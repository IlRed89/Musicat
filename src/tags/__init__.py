"""
Musicat Tags Module - unified tag editing and pattern translation.
"""

from .editor import AudioTagEditor, AudioMetadata, CoverArt, SUPPORTED_EXTENSIONS
from .patterns import PatternEngine, sanitize_filename, TAG_PATTERNS

__all__ = [
    "AudioTagEditor",
    "AudioMetadata",
    "CoverArt",
    "SUPPORTED_EXTENSIONS",
    "PatternEngine",
    "sanitize_filename",
    "TAG_PATTERNS",
]
