"""
Structured Logging Subsystem for Musicat.

Features:
- Automatic size-based rotation (max 20MB) with automatic gzip compression of rotated logs.
- Multi-level logging: DEBUG, INFO, WARNING, ERROR.
- Granular domain logging: filesystem scanning, acoustic analysis, HTTP scrapers,
  tag modifications, and physical file operations.
- Thread-safe GUI Log Handler for streaming live messages to Qt widgets.
"""

import gzip
import logging
import os
import shutil
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .path_resolver import PathResolver


class CompressedRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler that compresses old log files using gzip."""

    def rotation_filename(self, default_name: str) -> str:
        """Returns the target filename for rotated log ending with .gz."""
        return f"{default_name}.gz"

    def rotate(self, source: str, dest: str) -> None:
        """Compresses the rotated log file into gzip format and removes the original.

        Args:
            source (str): Source log file path that exceeded maxBytes.
            dest (str): Target destination path ending in .gz.
        """
        try:
            with open(source, "rb") as f_in:
                with gzip.open(dest, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(source)
        except Exception:
            # Fallback to standard rotation if compression fails
            if os.path.exists(source):
                try:
                    os.rename(source, dest)
                except Exception:
                    pass


class GuiLogHandler(logging.Handler):
    """Thread-safe logging handler that dispatches formatted records to GUI listeners."""

    def __init__(self, callback: Optional[Callable[[str, int, str], None]] = None) -> None:
        """Initializes the GUI logging handler.

        Args:
            callback (Optional[Callable[[str, int, str], None]]): Callback function receiving
                (timestamp, levelno, message).
        """
        super().__init__()
        self._callback: Optional[Callable[[str, int, str], None]] = callback
        self._lock = threading.Lock()

    def set_callback(self, callback: Callable[[str, int, str], None]) -> None:
        """Registers or updates the GUI subscriber callback."""
        with self._lock:
            self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        """Dispatches formatted log record to the active callback if present."""
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
    """Central logging controller for Musicat."""

    _logger: Optional[logging.Logger] = None
    _gui_handler: Optional[GuiLogHandler] = None
    _lock = threading.Lock()

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Returns the singleton application logger, initializing handlers if needed.

        Returns:
            logging.Logger: Configured Musicat logger instance.
        """
        with cls._lock:
            if cls._logger is not None:
                return cls._logger

            logger = logging.getLogger("Musicat")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False

            # Clear existing handlers if any
            logger.handlers.clear()

            # Formatters
            detailed_fmt = logging.Formatter(
                "[%(asctime)s] [%(levelname)-7s] [%(name)s:%(threadName)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_fmt = logging.Formatter(
                "[%(levelname)-7s] %(message)s"
            )

            # 1. Console Stream Handler (guarded for frozen/noconsole apps where stdout may be None)
            if sys.stdout is not None and hasattr(sys.stdout, "write"):
                try:
                    console_h = logging.StreamHandler(sys.stdout)
                    console_h.setLevel(logging.INFO)
                    console_h.setFormatter(console_fmt)
                    logger.addHandler(console_h)
                except Exception:
                    pass

            # 2. Compressed Rotating File Handler (Max 20MB, 5 backup archives)
            log_dirs = []
            primary_data_dir = PathResolver.get_data_dir()
            log_dirs.append(primary_data_dir / "logs")

            # In portable mode, also log to root app_dir/logs for immediate user discovery
            if PathResolver.is_portable_mode():
                app_logs = PathResolver.get_app_dir() / "logs"
                try:
                    if app_logs.resolve() != (primary_data_dir / "logs").resolve():
                        log_dirs.append(app_logs)
                except Exception:
                    log_dirs.append(app_logs)

            for ldir in log_dirs:
                try:
                    ldir.mkdir(parents=True, exist_ok=True)
                    log_file = ldir / "musicat.log"
                    file_h = CompressedRotatingFileHandler(
                        filename=str(log_file),
                        maxBytes=20 * 1024 * 1024,  # 20 Megabytes
                        backupCount=5,
                        encoding="utf-8",
                    )
                    file_h.setLevel(logging.DEBUG)
                    file_h.setFormatter(detailed_fmt)
                    logger.addHandler(file_h)
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
            callback (Callable[[str, int, str], None]): Receiver function.
        """
        cls.get_logger()
        if cls._gui_handler:
            cls._gui_handler.set_callback(callback)

    # ================= GRANULAR DOMAIN EVENT LOGGERS =================

    @classmethod
    def log_scan(cls, folder: str, files_found: int, inserted: int, elapsed_ms: float) -> None:
        """Logs directory indexing scan statistics."""
        cls.get_logger().info(
            f"[SCAN] Indexed '{folder}' -> Found: {files_found}, Inserted: {inserted} in {elapsed_ms:.1f}ms"
        )

    @classmethod
    def log_acoustic(cls, filepath: str, bpm: Optional[float], key: str, camelot: str, elapsed_ms: float) -> None:
        """Logs acoustic analysis results for a track."""
        fname = Path(filepath).name
        bpm_str = f"{bpm:.1f} BPM" if bpm else "N/A"
        cls.get_logger().debug(
            f"[ACOUSTIC] '{fname}' -> Tempo: {bpm_str}, Key: {key} ({camelot}) in {elapsed_ms:.1f}ms"
        )

    @classmethod
    def log_http(
        cls,
        source: str,
        url: str,
        status_code: int,
        latency_ms: float,
        results_count: int = 0,
    ) -> None:
        """Logs HTTP metadata scraper requests and performance."""
        level = logging.INFO if 200 <= status_code < 300 else logging.WARNING
        cls.get_logger().log(
            level,
            f"[HTTP:{source}] {status_code} ({latency_ms:.1f}ms) -> {url} [Results: {results_count}]",
        )

    @classmethod
    def log_tag_edit(cls, filepath: str, fields_modified: List[str], success: bool, error: str = "") -> None:
        """Logs metadata tag modifications."""
        fname = Path(filepath).name
        if success:
            cls.get_logger().info(f"[TAG] Saved [{', '.join(fields_modified)}] -> '{fname}'")
        else:
            cls.get_logger().error(f"[TAG:FAIL] Could not update '{fname}': {error}")

    @classmethod
    def log_file_op(cls, action: str, source: str, target: str, success: bool, details: str = "") -> None:
        """Logs file dispatch operations (copy/move)."""
        if success:
            cls.get_logger().info(f"[DISPATCH:{action.upper()}] '{Path(source).name}' -> '{target}'")
        else:
            cls.get_logger().error(f"[DISPATCH:FAIL] '{Path(source).name}' -> '{target}': {details}")

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
    def flush(cls) -> None:
        """Flushes all attached log handlers to disk immediately."""
        with cls._lock:
            if cls._logger:
                for h in cls._logger.handlers:
                    try:
                        h.flush()
                    except Exception:
                        pass

