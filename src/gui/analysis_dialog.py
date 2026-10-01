"""
Hardware-Aware Acoustic Analysis Dialog for Musicat.

Features:
- Thread-safe QThread bridge for non-blocking UI responsiveness.
- Multi-core CPU utilization slider and logical core detector.
- In-memory L1 RAM cache configuration slider.
- Real-time telemetry: live throughput (tracks/sec), progress percentage, ETA.
- Interactive user controls: Start, Pause, Resume, Cancel.
- Zero disk I/O bottleneck via batch RAM buffer flushing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.audio.parallel_analyzer import ParallelAnalyzer
from src.core.db import Database
from src.core.memory_cache import AnalysisMemoryCache, WaveformMemoryCache


class AnalysisControllerThread(QThread):
    """Background QThread orchestrator bridging ParallelAnalyzer with the Qt GUI."""

    progress_signal = Signal(dict)
    flushed_signal = Signal(int)
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(
        self,
        filepaths: List[str],
        db: Database,
        num_workers: int = 4,
        cache_mb: int = 512,
        batch_size: int = 25,
        write_physical_tags: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.filepaths = filepaths
        self.db = db
        self.num_workers = num_workers
        self.cache_mb = cache_mb
        self.batch_size = batch_size
        self.write_physical_tags = write_physical_tags

        self.memory_cache = AnalysisMemoryCache()
        self.waveform_cache = WaveformMemoryCache.get_instance(default_mb=cache_mb)
        self.waveform_cache.set_max_memory_mb(cache_mb)

        self.analyzer = ParallelAnalyzer(
            num_workers=self.num_workers,
            batch_size=self.batch_size,
            memory_cache=self.memory_cache,
            waveform_cache=self.waveform_cache,
        )

    def run(self) -> None:
        """Executes the analysis pipeline in the background."""
        try:
            # 1. Start periodic RAM auto-flush to disk
            self.memory_cache.start_auto_flush(
                disk_db=self.db,
                interval_sec=20.0,
                batch_threshold=100,
                on_flush_callback=lambda count: self.flushed_signal.emit(count),
            )

            # 2. Run parallel acoustic analysis
            summary = self.analyzer.analyze_tracks(
                filepaths=self.filepaths,
                on_progress=lambda info: self.progress_signal.emit(info),
            )

            # 3. Stop auto-flush and execute final commit to persistent disk DB
            final_flushed = self.memory_cache.stop_auto_flush(final_flush=True)
            if final_flushed > 0:
                self.flushed_signal.emit(final_flushed)

            self.finished_signal.emit(summary)

        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.memory_cache.close()

    def pause(self) -> None:
        """Pauses the analyzer."""
        self.analyzer.pause()

    def resume(self) -> None:
        """Resumes the analyzer."""
        self.analyzer.resume()

    def cancel(self) -> None:
        """Cancels analysis cleanly."""
        self.analyzer.cancel()


class AcousticAnalysisDialog(QDialog):
    """Modern dark-themed dialog for high-performance acoustic batch analysis."""

    def __init__(
        self,
        tracks: List[Dict[str, Any]],
        db: Database,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.tracks = tracks
        self.db = db
        self.thread: Optional[AnalysisControllerThread] = None
        self._is_paused = False
        self._total_flushed_count = 0

        self.setWindowTitle("Musicat — Analizzatore Acustico Hardware-Aware")
        self.setMinimumSize(700, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #12141a;
                color: #e0e6ed;
            }
            QGroupBox {
                border: 1px solid #282c3c;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #00d2ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                left: 10px;
            }
            QLabel {
                color: #d1d5db;
                font-size: 13px;
            }
            QProgressBar {
                border: 1px solid #282c3c;
                border-radius: 6px;
                background-color: #1b1e28;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0091ea, stop:1 #00e5ff
                );
                border-radius: 5px;
            }
            QPushButton {
                background-color: #242838;
                border: 1px solid #363c54;
                border-radius: 6px;
                color: #ffffff;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2f344a;
                border-color: #00d2ff;
            }
            QPushButton:disabled {
                background-color: #161822;
                border-color: #222636;
                color: #555b70;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #252838;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00d2ff;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #00d2ff;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QSpinBox {
                background-color: #1a1c26;
                border: 1px solid #363c54;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px;
                font-weight: bold;
            }
            QCheckBox {
                color: #cbd5e1;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #3b425b;
                background: #1b1e28;
            }
            QCheckBox::indicator:checked {
                background-color: #00d2ff;
                border-color: #00e5ff;
            }
        """)

        self._init_ui()

    def _init_ui(self) -> None:
        """Constructs dialog user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 1. Header Banner
        header_layout = QHBoxLayout()
        header_icon = QLabel("⚡")
        header_icon.setFont(QFont("Segoe UI Emoji", 24))
        header_layout.addWidget(header_icon)

        header_text_layout = QVBoxLayout()
        title_label = QLabel("Analizzatore Acustico Hardware-Aware")
        title_label.setStyleSheet("font-size: 17px; font-weight: bold; color: #ffffff;")
        subtitle_label = QLabel("Multiprocessing nativo multi-core con buffer L1 in RAM & zero disk I/O bottleneck.")
        subtitle_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        header_text_layout.addWidget(title_label)
        header_text_layout.addWidget(subtitle_label)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # 2. Configuration Box
        config_group = QGroupBox("⚙️ Configurazione Risorse Hardware")
        config_layout = QGridLayout(config_group)
        config_layout.setContentsMargins(16, 16, 16, 16)
        config_layout.setSpacing(12)

        # CPU Cores allocation
        cores_max = os.cpu_count() or 4
        default_cores = max(1, cores_max - 1)

        self.label_cores = QLabel(f"Core CPU Dedicati: {default_cores} / {cores_max} logici")
        self.slider_cores = QSlider(Qt.Orientation.Horizontal)
        self.slider_cores.setRange(1, cores_max)
        self.slider_cores.setValue(default_cores)
        self.spin_cores = QSpinBox()
        self.spin_cores.setRange(1, cores_max)
        self.spin_cores.setValue(default_cores)

        self.slider_cores.valueChanged.connect(self.spin_cores.setValue)
        self.spin_cores.valueChanged.connect(self.slider_cores.setValue)
        self.slider_cores.valueChanged.connect(self._on_cores_changed)

        config_layout.addWidget(self.label_cores, 0, 0)
        config_layout.addWidget(self.slider_cores, 0, 1)
        config_layout.addWidget(self.spin_cores, 0, 2)

        # RAM Cache Size allocation
        self.label_ram = QLabel("Dimensione Buffer RAM L1: 512 MB")
        self.slider_ram = QSlider(Qt.Orientation.Horizontal)
        self.slider_ram.setRange(128, 2048)
        self.slider_ram.setSingleStep(128)
        self.slider_ram.setValue(512)
        self.spin_ram = QSpinBox()
        self.spin_ram.setRange(128, 4096)
        self.spin_ram.setSingleStep(128)
        self.spin_ram.setValue(512)

        self.slider_ram.valueChanged.connect(self.spin_ram.setValue)
        self.spin_ram.valueChanged.connect(self.slider_ram.setValue)
        self.slider_ram.valueChanged.connect(self._on_ram_changed)

        config_layout.addWidget(self.label_ram, 1, 0)
        config_layout.addWidget(self.slider_ram, 1, 1)
        config_layout.addWidget(self.spin_ram, 1, 2)

        # Write physical tags checkbox
        self.check_write_tags = QCheckBox("Scrivi metadati (BPM, Chiave Camelot) nei file fisici (ID3 / Vorbis)")
        self.check_write_tags.setChecked(True)
        config_layout.addWidget(self.check_write_tags, 2, 0, 1, 3)

        main_layout.addWidget(config_group)

        # 3. Telemetry and Progress Box
        telemetry_group = QGroupBox("📊 Avanzamento & Metriche in Tempo Reale")
        telemetry_layout = QVBoxLayout(telemetry_group)
        telemetry_layout.setContentsMargins(16, 16, 16, 16)
        telemetry_layout.setSpacing(12)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        telemetry_layout.addWidget(self.progress_bar)

        # Metrics Grid
        stats_grid = QGridLayout()
        stats_grid.setSpacing(10)

        self.val_throughput = QLabel("0.0 tracce / sec")
        self.val_throughput.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 14px;")
        stats_grid.addWidget(QLabel("⚡ Velocità (Throughput):"), 0, 0)
        stats_grid.addWidget(self.val_throughput, 0, 1)

        self.val_tracks = QLabel(f"0 / {len(self.tracks)} (0.0%)")
        self.val_tracks.setStyleSheet("color: #ffffff; font-weight: bold;")
        stats_grid.addWidget(QLabel("📈 Tracce Elaborate:"), 0, 2)
        stats_grid.addWidget(self.val_tracks, 0, 3)

        self.val_elapsed = QLabel("00:00:00")
        self.val_elapsed.setStyleSheet("color: #e2e8f0; font-family: monospace;")
        stats_grid.addWidget(QLabel("⏱️ Tempo Trascorso:"), 1, 0)
        stats_grid.addWidget(self.val_elapsed, 1, 1)

        self.val_eta = QLabel("--:--:--")
        self.val_eta.setStyleSheet("color: #ffd166; font-family: monospace; font-weight: bold;")
        stats_grid.addWidget(QLabel("⏳ Tempo Stimato (ETA):"), 1, 2)
        stats_grid.addWidget(self.val_eta, 1, 3)

        self.val_ram_status = QLabel("0 tracce in RAM (0 su disco)")
        self.val_ram_status.setStyleSheet("color: #a78bfa;")
        stats_grid.addWidget(QLabel("💾 Stato Buffer RAM L1:"), 2, 0)
        stats_grid.addWidget(self.val_ram_status, 2, 1, 1, 3)

        self.val_current_file = QLabel("In attesa di avvio...")
        self.val_current_file.setStyleSheet("color: #94a3b8; font-style: italic;")
        stats_grid.addWidget(QLabel("🎵 Traccia Corrente:"), 3, 0)
        stats_grid.addWidget(self.val_current_file, 3, 1, 1, 3)

        telemetry_layout.addLayout(stats_grid)
        main_layout.addWidget(telemetry_group)

        # 4. Action Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.btn_start = QPushButton("▶ Avvia Analisi")
        self.btn_start.setStyleSheet("background-color: #0077b6; border-color: #0096c7;")
        self.btn_start.clicked.connect(self._on_start_clicked)
        button_layout.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ Pausa")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("background-color: #b45309; border-color: #d97706;")
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        button_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("⏹ Annulla")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("background-color: #991b1b; border-color: #dc2626;")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.btn_cancel)

        button_layout.addStretch()

        self.btn_close = QPushButton("Chiudi")
        self.btn_close.clicked.connect(self.accept)
        button_layout.addWidget(self.btn_close)

        main_layout.addLayout(button_layout)

    def _on_cores_changed(self, value: int) -> None:
        """Updates CPU core indicator label."""
        cores_max = os.cpu_count() or 4
        self.label_cores.setText(f"Core CPU Dedicati: {value} / {cores_max} logici")

    def _on_ram_changed(self, value: int) -> None:
        """Updates RAM cache indicator label."""
        self.label_ram.setText(f"Dimensione Buffer RAM L1: {value} MB")

    def _format_time(self, seconds: float) -> str:
        """Formats seconds into HH:MM:SS."""
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _on_start_clicked(self) -> None:
        """Starts or restarts analysis execution."""
        if not self.tracks:
            QMessageBox.warning(self, "Nessuna traccia", "Nessuna traccia selezionata per l'analisi.")
            return

        # Disable configuration inputs during active processing
        self.slider_cores.setEnabled(False)
        self.spin_cores.setEnabled(False)
        self.slider_ram.setEnabled(False)
        self.spin_ram.setEnabled(False)
        self.check_write_tags.setEnabled(False)

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.btn_close.setEnabled(False)

        filepaths = [t.get("filepath", "") for t in self.tracks if t.get("filepath")]

        self.thread = AnalysisControllerThread(
            filepaths=filepaths,
            db=self.db,
            num_workers=self.slider_cores.value(),
            cache_mb=self.slider_ram.value(),
            batch_size=25,
            write_physical_tags=self.check_write_tags.isChecked(),
            parent=self,
        )

        self.thread.progress_signal.connect(self._on_progress_update)
        self.thread.flushed_signal.connect(self._on_flushed_update)
        self.thread.finished_signal.connect(self._on_finished)
        self.thread.error_signal.connect(self._on_error)
        self.thread.start()

    def _on_pause_clicked(self) -> None:
        """Toggles pause/resume state."""
        if not self.thread:
            return

        if not self._is_paused:
            self.thread.pause()
            self._is_paused = True
            self.btn_pause.setText("▶ Riprendi")
            self.btn_pause.setStyleSheet("background-color: #047857; border-color: #10b981;")
            self.val_current_file.setText("⏸ Analisi in pausa...")
        else:
            self.thread.resume()
            self._is_paused = False
            self.btn_pause.setText("⏸ Pausa")
            self.btn_pause.setStyleSheet("background-color: #b45309; border-color: #d97706;")

    def _on_cancel_clicked(self) -> None:
        """Cancels running analysis."""
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Conferma Annullamento",
                "Sei sicuro di voler interrompere l'analisi acustica?\nI dati già analizzati rimarranno salvati nel database.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.btn_cancel.setEnabled(False)
                self.val_current_file.setText("⏹ Interruzione in corso...")
                self.thread.cancel()

    def _on_progress_update(self, info: Dict[str, Any]) -> None:
        """Updates GUI telemetry controls with new metrics."""
        percent = int(info.get("percent", 0))
        self.progress_bar.setValue(percent)

        processed = info.get("processed", 0)
        total = info.get("total", len(self.tracks))
        self.val_tracks.setText(f"{processed:,} / {total:,} ({percent}%)")

        throughput = info.get("throughput", 0.0)
        self.val_throughput.setText(f"{throughput:.1f} tracce / sec")

        elapsed = info.get("elapsed_seconds", 0.0)
        self.val_elapsed.setText(self._format_time(elapsed))

        eta = info.get("eta_seconds", 0.0)
        self.val_eta.setText(self._format_time(eta))

        cur_file = info.get("current_track", "")
        if len(cur_file) > 55:
            cur_file = cur_file[:25] + "..." + cur_file[-25:]
        self.val_current_file.setText(cur_file)

        pending_ram = info.get("pending_ram_count", 0)
        self.val_ram_status.setText(
            f"{pending_ram} tracce nel buffer RAM (Sincronizzate su disco: {self._total_flushed_count:,})"
        )

    def _on_flushed_update(self, flushed_count: int) -> None:
        """Updates disk synchronization indicator."""
        self._total_flushed_count += flushed_count
        self.val_ram_status.setText(
            f"0 tracce nel buffer RAM (Sincronizzate su disco: {self._total_flushed_count:,})"
        )

    def _on_finished(self, summary: Dict[str, Any]) -> None:
        """Called when parallel analyzer completes all batches."""
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(True)

        success = summary.get("success", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 0)
        elapsed = summary.get("elapsed_seconds", 0.0)
        avg_tp = summary.get("average_throughput", 0.0)

        self.progress_bar.setValue(100)
        self.val_current_file.setText("✅ Analisi completata con successo!")
        self.val_current_file.setStyleSheet("color: #10b981; font-weight: bold;")

        QMessageBox.information(
            self,
            "Analisi Completata",
            f"Analisi acustica completata con successo!\n\n"
            f"• Tracce analizzate: {success:,} di {total:,}\n"
            f"• Tracce fallite: {failed}\n"
            f"• Velocità media: {avg_tp:.1f} tracce/sec\n"
            f"• Tempo impiegato: {self._format_time(elapsed)}\n"
            f"• Totale sincronizzato su disco: {self._total_flushed_count:,}",
        )

    def _on_error(self, err_msg: str) -> None:
        """Handles background thread errors."""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(True)
        QMessageBox.critical(self, "Errore Analisi", f"Si è verificato un errore:\n{err_msg}")

    def closeEvent(self, event) -> None:
        """Intercepts window close while thread is active."""
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Analisi in Corso",
                "L'analisi è ancora in corso. Desideri interromperla prima di chiudere?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.thread.cancel()
                self.thread.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
