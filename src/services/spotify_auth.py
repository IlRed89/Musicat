"""
Spotify OAuth2 Authentication Handler for Musicat.

Generates official authorization URLs with 'response_type=code', handles loopback
callbacks, and exchanges authorization codes for Bearer access tokens.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Optional
import requests

from ..core.logger import MusicatLogger


class SpotifyAuth:
    """Manages Spotify OAuth2 Authorization Code flow."""

    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    DEFAULT_REDIRECT_URI = "http://localhost:8888/callback"
    DEFAULT_SCOPE = (
        "user-read-playback-state user-read-private user-read-email "
        "playlist-read-private playlist-modify-public playlist-modify-private"
    )

    @classmethod
    def build_authorization_url(
        cls,
        client_id: str,
        redirect_uri: str = DEFAULT_REDIRECT_URI,
        scope: Optional[str] = None,
        state: Optional[str] = None,
    ) -> str:
        """
        Builds the standard Spotify OAuth2 authorization URL.
        Guarantees response_type='code' as required by the Spotify Accounts service.
        """
        params: Dict[str, str] = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scope or cls.DEFAULT_SCOPE,
            "show_dialog": "true",
        }
        if state:
            params["state"] = state

        query_str = urllib.parse.urlencode(params)
        return f"{cls.AUTH_URL}?{query_str}"

    @classmethod
    def exchange_code_for_token(
        cls,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str = DEFAULT_REDIRECT_URI,
        timeout: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Exchanges the authorization code received via localhost callback for an access token.
        """
        if not code or not client_id:
            return {"error": "Parametri non validi per lo scambio del token"}

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
        }
        if client_secret:
            data["client_secret"] = client_secret

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Musicat/1.2",
        }

        try:
            resp = requests.post(cls.TOKEN_URL, data=data, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Scambio token fallito: HTTP {resp.status_code} - {resp.text}"}
        except Exception as exc:
            MusicatLogger.error("SPOTIFY_AUTH", f"Token exchange network error: {exc}")
            return {"error": str(exc)}
