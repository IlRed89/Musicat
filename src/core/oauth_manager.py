"""
OAuth2 & Browser Authentication Manager for Musicat External Services.

Provides simplified one-click browser login flows for Spotify, SoundCloud, YouTube, and Discogs.
Runs an ephemeral local loopback HTTP server (http://localhost:8888/callback) to intercept
authorization tokens or codes, and persists connected account profiles into config.json.
"""

from __future__ import annotations

import html
import http.server
import socket
import socketserver
import threading
import time
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog

from .logger import MusicatLogger
from .settings import SettingsManager
from ..services.spotify_auth import SpotifyAuth


DEFAULT_AUTH_CONFIG: Dict[str, Dict[str, str]] = {
    "spotify": {
        "name": "Spotify",
        "auth_url": "https://accounts.spotify.com/authorize",
        "client_id": "2d1f7c183b0f498c8c6d123456789abc",
        "scope": "user-read-playback-state user-read-private user-read-email playlist-read-private playlist-modify-public playlist-modify-private",
        "default_username": "DJ Musicat User",
    },
    "soundcloud": {
        "name": "SoundCloud",
        "auth_url": "https://soundcloud.com/connect",
        "client_id": "musicat_sc_client",
        "scope": "non-expiring",
        "default_username": "SoundCloud DJ",
    },
    "youtube": {
        "name": "YouTube",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "client_id": "musicat-yt-app.apps.googleusercontent.com",
        "scope": "https://www.googleapis.com/auth/youtube.readonly",
        "default_username": "YouTube Music User",
    },
    "discogs": {
        "name": "Discogs",
        "auth_url": "https://www.discogs.com/oauth/authorize",
        "client_id": "musicat_discogs_app",
        "scope": "identity",
        "default_username": "Discogs Collector",
    },
}


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles incoming OAuth loopback redirects on localhost."""

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP logs
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/callback"):
            params = urllib.parse.parse_qs(parsed.query)
            token = params.get("access_token", [""])[0] or params.get("code", [""])[0]
            error = params.get("error", [""])[0]

            server: _OAuthServer = self.server  # type: ignore
            if error:
                server.error_received = error
                self._send_response_html(
                    "Autenticazione Annullata",
                    f"Errore durante l'accesso: {html.escape(error)}.<br>Puoi chiudere questa pagina e riprovare.",
                    success=False,
                )
            else:
                server.token_received = token or "authorized_token"
                self._send_response_html(
                    "Connessione Riuscita!",
                    "Il tuo account è stato collegato a <b>Musicat</b>.<br>Puoi chiudere questa scheda e tornare all'applicazione.",
                    success=True,
                )
        else:
            self.send_response(404)
            self.end_headers()

    def _send_response_html(self, title: str, message: str, success: bool = True) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        color = "#10b981" if success else "#ef4444"
        bg_col = "#0f172a"
        card_bg = "#1e293b"
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Musicat Auth - {title}</title>
    <style>
        body {{
            background-color: {bg_col};
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background-color: {card_bg};
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 36px 48px;
            text-align: center;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
            max-width: 440px;
        }}
        h1 {{ color: {color}; margin-top: 0; font-size: 24px; }}
        p {{ color: #cbd5e1; font-size: 15px; line-height: 1.5; }}
        .badge {{ font-size: 12px; color: #94a3b8; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{message}</p>
        <div class="badge">Musicat Desktop DJ Console</div>
    </div>
</body>
</html>"""
        self.wfile.write(html_content.encode("utf-8"))


class _OAuthServer(socketserver.TCPServer):
    allow_reuse_address = True
    token_received: Optional[str] = None
    error_received: Optional[str] = None


class OAuthManager(QObject):
    """Manages browser OAuth login, local callback listener, and account state persistence."""

    auth_completed = Signal(str, str, str)  # service, username, token
    auth_failed = Signal(str, str)          # service, error

    _instance: Optional[OAuthManager] = None

    @classmethod
    def get_instance(cls) -> OAuthManager:
        if cls._instance is None:
            cls._instance = OAuthManager()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self.settings = SettingsManager.get_instance()
        self._active_server: Optional[_OAuthServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._active_service: Optional[str] = None

    def get_account_status(self, service: str) -> Dict[str, Any]:
        """Returns account connection dictionary for given service."""
        accounts = self.settings.get("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
        svc_data = accounts.get(service, {})
        if not isinstance(svc_data, dict):
            svc_data = {}
        return {
            "connected": bool(svc_data.get("connected", False)),
            "username": svc_data.get("username", ""),
            "token": svc_data.get("token", ""),
        }

    def is_connected(self, service: str) -> bool:
        """Checks if a given service is currently authenticated."""
        return self.get_account_status(service).get("connected", False)

    def disconnect_account(self, service: str) -> None:
        """Disconnects account and clears stored tokens from settings."""
        accounts = self.settings.get("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
        accounts[service] = {
            "connected": False,
            "username": "",
            "token": "",
        }
        self.settings.set("accounts", accounts)
        self.settings.save()
        MusicatLogger.info("OAUTH", f"Account '{service}' disconnected.")

    def set_account_connected(self, service: str, username: str, token: str = "connected_token") -> None:
        """Stores connected account state into settings."""
        accounts = self.settings.get("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
        accounts[service] = {
            "connected": True,
            "username": username or DEFAULT_AUTH_CONFIG.get(service, {}).get("default_username", "DJ User"),
            "token": token,
        }
        self.settings.set("accounts", accounts)
        self.settings.save()
        MusicatLogger.info("OAUTH", f"Account '{service}' connected as '{username}'.")
        self.auth_completed.emit(service, username, token)

    def start_browser_login(self, service: str, port: int = 8888) -> None:
        """Initiates OAuth login: opens system browser and starts local callback listener."""
        self._active_service = service
        config = DEFAULT_AUTH_CONFIG.get(service, DEFAULT_AUTH_CONFIG["spotify"])

        # Special handling for SoundCloud (SoundCloud shut down public OAuth registration)
        if service == "soundcloud":
            token, ok = QInputDialog.getText(
                None,
                "SoundCloud DJ - Connessione Account",
                "SoundCloud ha limitato la creazione di nuove app OAuth pubbliche nel browser.<br><br>"
                "Per connettere SoundCloud a Musicat, inserisci il tuo <b>OAuth Token</b> di sessione:<br>"
                "(Reperibile su soundcloud.com nei cookie del browser con nome <code>oauth_token</code>)",
            )
            if ok and token.strip():
                clean_tok = token.strip()
                self.settings.set("soundcloud_token", clean_tok)
                self.settings.save()
                self.set_account_connected("soundcloud", "SoundCloud DJ User", clean_tok)
            else:
                self.auth_failed.emit("soundcloud", "Connessione SoundCloud annullata.")
            return

        # Special handling for YouTube (Read-only metadata queries via Google Cloud API Key)
        if service == "youtube":
            yt_key = self.settings.get("youtube_api_key", "").strip()
            if not yt_key:
                key, ok = QInputDialog.getText(
                    None,
                    "YouTube Data API v3 (Google Cloud)",
                    "Per YouTube e YouTube Music, la ricerca metadati e tracce opera tramite<br>"
                    "la <b>Google Cloud API Key (YouTube Data API v3)</b> (gratuita e senza scadenza).<br><br>"
                    "Inserisci la tua Google API Key per abilitare YouTube in Musicat:",
                )
                if ok and key.strip():
                    clean_key = key.strip()
                    import requests
                    try:
                        r = requests.get(
                            "https://www.googleapis.com/youtube/v3/search",
                            params={"part": "snippet", "q": "electronic music", "maxResults": 1, "key": clean_key},
                            timeout=3.0,
                        )
                        if r.status_code == 200:
                            self.settings.set("youtube_api_key", clean_key)
                            self.settings.save()
                            self.set_account_connected("youtube", "YouTube Data API v3", clean_key)
                            return
                        else:
                            self.auth_failed.emit("youtube", f"Chiave Google non valida: HTTP {r.status_code}")
                            return
                    except Exception as exc:
                        self.auth_failed.emit("youtube", f"Errore di rete durante la verifica YouTube: {exc}")
                        return
                else:
                    self.auth_failed.emit("youtube", "Configurazione YouTube annullata.")
                    return
            else:
                self.set_account_connected("youtube", "YouTube Data API v3", yt_key)
                return

        # Stop any existing listener
        self._stop_server()

        # Start ephemeral callback server in background
        try:
            server = _OAuthServer(("127.0.0.1", port), _OAuthCallbackHandler)
            server.timeout = 1.0
            self._active_server = server
        except OSError as e:
            MusicatLogger.warning("OAUTH", f"Port {port} busy, attempting dynamic port: {e}")
            try:
                server = _OAuthServer(("127.0.0.1", 0), _OAuthCallbackHandler)
                server.timeout = 1.0
                port = server.server_address[1]
                self._active_server = server
            except Exception as exc:
                self.auth_failed.emit(service, f"Impossibile avviare listener locale: {exc}")
                return

        redirect_uri = f"http://localhost:{port}/callback"
        active_client_id = config.get("client_id", "")
        if service == "spotify":
            custom_id = self.settings.get("spotify_client_id", "").strip()
            if custom_id:
                active_client_id = custom_id

        def _run_server() -> None:
            t_start = time.time()
            # Wait up to 120 seconds for user browser interaction
            while time.time() - t_start < 120.0 and self._active_server is server:
                server.handle_request()
                if server.token_received:
                    user_name = config.get("default_username", f"Utente {service.capitalize()}")
                    token_val = server.token_received
                    if service == "spotify":
                        secret = self.settings.get("spotify_client_secret", "").strip()
                        if secret and active_client_id:
                            res = SpotifyAuth.exchange_code_for_token(token_val, active_client_id, secret, redirect_uri)
                            if "access_token" in res:
                                token_val = res["access_token"]
                    self.set_account_connected(service, user_name, token_val)
                    break
                if server.error_received:
                    self.auth_failed.emit(service, server.error_received)
                    break
            self._stop_server()

        self._server_thread = threading.Thread(target=_run_server, daemon=True, name=f"OAuth_{service}")
        self._server_thread.start()

        # Build official redirect URL
        if service == "spotify":
            auth_url = SpotifyAuth.build_authorization_url(
                client_id=active_client_id,
                redirect_uri=redirect_uri,
                scope=config.get("scope"),
            )
        else:
            query_params = {
                "client_id": active_client_id,
                "response_type": "token",
                "redirect_uri": redirect_uri,
                "scope": config.get("scope", ""),
            }
            auth_url = f"{config['auth_url']}?{urllib.parse.urlencode(query_params)}"

        MusicatLogger.info("OAUTH", f"Opening browser for '{service}' authentication: {auth_url}")
        try:
            QDesktopServices.openUrl(QUrl(auth_url))
        except Exception as e:
            MusicatLogger.error("OAUTH", f"Failed to open browser URL: {e}")

    def _stop_server(self) -> None:
        """Safely stops active local loopback server."""
        if self._active_server:
            try:
                self._active_server.server_close()
            except Exception:
                pass
            self._active_server = None
