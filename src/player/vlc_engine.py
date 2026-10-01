"""
High-Performance Audio Engine for Musicat based on libVLC.

Provides universal audio format decoding (MP3, WAV, FLAC, AIFF, M4A, OGG, ALAC, OPUS),
precise waveform scrubbing, volume management, looping, and DJ pitch/tempo rate adjustment (+/- 8% or +/- 16%).
Dispatches audio events asynchronously off the Qt GUI thread.
"""

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from ..core.logger import MusicatLogger

# Try importing vlc module
_VLC_AVAILABLE = False
try:
    # Check potential VLC locations on Windows before importing
    if sys.platform == "win32":
        app_dir = Path(__file__).resolve().parent.parent.parent
        vlc_search_dirs = [
            app_dir / "vlc",
            app_dir,
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "VideoLAN" / "VLC",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "VideoLAN" / "VLC",
        ]
        for vdir in vlc_search_dirs:
            dll_cand = vdir / "libvlc.dll"
            if dll_cand.exists():
                os.environ["PYTHON_VLC_LIB_PATH"] = str(dll_cand)
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(str(vdir))
                    except Exception:
                        pass
                break

    import vlc
    _VLC_AVAILABLE = True
except Exception as e:
    _VLC_AVAILABLE = False


class VLCAudioPlayer:
    """Asynchronous DJ player engine wrapping libVLC with pitch bending and scrubbing."""

    def __init__(self) -> None:
        """Initializes the VLC player instance and event listeners."""
        self._is_vlc = _VLC_AVAILABLE
        self._instance: Any = None
        self._player: Any = None
        self._current_filepath: str = ""
        self._is_looping: bool = False
        self._pitch_rate: float = 1.0  # 1.0 = Normal, 1.08 = +8%
        self._volume: int = 80
        self._lock = threading.Lock()

        # Listeners
        self._time_callback: Optional[Callable[[int, int], None]] = None  # (cur_ms, total_ms)
        self._state_callback: Optional[Callable[[str], None]] = None     # ("playing", "paused", "stopped")
        self._finished_callback: Optional[Callable[[], None]] = None

        self._monitor_running = False
        self._monitor_thread: Optional[threading.Thread] = None

        if self._is_vlc:
            try:
                # VLC parameters: minimal latency, no video, no OSD
                args = [
                    "--no-video",
                    "--no-osd",
                    "--no-snapshot-preview",
                    "--audio-resampler=soxr",
                ]
                self._instance = vlc.Instance(args)
                self._player = self._instance.media_player_new()
                MusicatLogger.get_logger().info("[PLAYER:VLC] libVLC audio engine initialized successfully.")
            except Exception as e:
                MusicatLogger.get_logger().warning(f"[PLAYER:VLC] Failed to instantiate libVLC: {e}. Switching to fallback mode.")
                self._is_vlc = False

    def is_available(self) -> bool:
        """Returns True if native libVLC backend is active, False for fallback."""
        return self._is_vlc and (self._player is not None)

    def set_callbacks(
        self,
        time_cb: Optional[Callable[[int, int], None]] = None,
        state_cb: Optional[Callable[[str], None]] = None,
        finished_cb: Optional[Callable[[], None]] = None,
    ) -> None:
        """Registers listener callbacks for playback position and state changes.

        Args:
            time_cb (Optional[Callable[[int, int], None]]): Receives (current_ms, duration_ms).
            state_cb (Optional[Callable[[str], None]]): Receives ('playing', 'paused', 'stopped').
            finished_cb (Optional[Callable[[], None]]): Fired on track completion.
        """
        with self._lock:
            self._time_callback = time_cb
            self._state_callback = state_cb
            self._finished_callback = finished_cb

    def load(self, filepath: str) -> bool:
        """Loads an audio file into the player.

        Args:
            filepath (str): Absolute path to audio track.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        if not filepath or not Path(filepath).exists():
            return False

        with self._lock:
            self._current_filepath = str(Path(filepath).resolve())

            if self.is_available():
                media = self._instance.media_new(self._current_filepath)
                self._player.set_media(media)
                self._player.audio_set_volume(self._volume)
                self._player.set_rate(self._pitch_rate)
                # Parse media info
                media.parse_with_options(vlc.MediaParseFlag.local, -1)

            MusicatLogger.get_logger().debug(f"[PLAYER] Loaded track: {Path(filepath).name}")
            return True

    def play(self) -> None:
        """Starts or resumes audio playback asynchronously."""
        if not self._current_filepath:
            return

        if self.is_available():
            self._player.play()
            self._start_monitor_thread()

        if self._state_callback:
            self._state_callback("playing")

    def pause(self) -> None:
        """Pauses audio playback."""
        if self.is_available():
            self._player.pause()

        if self._state_callback:
            self._state_callback("paused")

    def stop(self) -> None:
        """Stops audio playback and resets position to beginning."""
        if self.is_available():
            self._player.stop()

        self._stop_monitor_thread()

        if self._state_callback:
            self._state_callback("stopped")
        if self._time_callback:
            self._time_callback(0, self.get_duration_ms())

    def toggle_play_pause(self) -> None:
        """Toggles between playing and paused states."""
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def is_playing(self) -> bool:
        """Checks if audio is currently playing."""
        if self.is_available():
            return bool(self._player.is_playing())
        return False

    def seek_ms(self, target_ms: int) -> None:
        """Seeks accurately to a millisecond timestamp in the track.

        Args:
            target_ms (int): Target timestamp in milliseconds.
        """
        if self.is_available():
            self._player.set_time(max(0, target_ms))

    def seek_fraction(self, fraction: float) -> None:
        """Seeks to a normalized position between 0.0 and 1.0 (matching waveform clicks).

        Args:
            fraction (float): Target ratio [0.0 - 1.0].
        """
        clamped = max(0.0, min(1.0, fraction))
        if self.is_available():
            self._player.set_position(clamped)

    def set_volume(self, volume_percent: int) -> None:
        """Adjusts the playback volume.

        Args:
            volume_percent (int): Volume level from 0 to 100.
        """
        self._volume = max(0, min(100, volume_percent))
        if self.is_available():
            self._player.audio_set_volume(self._volume)

    def get_volume(self) -> int:
        """Returns the current volume level [0-100]."""
        return self._volume

    def set_pitch_rate(self, rate: float) -> None:
        """Adjusts the DJ playback tempo and pitch (speed rate).

        Args:
            rate (float): Multiplier (e.g., 1.0 = standard, 1.08 = +8%, 0.92 = -8%).
        """
        # Clamp to realistic DJ pitch ranges [-16% to +16%]
        clamped_rate = max(0.80, min(1.20, rate))
        self._pitch_rate = clamped_rate
        if self.is_available():
            self._player.set_rate(clamped_rate)
            MusicatLogger.get_logger().debug(f"[PLAYER:PITCH] Rate set to {clamped_rate:.3f}x")

    def get_pitch_rate(self) -> float:
        """Returns the current pitch rate multiplier."""
        return self._pitch_rate

    def set_loop(self, enabled: bool) -> None:
        """Enables or disables automatic looping of the current track."""
        self._is_looping = enabled

    def is_looping(self) -> bool:
        """Returns True if looping is enabled."""
        return self._is_looping

    def get_position_ms(self) -> int:
        """Returns current playback position in milliseconds."""
        if self.is_available():
            t = self._player.get_time()
            return max(0, t) if t != -1 else 0
        return 0

    def get_duration_ms(self) -> int:
        """Returns total duration of currently loaded track in milliseconds."""
        if self.is_available():
            d = self._player.get_length()
            return max(0, d) if d != -1 else 0
        return 0

    # ================= ASYNCHRONOUS POSITION MONITOR =================

    def _start_monitor_thread(self) -> None:
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _stop_monitor_thread(self) -> None:
        self._monitor_running = False

    def _monitor_loop(self) -> None:
        """Background thread updating UI seekbars and checking track endings without freezing Qt."""
        while self._monitor_running:
            if not self.is_available():
                break

            state = self._player.get_state()
            if state == vlc.State.Ended:
                if self._is_looping:
                    self._player.set_time(0)
                    self._player.play()
                else:
                    self._stop_monitor_thread()
                    if self._finished_callback:
                        self._finished_callback()
                    if self._state_callback:
                        self._state_callback("stopped")
                break

            cur_ms = self.get_position_ms()
            tot_ms = self.get_duration_ms()

            if self._time_callback:
                self._time_callback(cur_ms, tot_ms)

            time.sleep(0.05)  # 20 updates per second for smooth waveform scrubbing
