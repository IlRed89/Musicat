"""
Base Metadata Provider Interface for Musicat.
Provides standard structured data models and query contract for all specialized scrapers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderMetadataResult:
    """Standardized metadata record returned by any provider."""

    source: str
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    subgenres: List[str] = field(default_factory=list)
    year: Optional[int] = None
    original_year: Optional[int] = None
    label: str = ""
    catalog_number: str = ""
    barcode: str = ""
    matrix_runout: str = ""
    format: str = ""
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    camelot_key: Optional[str] = None
    isrc: str = ""
    iswc: str = ""
    mbid: str = ""
    composers: List[str] = field(default_factory=list)
    producers: List[str] = field(default_factory=list)
    rights_holders: List[Dict[str, Any]] = field(default_factory=list)
    samples: List[Dict[str, str]] = field(default_factory=list)  # {"type": "sample|cover|remix", "track": "..."}
    acoustic_features: Dict[str, float] = field(default_factory=dict)  # energy, danceability, valence
    extra_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes result into standardized dictionary."""
        d = {
            "source": self.source,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "genre": self.genre,
            "subgenres": self.subgenres,
            "year": self.year,
            "original_year": self.original_year or self.year,
            "label": self.label,
            "catalog_number": self.catalog_number,
            "barcode": self.barcode,
            "matrix_runout": self.matrix_runout,
            "format": self.format,
            "bpm": self.bpm,
            "musical_key": self.musical_key,
            "camelot_key": self.camelot_key,
            "isrc": self.isrc,
            "iswc": self.iswc,
            "mbid": self.mbid,
            "composers": self.composers,
            "producers": self.producers,
            "rights_holders": self.rights_holders,
            "samples": self.samples,
            "acoustic_features": self.acoustic_features,
        }
        d.update(self.extra_details)
        return d


class BaseMetadataProvider(ABC):
    """Abstract base class for all metadata and audio discovery providers."""

    name: str = "BaseProvider"
    category: str = "General"
    description: str = ""

    @abstractmethod
    def search(
        self,
        query: str,
        artist: str = "",
        title: str = "",
        limit: int = 5,
        **kwargs: Any,
    ) -> List[ProviderMetadataResult]:
        """Executes a search query and returns standardized metadata results."""
        pass

    def get_provider_info(self) -> Dict[str, str]:
        """Returns provider identity and metadata."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
        }
