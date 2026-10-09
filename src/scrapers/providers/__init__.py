"""
Musicat Specialized Scrapers & Metadata Providers.
Organized into 5 domain categories:
1. Discography, Physical Editions & Collectors (Discogs, 45cat, RYM, CD and LP)
2. Open Metadata, Credits & Musical Lineage (MusicBrainz, AllMusic, WhoSampled, SecondHandSongs, Genius)
3. Legal Repertoires, Rights & Codes (SIAE, ASCAP/BMI, ISRC, ISWC)
4. Historical Archives & Classical Music (IMSLP, RISM, Internet Culturale, DAHR)
5. Acoustic Parameters & Similarity Discovery (Tunebat/SongBPM, Chosic)
"""

from typing import Any, Dict, List, Optional, Type

from .base import BaseMetadataProvider, ProviderMetadataResult
from .discography import (
    DiscogsProvider,
    FortyFiveCatProvider,
    RateYourMusicProvider,
    CdAndLpProvider,
)
from .credits_lineage import (
    MusicBrainzProvider,
    AllMusicProvider,
    WhoSampledProvider,
    SecondHandSongsProvider,
    GeniusProvider,
)
from .legal_rights import (
    SiaeProvider,
    AscapBmiProvider,
    IsrcSearchProvider,
    IswcNetworkProvider,
)
from .historical import (
    ImslpProvider,
    RismProvider,
    InternetCulturaleProvider,
    DahrProvider,
)
from .acoustic_discovery import (
    TunebatSongBpmProvider,
    ChosicProvider,
)


ALL_PROVIDERS: List[Type[BaseMetadataProvider]] = [
    # 1. Discography & Physical
    DiscogsProvider,
    FortyFiveCatProvider,
    RateYourMusicProvider,
    CdAndLpProvider,
    # 2. Credits & Lineage
    MusicBrainzProvider,
    AllMusicProvider,
    WhoSampledProvider,
    SecondHandSongsProvider,
    GeniusProvider,
    # 3. Legal & Rights
    SiaeProvider,
    AscapBmiProvider,
    IsrcSearchProvider,
    IswcNetworkProvider,
    # 4. Historical Archives
    ImslpProvider,
    RismProvider,
    InternetCulturaleProvider,
    DahrProvider,
    # 5. Acoustic & Discovery
    TunebatSongBpmProvider,
    ChosicProvider,
]


class ProviderRegistry:
    """Central registry for discovering and querying specialized metadata providers."""

    @classmethod
    def get_providers(cls, category: Optional[str] = None) -> List[BaseMetadataProvider]:
        """Returns instantiated providers, optionally filtered by category name or keyword."""
        instances = [p_cls() for p_cls in ALL_PROVIDERS]
        if category:
            cat_lower = category.lower().strip()
            return [
                p for p in instances
                if p.category.lower() == cat_lower
                or cat_lower in p.category.lower()
                or (cat_lower == "acoustic_discovery" and "acustici" in p.category.lower())
                or (cat_lower == "discography" and "discograf" in p.category.lower())
                or (cat_lower == "credits_lineage" and "crediti" in p.category.lower())
                or (cat_lower == "legal_rights" and "legali" in p.category.lower())
                or (cat_lower == "historical" and "storici" in p.category.lower())
            ]
        return instances

    @classmethod
    def get_providers_by_category(cls) -> Dict[str, List[BaseMetadataProvider]]:
        """Returns instantiated providers mapped by category."""
        grouped: Dict[str, List[BaseMetadataProvider]] = {}
        for p_cls in ALL_PROVIDERS:
            inst = p_cls()
            grouped.setdefault(inst.category, []).append(inst)
        return grouped

    @classmethod
    def search_all(
        cls,
        query: str,
        artist: str = "",
        title: str = "",
        categories: Optional[List[str]] = None,
        limit_per_provider: int = 2,
    ) -> List[ProviderMetadataResult]:
        """Queries providers concurrently across designated categories."""
        results: List[ProviderMetadataResult] = []
        for p_cls in ALL_PROVIDERS:
            try:
                inst = p_cls()
                if categories and inst.category not in categories:
                    continue
                res = inst.search(query=query, artist=artist, title=title, limit=limit_per_provider)
                results.extend(res)
            except Exception:
                pass
        return results


__all__ = [
    "BaseMetadataProvider",
    "ProviderMetadataResult",
    "DiscogsProvider",
    "FortyFiveCatProvider",
    "RateYourMusicProvider",
    "CdAndLpProvider",
    "MusicBrainzProvider",
    "AllMusicProvider",
    "WhoSampledProvider",
    "SecondHandSongsProvider",
    "GeniusProvider",
    "SiaeProvider",
    "AscapBmiProvider",
    "IsrcSearchProvider",
    "IswcNetworkProvider",
    "ImslpProvider",
    "RismProvider",
    "InternetCulturaleProvider",
    "DahrProvider",
    "TunebatSongBpmProvider",
    "ChosicProvider",
    "ALL_PROVIDERS",
    "ProviderRegistry",
]
