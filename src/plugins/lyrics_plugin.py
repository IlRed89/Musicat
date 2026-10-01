"""
Synchronized Lyrics & Vocal Detection Plugin for Musicat.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.plugins.base import BasePlugin


class LyricsPlugin(BasePlugin):
    """Fetches synchronized LRC and plain lyrics from LRCLIB and Genius."""

    @property
    def plugin_id(self) -> str:
        return "lyrics_fetcher"

    @property
    def name(self) -> str:
        return "Synced Lyrics & Vocals Assistant"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def author(self) -> str:
        return "Musicat Community"

    @property
    def description(self) -> str:
        return "Scarica testi sincronizzati (.lrc) o non sincronizzati da LRCLIB e Genius per tracce vocali."

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "genius_access_token",
                "label": "Genius Access Token (opzionale)",
                "type": "password",
                "default": "",
                "description": "Token API per arricchimento annotazioni da Genius.com",
            },
            {
                "key": "prefer_synced",
                "label": "Preferisci testi sincronizzati (.lrc)",
                "type": "bool",
                "default": True,
                "description": "Cerca file .lrc sincronizzati con timestamp al millisecondo",
            },
            {
                "key": "auto_save_lrc_file",
                "label": "Salva file .lrc a fianco del brano musicale",
                "type": "bool",
                "default": True,
                "description": "Crea una copia traccia.lrc nella cartella del file",
            },
        ]

    def initialize(self, context: Optional[Dict[str, Any]] = None) -> bool:
        return True

    def shutdown(self) -> None:
        pass
