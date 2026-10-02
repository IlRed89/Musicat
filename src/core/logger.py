"""
Structured Logging & Troubleshooting Subsystem for Musicat.

Features:
- Automatic size-based rotation (max 20MB) with automatic ZIP compression of rotated logs (up to 10 backups).
- Adaptive log directory location:
  - Portable mode (portable.lock): adjacent './logs' directory.
  - Standard mode: '%APPDATA%/Musicat/logs' (Windows) or '~/Library/Application Support/Musicat/logs' (macOS).
- Multi-level logging: DEBUG, INFO, WARNING, ERROR, CRITICAL.
- Granular domain-specific tracking for deep troubleshooting:
  - Filesystem indexing & scans (permissions, unreadable paths, total items).
  - Audio Engine (libVLC codec init, playback failures, buffer underruns, DSP).
  - Tag Editor (Mutagen pre/post dumps, overwritten fields, corrupt ID3 headers).
  - Scrapers & APIs (endpoint URLs, search params, HTTP codes, latency ms, JSON failures).
  - Physical file dispatch (SRC -> DEST, collisions and resolutions).
- Thread-safe GUI Log Handler for real-time log terminal widgets.
- Diagnostic Support Bundle generator (.zip archive containing logs, hardware, and sanitized configuration).
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import sys
import threading
import time
import zipfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .path_resolver import PathResolver


class ZipRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler that compresses archived log files into ZIP format.

    When the active log file reaches maxBytes, it closes the stream, rotates existing
    ZIP archives (e.g. musicat.log.1.zip -> musicat.log.2.zip up to backupCount),
    compresses the current log file into musicat.log.1.zip with ZIP_DEFLATED,
    removes the uncompressed raw log file, and creates a fresh active log file.

    Example:
        >>> handler = ZipRotatingFileHandler("logs/musicat.log", maxBytes=20*1024*1024, backupCount=10)
    """

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 20 * 1024 * 1024,
        backupCount: int = 10,
        encoding: Optional[str] = "utf-8",
        delay: bool = False,
    ) -> None:
        """Initializes the ZIP rotating file handler.

        Args:
            filename (str): Path to target active log file.
            mode (str): File open mode (defaults to 'a').
            maxBytes (int): Maximum size in bytes before rotation triggers (defaults to 20MB).
            backupCount (int): Number of compressed ZIP backup files to retain (defaults to 10).
            encoding (Optional[str]): File encoding (defaults to 'utf-8').
            delay (bool): If True, file opening is deferred until first emit.
        """
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
        )

    def doRollover(self) -> None:
        """Performs atomic log rollover with ZIP archive compression."""
        if self.stream:
            self.stream.close()
            self.stream = None

        if self.backupCount > 0:
            # 1. Shift older zip files: e.g. musicat.log.9.zip -> musicat.log.10.zip
            for i in range(self.backupCount - 1, 0, -1):
                sfn = f"{self.baseFilename}.{i}.zip"
                dfn = f"{self.baseFilename}.{i + 1}.zip"
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        try:
                            os.remove(dfn)
                        except OSError:
                            pass
                    try:
                        os.rename(sfn, dfn)
                    except OSError:
                        pass

            # 2. Compress the freshly rotated log file into .1.zip
            target_zip = f"{self.baseFilename}.1.zip"
            if os.path.exists(target_zip):
                try:
                    os.remove(target_zip)
                except OSError:
                    pass

            if os.path.exists(self.baseFilename):
                try:
                    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                        zf.write(self.baseFilename, arcname=os.path.basename(self.baseFilename))
                    os.remove(self.baseFilename)
                except Exception:
                    # Fallback: rename without compression if zip compression fails
                    fallback_name = f"{self.baseFilename}.1"
                    if os.path.exists(self.baseFilename):
                        try:
                            if os.path.exists(fallback_name):
                                os.remove(fallback_name)
                            os.rename(self.baseFilename, fallback_name)
                        except OSError:
                            pass

        if not self.delay:
            self.stream = self._open()


# Backward compatibility alias
CompressedRotatingFileHandler = ZipRotatingFileHandler


class GuiLogHandler(logging.Handler):
    """Thread-safe logging handler that dispatches formatted records to GUI listeners.

    Example:
        >>> handler = GuiLogHandler(callback=lambda t, lvl, msg: print(f"[{t}] {msg}"))
    """

    def __init__(self, callback: Optional[Callable[[str, int, str], None]] = None) -> None:
        """Initializes the GUI logging handler.

        Args:
            callback (Optional[Callable[[str, int, str], None]]): Callback function receiving
                (timestamp_str, levelno, message_str).
        """
        super().__init__()
        self._callback: Optional[Callable[[str, int, str], None]] = callback
        self._lock = threading.Lock()

    def set_callback(self, callback: Callable[[str, int, str], None]) -> None:
        """Registers or updates the active GUI subscriber callback.

        Args:
            callback (Callable[[str, int, str], None]): Receiver function.
        """
        with self._lock:
            self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        """Dispatches formatted log record to the active callback if registered.

        Args:
            record (logging.LogRecord): The record to dispatch.
        """
        with self._lock:
            if not self._callback:
                return

        try:
            msg = self.format(record)
            time_str = time.strftime("%H:%M:%S", time.localtime(record.created))
            with self._lock:
                if self._callback:
                    self._callback(time_str, record.levelno, msg)
        except Exception:
            self.handleError(record)


class MusicatLogger:
    """Central logging controller for Musicat with advanced troubleshooting capabilities."""

    _logger: Optional[logging.Logger] = None
    _gui_handler: Optional[GuiLogHandler] = None
    _file_handlers: List[logging.Handler] = []
    _lock = threading.Lock()

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Returns the singleton application logger, initializing handlers if needed.

        Returns:
            logging.Logger: Configured Musicat root logger instance.

        Example:
            >>> logger = MusicatLogger.get_logger()
            >>> logger.info("Application started")
        """
        with cls._lock:
            if cls._logger is not None:
                return cls._logger

            logger = logging.getLogger("Musicat")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False

            # Clear existing handlers
            logger.handlers.clear()
            cls._file_handlers.clear()

            # Formatters
            detailed_fmt = logging.Formatter(
                "[%(asctime)s] [%(levelname)-7s] [%(name)s:%(threadName)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_fmt = logging.Formatter("[%(levelname)-7s] %(message)s")

            # 1. Console Stream Handler (guarded for frozen GUI apps where sys.stdout is None)
            if sys.stdout is not None and hasattr(sys.stdout, "write"):
                try:
                    console_h = logging.StreamHandler(sys.stdout)
                    console_h.setLevel(logging.INFO)
                    console_h.setFormatter(console_fmt)
                    logger.addHandler(console_h)
                except Exception:
                    pass

            # 2. Adaptive Logs Directory (Max 20MB, 10 backup ZIP archives)
            logs_dir = PathResolver.get_logs_dir()
            try:
                logs_dir.mkdir(parents=True, exist_ok=True)
                log_file = logs_dir / "musicat.log"
                file_h = ZipRotatingFileHandler(
                    filename=str(log_file),
                    maxBytes=20 * 1024 * 1024,  # 20 Megabytes per file
                    backupCount=10,             # Keep 10 compressed .zip backups
                    encoding="utf-8",
                )
                file_h.setLevel(logging.DEBUG)
                file_h.setFormatter(detailed_fmt)
                logger.addHandler(file_h)
                cls._file_handlers.append(file_h)
            except Exception:
                pass

            # In portable mode, if root app_dir/logs differs from data_dir/logs, attach mirror
            if PathResolver.is_portable_mode():
                alt_logs = PathResolver.get_app_dir() / "logs"
                try:
                    if alt_logs.resolve() != logs_dir.resolve():
                        alt_logs.mkdir(parents=True, exist_ok=True)
                        alt_file = alt_logs / "musicat.log"
                        alt_h = ZipRotatingFileHandler(
                            filename=str(alt_file),
                            maxBytes=20 * 1024 * 1024,
                            backupCount=10,
                            encoding="utf-8",
                        )
                        alt_h.setLevel(logging.DEBUG)
                        alt_h.setFormatter(detailed_fmt)
                        logger.addHandler(alt_h)
                        cls._file_handlers.append(alt_h)
                except Exception:
                    pass

            # 3. GUI Handler
            cls._gui_handler = GuiLogHandler()
            cls._gui_handler.setLevel(logging.DEBUG)
            cls._gui_handler.setFormatter(console_fmt)
            logger.addHandler(cls._gui_handler)

            cls._logger = logger
            return cls._logger

    @classmethod
    def register_gui_callback(cls, callback: Callable[[str, int, str], None]) -> None:
        """Connects a GUI widget or window to receive live log events.

        Args:
            callback (Callable[[str, int, str], None]): Receiver function receiving
                (time_str, levelno, message).
        """
        cls.get_logger()
        if cls._gui_handler:
            cls._gui_handler.set_callback(callback)

    # ================= GRANULAR DOMAIN EVENT LOGGERS =================

    @classmethod
    def log_scan(
        cls,
        folder: str,
        files_found: int,
        inserted: int,
        errors: int = 0,
        elapsed_ms: float = 0.0,
        skipped_files: Optional[List[str]] = None,
    ) -> None:
        """Logs directory indexing scan statistics and file discovery metrics.

        Args:
            folder (str): Directory scanned.
            files_found (int): Total supported audio files identified.
            inserted (int): Total records inserted/updated in SQLite.
            errors (int): Count of unreadable or corrupt files encountered.
            elapsed_ms (float): Total elapsed execution duration in milliseconds.
            skipped_files (Optional[List[str]]): List of rejected or inaccessible paths.
        """
        msg = (
            f"[SCAN] Indexed '{folder}' -> Found: {files_found}, Inserted: {inserted}, "
            f"Errors: {errors} in {elapsed_ms:.1f}ms"
        )
        if errors > 0:
            cls.get_logger().warning(msg)
        else:
            cls.get_logger().info(msg)

        if skipped_files:
            for s in skipped_files[:15]:
                cls.get_logger().debug(f"[SCAN:SKIPPED] {s}")
            if len(skipped_files) > 15:
                cls.get_logger().debug(f"[SCAN:SKIPPED] ... and {len(skipped_files) - 15} more.")

    @classmethod
    def log_audio_engine(
        cls,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        level: str = "info",
    ) -> None:
        """Logs audio playback, codec lifecycle, buffer status, and player engine events.

        Args:
            event_type (str): Category (e.g. 'CODEC_INIT', 'PLAY', 'BUFFER_UNDERRUN', 'CRASH', 'DEVICE_SWITCH').
            message (str): Human-readable event description.
            details (Optional[Dict[str, Any]]): Optional telemetry metrics or error dict.
            level (str): Log severity ('debug', 'info', 'warning', 'error', 'critical').
        """
        detail_str = f" | Details: {json.dumps(details)}" if details else ""
        full_msg = f"[AUDIO:{event_type.upper()}] {message}{detail_str}"
        lvl_func = getattr(cls.get_logger(), level.lower(), cls.get_logger().info)
        lvl_func(full_msg)

    @classmethod
    def log_acoustic(
        cls,
        filepath: str,
        bpm: Optional[float],
        key: str,
        camelot: str,
        elapsed_ms: float,
        energy: Optional[int] = None,
    ) -> None:
        """Logs acoustic analysis results for a track.

        Args:
            filepath (str): Audio file path.
            bpm (Optional[float]): Detected tempo.
            key (str): Detected musical key.
            camelot (str): Canonical Camelot code.
            elapsed_ms (float): DSP processing time in ms.
            energy (Optional[int]): Detected energy level (1-10).
        """
        fname = Path(filepath).name
        bpm_str = f"{bpm:.1f} BPM" if bpm else "N/A"
        energy_str = f", Energy: {energy}/10" if energy is not None else ""
        cls.get_logger().debug(
            f"[ACOUSTIC] '{fname}' -> Tempo: {bpm_str}, Key: {key} ({camelot}){energy_str} in {elapsed_ms:.1f}ms"
        )

    @classmethod
    def log_tag_edit(
        cls,
        filepath: str,
        fields_modified: List[str],
        pre_dump: Optional[Dict[str, Any]] = None,
        post_dump: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: str = "",
    ) -> None:
        """Logs metadata tag modifications with pre/post diff inspection.

        Args:
            filepath (str): Filepath of audio file modified.
            fields_modified (List[str]): Field keys updated (e.g. ['title', 'artist', 'bpm']).
            pre_dump (Optional[Dict[str, Any]]): Original metadata values.
            post_dump (Optional[Dict[str, Any]]): Updated metadata values.
            success (bool): Whether write operation succeeded.
            error (str): Error message if write failed.
        """
        fname = Path(filepath).name
        if success:
            cls.get_logger().info(f"[TAG] Saved [{', '.join(fields_modified)}] -> '{fname}'")
            if pre_dump and post_dump:
                diffs = {}
                for k in fields_modified:
                    diffs[k] = {"before": pre_dump.get(k), "after": post_dump.get(k)}
                cls.get_logger().debug(f"[TAG:DIFF] '{fname}' -> {json.dumps(diffs)}")
        else:
            cls.get_logger().error(f"[TAG:FAIL] Could not update '{fname}': {error}")

    @classmethod
    def log_http(
        cls,
        source: str,
        url: str,
        status_code: int,
        latency_ms: float,
        params: Optional[Dict[str, Any]] = None,
        results_count: int = 0,
        error: str = "",
    ) -> None:
        """Logs HTTP metadata scraper requests, search queries, and response performance.

        Args:
            source (str): Remote service name (e.g. 'Spotify', 'Beatport', 'Cosine', 'Discogs').
            url (str): Remote request URL.
            status_code (int): HTTP response status code (e.g. 200, 404, 429).
            latency_ms (float): Round-trip duration in milliseconds.
            params (Optional[Dict[str, Any]]): Query search parameters.
            results_count (int): Count of results returned.
            error (str): Error description if request failed or timed out.
        """
        level = logging.INFO if 200 <= status_code < 300 else logging.WARNING
        param_str = f" [Params: {json.dumps(params)}]" if params else ""
        err_str = f" [Error: {error}]" if error else ""
        cls.get_logger().log(
            level,
            f"[HTTP:{source}] {status_code} ({latency_ms:.1f}ms) -> {url}{param_str} [Results: {results_count}]{err_str}",
        )

    @classmethod
    def log_file_op(
        cls,
        action: str,
        source: str,
        target: str,
        collision_resolved: str = "",
        success: bool = True,
        details: str = "",
    ) -> None:
        """Logs physical file dispatch operations (Move/Copy/Rename).

        Args:
            action (str): Operation type ('MOVE', 'COPY', 'RENAME', 'DELETE').
            source (str): Source path.
            target (str): Target destination path.
            collision_resolved (str): Strategy applied on conflict ('RENAME', 'OVERWRITE', 'SKIP').
            success (bool): Whether operation succeeded.
            details (str): Additional context or error details.
        """
        col_str = f" [Collision: {collision_resolved}]" if collision_resolved else ""
        if success:
            cls.get_logger().info(f"[DISPATCH:{action.upper()}] '{Path(source).name}' -> '{target}'{col_str}")
        else:
            cls.get_logger().error(f"[DISPATCH:FAIL] '{Path(source).name}' -> '{target}'{col_str}: {details}")

    # ================= STANDARD DOMAIN LOGGERS =================

    @classmethod
    def debug(cls, domain: str, message: str) -> None:
        """Logs a debug message with domain prefix."""
        cls.get_logger().debug(f"[{domain}] {message}")

    @classmethod
    def info(cls, domain: str, message: str) -> None:
        """Logs an info message with domain prefix."""
        cls.get_logger().info(f"[{domain}] {message}")

    @classmethod
    def warning(cls, domain: str, message: str) -> None:
        """Logs a warning message with domain prefix."""
        cls.get_logger().warning(f"[{domain}] {message}")

    @classmethod
    def error(cls, domain: str, message: str) -> None:
        """Logs an error message with domain prefix."""
        cls.get_logger().error(f"[{domain}] {message}")

    @classmethod
    def critical(cls, domain: str, message: str) -> None:
        """Logs a critical error message with domain prefix and flushes handlers."""
        cls.get_logger().critical(f"[{domain}] {message}")
        cls.flush()

    @classmethod
    def exception(cls, domain: str, message: str) -> None:
        """Logs an exception traceback with domain prefix."""
        cls.get_logger().exception(f"[{domain}] {message}")
        cls.flush()

    @classmethod
    def flush(cls) -> None:
        """Flushes all attached log handlers to disk immediately."""
        with cls._lock:
            if cls._logger:
                for h in cls._logger.handlers:
                    try:
                        h.flush()
                    except Exception:
                        pass

    # ================= SUPPORT DIAGNOSTICS BUNDLE EXPORTER =================

    @classmethod
    def export_support_bundle(
        cls,
        destination_zip: Optional[Union[str, Path]] = None,
        db: Optional[Any] = None,
    ) -> str:
        """Generates a complete ZIP diagnostic bundle for assistance and troubleshooting.

        The archive includes:
        - Current and rotated compressed log files from all active log folders.
        - Detailed system telemetry (OS, architecture, CPU, Python, Qt, libVLC).
        - Database overview metrics (total tracks, crates count, database file size).
        - Sanitized settings dump (all passwords, client secrets, and API tokens are masked).

        Args:
            destination_zip (Optional[Union[str, Path]]): Destination path. If None,
                saved to the user's Desktop or home directory.
            db (Optional[Any]): Optional Database instance to collect track statistics.

        Returns:
            str: Absolute file path to the generated support ZIP bundle.

        Raises:
            IOError: If writing to the destination path fails.

        Example:
            >>> bundle_path = MusicatLogger.export_support_bundle()
            >>> print(f"Support bundle created at: {bundle_path}")
        """
        cls.flush()

        # 1. Determine destination path
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        if destination_zip:
            out_path = Path(destination_zip).resolve()
        else:
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home()
            out_path = desktop / f"musicat_support_bundle_{now_str}.zip"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 2. Gather diagnostic data
        from .settings import SettingsManager
        settings_mgr = SettingsManager.get_instance()
        safe_settings = settings_mgr.get_all()

        # Sanitize sensitive scraper keys and passwords
        if "scrapers" in safe_settings and isinstance(safe_settings["scrapers"], dict):
            for k in safe_settings["scrapers"]:
                if safe_settings["scrapers"][k]:
                    safe_settings["scrapers"][k] = "******** [REDACTED]"

        # Collect database metrics
        db_stats: Dict[str, Any] = {"available": False}
        if db is not None:
            try:
                db_stats["available"] = True
                db_stats["db_path"] = str(getattr(db, "db_path", ""))
                if Path(db_stats["db_path"]).exists():
                    db_stats["size_bytes"] = Path(db_stats["db_path"]).stat().st_size
                tracks = db.search_tracks(limit=10)
                db_stats["tracks_count"] = len(db.search_tracks(limit=100000))
                db_stats["crates_count"] = len(db.get_crates())
            except Exception as e:
                db_stats["error"] = str(e)

        # Collect system environment metrics
        sys_info: Dict[str, Any] = {
            "app_name": "Musicat",
            "timestamp": datetime.now().isoformat(),
            "os_platform": platform.platform(),
            "os_system": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.architecture(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "is_portable_mode": PathResolver.is_portable_mode(),
            "app_directory": str(PathResolver.get_app_dir()),
            "data_directory": str(PathResolver.get_data_dir()),
            "logs_directory": str(PathResolver.get_logs_dir()),
            "database_diagnostics": db_stats,
            "sanitized_configuration": safe_settings,
        }

        # Check libVLC status
        try:
            from ..player.vlc_engine import _VLC_AVAILABLE, VLCAudioPlayer
            sys_info["libvlc_available"] = _VLC_AVAILABLE
        except Exception:
            sys_info["libvlc_available"] = False

        # 3. Write ZIP archive
        with zipfile.ZipFile(str(out_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Write diagnostics JSON
            diag_json = json.dumps(sys_info, indent=2, ensure_ascii=False)
            zf.writestr("diagnostics/system_info.json", diag_json)

            # Include log files from PathResolver.get_logs_dir()
            logs_dir = PathResolver.get_logs_dir()
            if logs_dir.exists():
                for p in logs_dir.glob("*"):
                    if p.is_file() and (p.suffix in (".log", ".zip", ".gz")):
                        try:
                            zf.write(p, arcname=f"logs/{p.name}")
                        except Exception:
                            pass

            # If portable mode, check root app logs too
            if PathResolver.is_portable_mode():
                alt_logs = PathResolver.get_app_dir() / "logs"
                if alt_logs.exists() and alt_logs.resolve() != logs_dir.resolve():
                    for p in alt_logs.glob("*"):
                        if p.is_file() and (p.suffix in (".log", ".zip", ".gz")):
                            try:
                                zf.write(p, arcname=f"logs_root/{p.name}")
                            except Exception:
                                pass

        cls.get_logger().info(f"[SUPPORT] Created diagnostic bundle: '{out_path}'")
        return str(out_path)
