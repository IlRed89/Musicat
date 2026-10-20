"""
Musicat GitHub Auto-Update Checker & In-App Downloader.

Asynchronously queries GitHub Releases REST API for latest version, compares with
local __version__, detects OS-compatible assets (Installer vs Portable vs DMG),
and handles stream downloading with live progress telemetry.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from PySide6.QtCore import QObject, QThread, Signal

from src import __version__
from src.core.logger import MusicatLogger
from src.core.path_resolver import PathResolver

# Version comparison utility
try:
    from packaging.version import parse as _parse_version
except ImportError:
    def _parse_version(v_str: str) -> Any:
        # Fallback numeric tuple parser
        nums = re.findall(r"\d+", str(v_str))
        return tuple(int(x) for x in nums) if nums else (0,)


def parse_clean_version(version_str: str) -> Any:
    """Strips leading 'v' or 'V' and parses into a comparable version object."""
    cleaned = str(version_str).strip().lstrip("vV").strip()
    return _parse_version(cleaned)


def is_version_newer(remote_version: str, local_version: str = __version__) -> bool:
    """Returns True if remote_version is strictly newer than local_version."""
    try:
        remote_parsed = parse_clean_version(remote_version)
        local_parsed = parse_clean_version(local_version)
        return remote_parsed > local_parsed
    except Exception as exc:
        MusicatLogger.warning("UPDATER", f"Error comparing versions '{remote_version}' vs '{local_version}': {exc}")
        return False


def find_compatible_asset(
    assets: List[Dict[str, Any]],
    os_platform: str = sys.platform,
    is_portable: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Selects the best matching release asset for the current operating system and runtime mode.

    Args:
        assets: List of asset dicts returned from GitHub releases API.
        os_platform: sys.platform string ('win32', 'darwin', 'linux').
        is_portable: Whether the current instance is running in portable mode.

    Returns:
        The matched asset dictionary or None.
    """
    if not assets:
        return None

    if is_portable is None:
        try:
            is_portable = PathResolver.is_portable_mode()
        except Exception:
            is_portable = False

    if os_platform == "win32":
        if is_portable:
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".zip") and "portable" in name:
                    return a
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".zip") and "win" in name:
                    return a
        else:
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".exe") and ("setup" in name or "installer" in name):
                    return a
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".exe"):
                    return a

        # Windows fallbacks
        for a in assets:
            name = a.get("name", "").lower()
            if (name.endswith(".zip") or name.endswith(".exe")) and "mac" not in name and "linux" not in name and "sha256" not in name:
                return a

    elif os_platform == "darwin":
        if is_portable:
            for a in assets:
                name = a.get("name", "").lower()
                if name.endswith(".zip") and ("mac" in name or "darwin" in name):
                    return a
        # Prefer DMG
        for a in assets:
            name = a.get("name", "").lower()
            if name.endswith(".dmg"):
                return a
        for a in assets:
            name = a.get("name", "").lower()
            if name.endswith(".zip") and ("mac" in name or "darwin" in name):
                return a

    else:
        # Linux / other
        for a in assets:
            name = a.get("name", "").lower()
            if any(name.endswith(ext) for ext in [".tar.gz", ".appimage", ".deb", ".rpm"]):
                return a

    # General fallback: non-metadata asset
    for a in assets:
        name = a.get("name", "").lower()
        if not name.endswith(".txt") and not name.endswith(".json") and "sha256" not in name:
            return a

    return assets[0]


@dataclass
class UpdateInfo:
    """Encapsulates metadata regarding an available application update."""

    remote_version: str
    local_version: str
    tag_name: str
    release_name: str
    release_notes: str
    html_url: str
    download_url: str
    asset_name: str
    asset_size: int
    published_at: str
    all_assets: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def asset_size_mb(self) -> float:
        return self.asset_size / (1024 * 1024) if self.asset_size else 0.0


class UpdateCheckerWorker(QThread):
    """Asynchronous worker that checks GitHub Releases for new updates."""

    update_available = Signal(object)      # UpdateInfo
    update_not_available = Signal(str)    # local_version
    check_failed = Signal(str)            # error message

    DEFAULT_REPO = "IlRed89/Musicat"

    def __init__(
        self,
        current_version: str = __version__,
        is_manual: bool = False,
        repo_slug: str = DEFAULT_REPO,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.is_manual = is_manual
        self.repo_slug = repo_slug

    def run(self) -> None:
        url = f"https://api.github.com/repos/{self.repo_slug}/releases/latest"
        headers = {
            "User-Agent": "Musicat-App",
            "Accept": "application/vnd.github.v3+json",
        }
        try:
            MusicatLogger.info("UPDATER", f"Checking GitHub for updates at: {url} (current: v{self.current_version})")
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 404:
                msg = "Nessuna release trovata nel repository GitHub."
                MusicatLogger.info("UPDATER", msg)
                self.update_not_available.emit(self.current_version)
                return

            if resp.status_code == 403:
                # Rate limit (60 requests/hr for unauthenticated users)
                msg = "Limite di richieste alle API di GitHub superato (60 req/ora). Riprova più tardi."
                MusicatLogger.warning("UPDATER", msg)
                self.check_failed.emit(msg)
                return

            resp.raise_for_status()
            data = resp.json()

            raw_tag = data.get("tag_name", "")
            remote_ver = raw_tag.lstrip("vV").strip()

            if not remote_ver:
                msg = "Dati di versione non validi restituiti da GitHub."
                MusicatLogger.warning("UPDATER", msg)
                self.check_failed.emit(msg)
                return

            if is_version_newer(remote_ver, self.current_version):
                assets = data.get("assets", [])
                compatible_asset = find_compatible_asset(assets)

                asset_name = compatible_asset.get("name", "Musicat-Update.zip") if compatible_asset else "Musicat-Update.zip"
                download_url = compatible_asset.get("browser_download_url", "") if compatible_asset else ""
                asset_size = compatible_asset.get("size", 0) if compatible_asset else 0

                info = UpdateInfo(
                    remote_version=remote_ver,
                    local_version=self.current_version,
                    tag_name=raw_tag,
                    release_name=data.get("name", f"Musicat v{remote_ver}"),
                    release_notes=data.get("body", "Nessuna nota di rilascio disponibile."),
                    html_url=data.get("html_url", f"https://github.com/{self.repo_slug}/releases"),
                    download_url=download_url,
                    asset_name=asset_name,
                    asset_size=asset_size,
                    published_at=data.get("published_at", ""),
                    all_assets=assets,
                )
                MusicatLogger.info("UPDATER", f"Update available: v{remote_ver} (asset: {asset_name})")
                self.update_available.emit(info)
            else:
                MusicatLogger.info("UPDATER", f"Musicat is up to date (current: v{self.current_version}, remote: v{remote_ver})")
                self.update_not_available.emit(self.current_version)

        except requests.exceptions.RequestException as exc:
            msg = f"Errore di connessione a GitHub: {exc}"
            MusicatLogger.warning("UPDATER", msg)
            self.check_failed.emit(msg)
        except Exception as exc:
            msg = f"Errore imprevisto durante la verifica aggiornamenti: {exc}"
            MusicatLogger.error("UPDATER", msg, exc_info=True)
            self.check_failed.emit(msg)


class UpdateDownloadWorker(QThread):
    """Streams release asset download to user's local disk with progress reporting."""

    download_progress = Signal(int, int)   # bytes_downloaded, total_bytes
    download_finished = Signal(str)        # destination file path
    download_failed = Signal(str)          # error message

    def __init__(
        self,
        download_url: str,
        destination_path: Union[str, Path],
        expected_size: int = 0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.download_url = download_url
        self.destination_path = Path(destination_path)
        self.expected_size = expected_size

    def run(self) -> None:
        headers = {"User-Agent": "Musicat-App"}
        part_path = self.destination_path.with_suffix(self.destination_path.suffix + ".part")

        try:
            self.destination_path.parent.mkdir(parents=True, exist_ok=True)
            MusicatLogger.info("UPDATER", f"Downloading update from {self.download_url} to {self.destination_path}")

            with requests.get(self.download_url, headers=headers, stream=True, timeout=30) as resp:
                resp.raise_for_status()
                total_bytes = int(resp.headers.get("content-length", 0)) or self.expected_size
                downloaded_bytes = 0

                with open(part_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if self.isInterruptionRequested():
                            MusicatLogger.info("UPDATER", "Download interrupted by user request.")
                            if part_path.exists():
                                part_path.unlink(missing_ok=True)
                            self.download_failed.emit("Download annullato dall'utente.")
                            return
                        if chunk:
                            f.write(chunk)
                            downloaded_bytes += len(chunk)
                            self.download_progress.emit(downloaded_bytes, total_bytes)

            # Move part file to final destination
            if part_path.exists():
                if self.destination_path.exists():
                    self.destination_path.unlink(missing_ok=True)
                part_path.rename(self.destination_path)

            MusicatLogger.info("UPDATER", f"Download completed successfully: {self.destination_path} ({downloaded_bytes} bytes)")
            self.download_finished.emit(str(self.destination_path))

        except Exception as exc:
            if part_path.exists():
                try:
                    part_path.unlink(missing_ok=True)
                except Exception:
                    pass
            msg = f"Errore durante il download dell'aggiornamento: {exc}"
            MusicatLogger.error("UPDATER", msg, exc_info=True)
            self.download_failed.emit(msg)
