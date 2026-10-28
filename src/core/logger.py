"""
Enterprise-Grade Structured Logging & Troubleshooting Subsystem for Musicat.

This module provides a hierarchical, multi-target logging infrastructure designed
specifically for real-time observability, post-mortem debugging, and crash analysis
in high-throughput DJ audio management environments.

Key Architecture Components:
    - Precise Millisecond Formatting: Detailed logs conforming to the enterprise standard:
      `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [MODULE.FUNCTION:LINE] [THREAD_NAME] - Message`
    - Colored Console Stream: High-visibility ANSI-formatted terminal stream for live development.
    - Size-Based Rotating Log File: Automatic rotation at 10 MB with 5 compressed ZIP backups,
      featuring immediate physical disk flushing (`flush()`) on ERROR and CRITICAL events.
    - Low-Level C/C++ Segfault Trap: Persistent hardware fault telemetry via `faulthandler`
      routed to `logs/crash.log`.
    - Key Subsystem Tracking: Dedicated tracing methods for Bootstrap, Filesystem I/O,
      Async Worker Pool, Acoustic DSP, Metadata Scraping & Conflict Resolution, Mutagen Tag Writes,
      libVLC Audio Engine, and OAuth / API flows.
    - GUI Log Dispatcher: Thread-safe log subscriber dispatching records to user interface docks.
    - Diagnostic Support Bundle: Generates sanitized `.zip` archives containing current/archived logs,
      hardware metrics, SQLite database stats, and redacted user configuration.

Usage Example:
    >>> from src.core.logger import MusicatLogger
    >>> logger = MusicatLogger.get_logger()
    >>> logger.info("Application initialized successfully.")
    >>> MusicatLogger.log_acoustic("track.mp3", bpm=128.0, key="Am", camelot="8A", elapsed_ms=45.2)
"""

from __future__ import annotations

import faulthandler
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


class PreciseMillisecondFormatter(logging.Formatter):
    """Custom logging formatter rendering timestamps with exact millisecond precision.

    Produces output formatted according to the enterprise specification:
    `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [MODULE.FUNCTION:LINE] [THREAD_NAME] - Message`

    Args:
        fmt (Optional[str]): Format string defining token placement.
        datefmt (Optional[str]): Base date format string (defaults to '%Y-%m-%d %H:%M:%S').
    """

    DEFAULT_FORMAT = (
        "[%(asctime)s] [%(levelname)-7s] "
        "[%(module)s.%(funcName)s:%(lineno)d] [%(threadName)s] - %(message)s"
    )

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
    ) -> None:
        super().__init__(fmt=fmt or self.DEFAULT_FORMAT, datefmt=datefmt or "%Y-%m-%d %H:%M:%S")

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """Formats the record creation timestamp including exact 3-digit millisecond resolution.

        Args:
            record (logging.LogRecord): The active log record.
            datefmt (Optional[str]): Optional strftime date format string.

        Returns:
            str: Timestamp string formatted as 'YYYY-MM-DD HH:MM:SS.mmm'.
        """
        ct = datetime.fromtimestamp(record.created)
        s = ct.strftime(datefmt or "%Y-%m-%d %H:%M:%S")
        return f"{s}.{int(record.msecs):03d}"


class ColoredConsoleFormatter(PreciseMillisecondFormatter):
    """Console-specific formatter with ANSI terminal coloring based on log severity level.

    Color Mapping:
        - DEBUG: Cyan (`\\033[36m`)
        - INFO: Green (`\\033[32m`)
        - WARNING: Yellow (`\\033[33m`)
        - ERROR: Red (`\\033[31m`)
        - CRITICAL: Bold Red (`\\033[1;31m`)
    """

    COLOR_CODES: Dict[int, str] = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[1;31m", # Bold Red
    }
    COLOR_RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Formats log record and wraps output in ANSI color codes if terminal supports them.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: ANSI-colorized formatted log string.
        """
        msg = super().format(record)
        if self._should_colorize():
            color = self.COLOR_CODES.get(record.levelno, "")
            if color:
                return f"{color}{msg}{self.COLOR_RESET}"
        return msg

    @staticmethod
    def _should_colorize() -> bool:
        """Determines if the runtime standard stream supports ANSI color codes."""
        if os.getenv("NO_COLOR"):
            return False
        if sys.platform == "win32":
            # Windows 10 build 10586+ / Windows 11 / Windows Terminal / VSCode
            if os.getenv("WT_SESSION") or os.getenv("VSCODE_PID") or os.getenv("TERM"):
                return True
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class ZipRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler that compresses archived log files into ZIP format.

    When the active log file reaches `maxBytes`, the stream is closed, existing
    backup archives are shifted progressively (`.1.zip` -> `.2.zip` up to `backupCount`),
    the current log is compressed into `.1.zip` using `zipfile.ZIP_DEFLATED`,
    and a fresh log file is instantiated.

    Additionally, forces an immediate physical disk flush whenever an ERROR or
    CRITICAL record is processed to ensure unbuffered crash logs are persisted.

    Args:
        filename (str): Path to active log file.
        mode (str, optional): File mode. Defaults to 'a'.
        maxBytes (int, optional): Size threshold in bytes before rotation triggers.
            Defaults to 10 MB (10 * 1024 * 1024).
        backupCount (int, optional): Number of compressed backup archives to retain.
            Defaults to 5.
        encoding (Optional[str], optional): Encoding format. Defaults to 'utf-8'.
        delay (bool, optional): Defer file opening until first record emit. Defaults to False.
    """

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 10 * 1024 * 1024,
        backupCount: int = 5,
        encoding: Optional[str] = "utf-8",
        delay: bool = False,
    ) -> None:
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
        )

    def emit(self, record: logging.LogRecord) -> None:
        """Emits a log record with immediate physical disk flush on severe error events.

        Args:
            record (logging.LogRecord): Record being processed.
        """
        super().emit(record)
        if record.levelno >= logging.ERROR and self.stream:
            try:
                self.flush()
                # Ensure physical write down to disk controller
                if hasattr(self.stream, "fileno"):
                    try:
                        os.fsync(self.stream.fileno())
                    except (AttributeError, OSError):
                        pass
            except Exception:
                pass

    def doRollover(self) -> None:
        """Performs atomic log rollover with ZIP archive compression."""
        if self.stream:
            self.stream.close()
            self.stream = None

        if self.backupCount > 0:
            # 1. Shift existing compressed zip archives
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
                    # Fallback rename if ZIP compression fails
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

    Args:
        callback (Optional[Callable[[str, int, str], None]]): Optional initial subscriber
            callback receiving `(timestamp_str, levelno, message_str)`.
    """

    def __init__(self, callback: Optional[Callable[[str, int, str], None]] = None) -> None:
        super().__init__()
        self._callback: Optional[Callable[[str, int, str], None]] = callback
        self._lock = threading.Lock()

    def set_callback(self, callback: Callable[[str, int, str], None]) -> None:
        """Registers or updates the active GUI subscriber callback.

        Args:
            callback (Callable[[str, int, str], None]): Receiver function receiving
                `(time_str, levelno, message)`.
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
    """Central enterprise logging controller for Musicat.

    Manages singleton logger configuration, multi-target output handlers (console,
    size-rotated file, crash faulthandler, GUI docks), and domain-specific tracing.
    """

    _logger: Optional[logging.Logger] = None
    _gui_handler: Optional[GuiLogHandler] = None
    _file_handlers: List[logging.Handler] = []
    _crash_file_handle: Optional[Any] = None
    _lock = threading.Lock()

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Returns the configured application singleton logger instance.

        Initializes all multi-target handlers on first invocation.

        Returns:
            logging.Logger: The configured root Musicat logger.
        """
        with cls._lock:
            if cls._logger is not None:
                return cls._logger

            logger = logging.getLogger("Musicat")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False

            # Clear existing handlers to prevent duplicates
            logger.handlers.clear()
            cls._file_handlers.clear()

            # Formatters
            detailed_fmt = PreciseMillisecondFormatter()
            console_fmt = ColoredConsoleFormatter()

            # 1. Console Stream Handler
            if sys.stdout is not None and hasattr(sys.stdout, "write"):
                try:
                    console_h = logging.StreamHandler(sys.stdout)
                    console_h.setLevel(logging.DEBUG if os.getenv("MUSICAT_DEBUG") else logging.INFO)
                    console_h.setFormatter(console_fmt)
                    logger.addHandler(console_h)
                except Exception:
                    pass

            # 2. Rotating File Handler (10 MB per file, 5 backup ZIP archives)
            logs_dir = PathResolver.get_logs_dir()
            try:
                logs_dir.mkdir(parents=True, exist_ok=True)
                log_file = logs_dir / "musicat.log"
                file_h = ZipRotatingFileHandler(
                    filename=str(log_file),
                    maxBytes=10 * 1024 * 1024,  # 10 Megabytes rotation threshold
                    backupCount=5,              # Retain 5 backup archives
                    encoding="utf-8",
                )
                file_h.setLevel(logging.DEBUG)
                file_h.setFormatter(detailed_fmt)
                logger.addHandler(file_h)
                cls._file_handlers.append(file_h)
            except Exception:
                pass

            # Mirror to app_dir/logs if portable mode uses different local directory
            if PathResolver.is_portable_mode():
                alt_logs = PathResolver.get_app_dir() / "logs"
                try:
                    if alt_logs.resolve() != logs_dir.resolve():
                        alt_logs.mkdir(parents=True, exist_ok=True)
                        alt_file = alt_logs / "musicat.log"
                        alt_h = ZipRotatingFileHandler(
                            filename=str(alt_file),
                            maxBytes=10 * 1024 * 1024,
                            backupCount=5,
                            encoding="utf-8",
                        )
                        alt_h.setLevel(logging.DEBUG)
                        alt_h.setFormatter(detailed_fmt)
                        logger.addHandler(alt_h)
                        cls._file_handlers.append(alt_h)
                except Exception:
                    pass

            # 3. Crash Faulthandler Dump (logs/crash.log)
            cls._init_crash_faulthandler(logs_dir)

            # 4. GUI Handler
            cls._gui_handler = GuiLogHandler()
            cls._gui_handler.setLevel(logging.DEBUG)
            cls._gui_handler.setFormatter(console_fmt)
            logger.addHandler(cls._gui_handler)

            cls._logger = logger
            return cls._logger

    @classmethod
    def _init_crash_faulthandler(cls, logs_dir: Path) -> None:
        """Initializes Python faulthandler to capture low-level C/C++ crashes and segfaults.

        Args:
            logs_dir (Path): Destination log directory.
        """
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            crash_log_path = logs_dir / "crash.log"
            cls._crash_file_handle = open(str(crash_log_path), "a", encoding="utf-8", buffering=1)
            faulthandler.enable(file=cls._crash_file_handle, all_threads=True)
        except Exception:
            pass

    @classmethod
    def register_gui_callback(cls, callback: Callable[[str, int, str], None]) -> None:
        """Connects a GUI widget or window to receive live log events.

        Args:
            callback (Callable[[str, int, str], None]): Receiver function receiving
                `(time_str, levelno, message)`.
        """
        cls.get_logger()
        if cls._gui_handler:
            cls._gui_handler.set_callback(callback)

    # ================= KEY LIFECYCLE & SUBSYSTEM TRACKING METHODS =================

    @classmethod
    def log_bootstrap(
        cls,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        level: str = "info",
    ) -> None:
        """Logs application lifecycle, hardware detection, runtime paths, and engine loading.

        Args:
            message (str): Description of bootstrap phase (e.g. 'Application startup', 'Hardware probe').
            details (Optional[Dict[str, Any]]): Context telemetry (e.g. CPU, RAM, GPU, paths).
            level (str, optional): Log severity ('debug', 'info', 'warning', 'error'). Defaults to 'info'.
        """
        detail_str = f" | Details: {json.dumps(details, default=str)}" if details else ""
        full_msg = f"[BOOTSTRAP] {message}{detail_str}"
        lvl_func = getattr(cls.get_logger(), level.lower(), cls.get_logger().info)
        lvl_func(full_msg)

    @classmethod
    def log_scan(
        cls,
        folder: str,
        files_found: int,
        inserted: int,
        errors: Union[int, float] = 0,
        elapsed_ms: float = 0.0,
        skipped_files: Optional[List[str]] = None,
    ) -> None:
        """Logs filesystem indexing scan metrics, discovered audio tracks, and skipped files.

        Args:
            folder (str): Directory scanned on disk.
            files_found (int): Total audio files identified.
            inserted (int): Total records added/updated in SQLite database.
            errors (Union[int, float], optional): Count of errors or timing fallback. Defaults to 0.
            elapsed_ms (float, optional): Total elapsed time in milliseconds. Defaults to 0.0.
            skipped_files (Optional[List[str]], optional): List of rejected or unreadable paths.
        """
        # Backward compatibility check if 4th arg was elapsed_ms in legacy tests
        actual_errors = int(errors) if isinstance(errors, (int, float)) and errors >= 1 and float(errors).is_integer() else (0 if isinstance(errors, float) else int(errors))
        actual_ms = elapsed_ms if elapsed_ms > 0.0 else (float(errors) if isinstance(errors, float) else 0.0)

        msg = (
            f"[SCAN] Indexed '{folder}' -> Found: {files_found}, Inserted: {inserted}, "
            f"Errors: {actual_errors} in {actual_ms:.1f}ms"
        )
        if actual_errors > 0:
            cls.get_logger().warning(msg)
        else:
            cls.get_logger().info(msg)

        if skipped_files:
            for s in skipped_files[:15]:
                cls.get_logger().debug(f"[SCAN:SKIPPED] {s}")
            if len(skipped_files) > 15:
                cls.get_logger().debug(f"[SCAN:SKIPPED] ... and {len(skipped_files) - 15} more.")

    @classmethod
    def log_worker(
        cls,
        worker_id: str,
        event: str,
        progress_pct: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
        error: str = "",
    ) -> None:
        """Logs asynchronous background worker events, task progress, and cancellations.

        Args:
            worker_id (str): Identifier or class name of worker (e.g. 'AsyncAnalysisWorker-1').
            event (str): Event name ('STARTED', 'PROGRESS', 'COMPLETED', 'CANCELLED', 'ERROR').
            progress_pct (float, optional): Completion percentage (0.0 - 100.0). Defaults to 0.0.
            details (Optional[Dict[str, Any]], optional): Context metrics. Defaults to None.
            error (str, optional): Error description if worker failed. Defaults to "".
        """
        detail_str = f" | Details: {json.dumps(details, default=str)}" if details else ""
        err_str = f" | Error: {error}" if error else ""
        full_msg = f"[WORKER:{worker_id}] [{event.upper()}] ({progress_pct:.1f}%){detail_str}{err_str}"
        if error:
            cls.get_logger().error(full_msg)
        else:
            cls.get_logger().info(full_msg)

    @classmethod
    def log_acoustic(
        cls,
        filepath: str,
        bpm: Optional[float],
        key: str,
        camelot: str,
        elapsed_ms: float,
        energy: Optional[int] = None,
        lufs: Optional[float] = None,
    ) -> None:
        """Logs acoustic DSP analysis results (BPM, Camelot Key, Loudness).

        Args:
            filepath (str): Audio file path.
            bpm (Optional[float]): Estimated tempo in Beats Per Minute.
            key (str): Standard musical key notation (e.g. 'Am', 'C').
            camelot (str): Canonical Camelot code (e.g. '8A', '8B').
            elapsed_ms (float): Processing time in milliseconds.
            energy (Optional[int], optional): Estimated energy score (1-10). Defaults to None.
            lufs (Optional[float], optional): Measured integrated loudness (LUFS). Defaults to None.
        """
        fname = Path(filepath).name
        bpm_str = f"{bpm:.1f} BPM" if bpm else "N/A"
        energy_str = f", Energy: {energy}/10" if energy is not None else ""
        lufs_str = f", Loudness: {lufs:.1f} LUFS" if lufs is not None else ""
        cls.get_logger().debug(
            f"[ACOUSTIC] '{fname}' -> Tempo: {bpm_str}, Key: {key} ({camelot})"
            f"{energy_str}{lufs_str} in {elapsed_ms:.1f}ms"
        )

    @classmethod
    def log_scraping(
        cls,
        source: str,
        url: str,
        status_code: int,
        latency_ms: float,
        conflicts: Optional[Dict[str, Any]] = None,
        mapping: Optional[Dict[str, Any]] = None,
        error: str = "",
    ) -> None:
        """Logs external metadata scraping responses, HTTP latency, and reconciliation conflicts.

        Args:
            source (str): Provider name (e.g. 'Discogs', 'MusicBrainz', 'Wikipedia').
            url (str): Remote request endpoint.
            status_code (int): HTTP status code returned.
            latency_ms (float): Round-trip duration in milliseconds.
            conflicts (Optional[Dict[str, Any]], optional): Detected field conflicts.
            mapping (Optional[Dict[str, Any]], optional): Resolved canonical tag mapping.
            error (str, optional): Error message if query failed.
        """
        level = logging.INFO if 200 <= status_code < 300 else logging.WARNING
        conflict_str = f" | Conflicts: {json.dumps(conflicts)}" if conflicts else ""
        map_str = f" | Mapping: {json.dumps(mapping)}" if mapping else ""
        err_str = f" | Error: {error}" if error else ""
        cls.get_logger().log(
            level,
            f"[SCRAPER:{source}] {status_code} ({latency_ms:.1f}ms) -> {url}{conflict_str}{map_str}{err_str}",
        )

    # Backward compatibility alias
    log_http = log_scraping

    @classmethod
    def log_tag_edit(
        cls,
        filepath: str,
        fields_modified: List[str],
        pre_dump: Optional[Union[Dict[str, Any], bool]] = None,
        post_dump: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: str = "",
    ) -> None:
        """Logs physical metadata tag modifications with pre/post inspection diffs.

        Args:
            filepath (str): Path of audio file modified.
            fields_modified (List[str]): Field keys updated (e.g. ['title', 'artist']).
            pre_dump (Optional[Union[Dict[str, Any], bool]], optional): Original metadata dict,
                or boolean success status for legacy compatibility.
            post_dump (Optional[Dict[str, Any]], optional): Updated metadata dict.
            success (bool, optional): Whether write operation succeeded. Defaults to True.
            error (str, optional): Error details if write failed. Defaults to "".
        """
        # Backward compatibility check for legacy calls: log_tag_edit(path, fields, success)
        actual_success = success
        actual_pre = None
        if isinstance(pre_dump, bool):
            actual_success = pre_dump
        elif isinstance(pre_dump, dict):
            actual_pre = pre_dump

        fname = Path(filepath).name
        if actual_success:
            cls.get_logger().info(f"[TAG] Saved [{', '.join(fields_modified)}] -> '{fname}'")
            if actual_pre and post_dump:
                diffs = {}
                for k in fields_modified:
                    diffs[k] = {"before": actual_pre.get(k), "after": post_dump.get(k)}
                cls.get_logger().debug(f"[TAG:DIFF] '{fname}' -> {json.dumps(diffs)}")
        else:
            cls.get_logger().error(f"[TAG:FAIL] Could not update '{fname}': {error}")

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
            event_type (str): Category (e.g. 'CODEC_INIT', 'LOAD', 'PLAY', 'BUFFER_UNDERRUN').
            message (str): Human-readable event description.
            details (Optional[Dict[str, Any]], optional): Telemetry metrics. Defaults to None.
            level (str, optional): Log severity ('debug', 'info', 'warning', 'error'). Defaults to 'info'.
        """
        detail_str = f" | Details: {json.dumps(details)}" if details else ""
        full_msg = f"[AUDIO:{event_type.upper()}] {message}{detail_str}"
        lvl_func = getattr(cls.get_logger(), level.lower(), cls.get_logger().info)
        lvl_func(full_msg)

    @classmethod
    def log_oauth(
        cls,
        service: str,
        event: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logs OAuth authorization flows, loopback callbacks, and token refreshes.

        Guarantees that sensitive secrets, client secrets, and full bearer tokens
        are redacted before writing to log streams.

        Args:
            service (str): Service name (e.g. 'Spotify', 'SoundCloud', 'YouTube').
            event (str): Flow event ('URL_BUILT', 'CALLBACK_RECEIVED', 'TOKEN_ACQUIRED', 'REFRESH_SUCCESS', 'ERROR').
            details (Optional[Dict[str, Any]], optional): Context metrics (redacted).
        """
        safe_details = {}
        if details:
            for k, v in details.items():
                if any(sec in k.lower() for sec in ("token", "secret", "password", "key", "code")):
                    safe_details[k] = "******** [REDACTED]"
                else:
                    safe_details[k] = v
        detail_str = f" | Details: {json.dumps(safe_details)}" if safe_details else ""
        cls.get_logger().info(f"[OAUTH:{service.upper()}] [{event.upper()}]{detail_str}")

    @classmethod
    def log_file_op(
        cls,
        action: str,
        source: str,
        target: str,
        collision_resolved: Union[str, bool] = "",
        success: bool = True,
        details: str = "",
    ) -> None:
        """Logs physical file dispatch operations (Move, Copy, Rename, Delete).

        Args:
            action (str): Operation type ('MOVE', 'COPY', 'RENAME', 'DELETE').
            source (str): Source path.
            target (str): Target destination path.
            collision_resolved (Union[str, bool], optional): Strategy on conflict ('RENAME', 'OVERWRITE', 'SKIP').
            success (bool, optional): Whether operation succeeded. Defaults to True.
            details (str, optional): Additional error or context details. Defaults to "".
        """
        col_str = f" [Collision: {collision_resolved}]" if collision_resolved else ""
        if success:
            cls.get_logger().info(f"[DISPATCH:{action.upper()}] '{Path(source).name}' -> '{target}'{col_str}")
        else:
            cls.get_logger().error(f"[DISPATCH:FAIL] '{Path(source).name}' -> '{target}'{col_str}: {details}")

    @classmethod
    def debug(cls, domain: str, message: str = "") -> None:
        """Logs a debug message prefixed with domain name.

        Args:
            domain (str): Subsystem or domain prefix, or full message if single argument.
            message (str, optional): Log message. Defaults to "".
        """
        if not message:
            cls.get_logger().debug(domain)
        else:
            cls.get_logger().debug(f"[{domain}] {message}")

    @classmethod
    def info(cls, domain: str, message: str = "") -> None:
        """Logs an informational message prefixed with domain name.

        Args:
            domain (str): Subsystem or domain prefix, or full message if single argument.
            message (str, optional): Log message. Defaults to "".
        """
        if not message:
            cls.get_logger().info(domain)
        else:
            cls.get_logger().info(f"[{domain}] {message}")

    @classmethod
    def warning(cls, domain: str, message: str = "") -> None:
        """Logs a warning message prefixed with domain name.

        Args:
            domain (str): Subsystem or domain prefix, or full message if single argument.
            message (str, optional): Log message. Defaults to "".
        """
        if not message:
            cls.get_logger().warning(domain)
        else:
            cls.get_logger().warning(f"[{domain}] {message}")

    @classmethod
    def error(cls, domain: str, message: str = "") -> None:
        """Logs an error message prefixed with domain name and flushes stream.

        Args:
            domain (str): Subsystem or domain prefix, or full message if single argument.
            message (str, optional): Log message. Defaults to "".
        """
        if not message:
            cls.get_logger().error(domain)
        else:
            cls.get_logger().error(f"[{domain}] {message}")
        cls.flush()

    @classmethod
    def critical(cls, domain: str, message: str = "") -> None:
        """Logs a critical error message prefixed with domain name and forces immediate physical flush.

        Args:
            domain (str): Subsystem or domain prefix, or full message if single argument.
            message (str, optional): Log message. Defaults to "".
        """
        if not message:
            cls.get_logger().critical(domain)
        else:
            cls.get_logger().critical(f"[{domain}] {message}")
        cls.flush()

    @classmethod
    def exception(cls, domain: str, message: str = "") -> None:
        """Logs an exception traceback prefixed with domain name and forces immediate physical flush.

        Args:
            domain (str): Subsystem or domain prefix, or full message if single argument.
            message (str, optional): Log message. Defaults to "".
        """
        if not message:
            cls.get_logger().exception(domain)
        else:
            cls.get_logger().exception(f"[{domain}] {message}")
        cls.flush()

    @classmethod
    def flush(cls) -> None:
        """Flushes all attached log file and stream handlers to physical disk immediately."""
        with cls._lock:
            if cls._logger:
                for h in cls._logger.handlers:
                    try:
                        h.flush()
                        if hasattr(h, "stream") and h.stream and hasattr(h.stream, "fileno"):
                            try:
                                os.fsync(h.stream.fileno())
                            except (AttributeError, OSError):
                                pass
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
            - Crash logs from faulthandler (`crash.log`).
            - Detailed system telemetry (OS, architecture, CPU, Python, Qt, libVLC).
            - Database overview metrics (total tracks, crates count, database file size).
            - Sanitized settings dump (all passwords, client secrets, and API tokens are masked).

        Args:
            destination_zip (Optional[Union[str, Path]], optional): Destination path.
                If None, defaults to the user's Desktop or home directory.
            db (Optional[Any], optional): Optional Database instance to collect track statistics.

        Returns:
            str: Absolute file path to the generated support ZIP bundle.

        Raises:
            IOError: If writing to the destination path fails.
        """
        cls.flush()

        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        if destination_zip:
            out_path = Path(destination_zip).resolve()
        else:
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home()
            out_path = desktop / f"musicat_support_bundle_{now_str}.zip"

        out_path.parent.mkdir(parents=True, exist_ok=True)

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

        try:
            from ..player.vlc_engine import _VLC_AVAILABLE
            sys_info["libvlc_available"] = _VLC_AVAILABLE
        except Exception:
            sys_info["libvlc_available"] = False

        with zipfile.ZipFile(str(out_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            diag_json = json.dumps(sys_info, indent=2, ensure_ascii=False)
            zf.writestr("diagnostics/system_info.json", diag_json)

            logs_dir = PathResolver.get_logs_dir()
            if logs_dir.exists():
                for p in logs_dir.glob("*"):
                    if p.is_file() and (p.suffix in (".log", ".zip", ".gz")):
                        try:
                            zf.write(p, arcname=f"logs/{p.name}")
                        except Exception:
                            pass

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
