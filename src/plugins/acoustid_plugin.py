"""
AcoustID & Chromaprint Audio Fingerprinting Plugin for Musicat.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.plugins.base import BasePlugin


class AcoustIdPlugin(BasePlugin):
    """Integrates AcoustID fingerprinting for missing tag identification."""

    @property
    def plugin_id(self) -> str:
        return "acoustid_fingerprint"

    @property
    def name(self) -> str:
        return "AcoustID & Chromaprint Engine"

    @property
    def version(self) -> str:
        return "1.1.0"

    @property
    def author(self) -> str:
        return "Musicat Core Team"

    @property
    def description(self) -> str:
        return "Riconosce brani con tag mancanti tramite impronta acustica su database AcoustID/MusicBrainz."

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "client_api_key",
                "label": "AcoustID API Key",
                "type": "str",
                "default": "8XaBELgH",
                "description": "API Key personale per query AcoustID",
            },
            {
                "key": "auto_fingerprint_on_scan",
                "label": "Calcola fingerprint automaticamente durante la scansione",
                "type": "bool",
                "default": False,
                "description": "Se attivo, calcola l'impronta sui file senza tag durante l'importazione",
            },
        ]

    def initialize(self, context: Optional[Dict[str, Any]] = None) -> bool:
        return True

    def shutdown(self) -> None:
        pass
