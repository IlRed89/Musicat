"""
Audio Quality & Loudness Diagnosis Dialog and Visual Gauges for Musicat.

Provides:
- Visual True Peak / LUFS meter bar widget
- QualityDiagnosisDialog for single track inspection and normalization
- BatchQualityDialog for mass library analysis and ReplayGain / loudnorm processing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal, QThread
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.db import Database
from src.plugins.quality_analyzer.analyzer import AcousticQualityAnalyzer, QualityReport
from src.plugins.quality_analyzer.normalizer import VolumeNormalizer, NormalizationResult


class LoudnessMeterBar(QWidget):
    """Custom-painted horizontal VU/Loudness bar widget showing LUFS and True Peak."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setMinimumWidth(160)
        self._lufs: float = -70.0
        self._true_peak: float = -100.0
        self._status: str = "OK"

    def set_metrics(self, lufs: float, true_peak: float, status: str = "OK") -> None:
        """Updates displayed loudness and peak values."""
        self._lufs = lufs
        self._true_peak = true_peak
        self._status = status
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background track
        painter.fillRect(0, 0, w, h, QColor("#12141a"))
        painter.setPen(QPen(QColor("#272a38"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        # Map LUFS [-40 to 0] to fraction [0.0 to 1.0]
        clamped_lufs = max(-40.0, min(0.0, self._lufs))
        lufs_ratio = (clamped_lufs + 40.0) / 40.0
        fill_w = int(lufs_ratio * (w - 2))

        if fill_w > 0:
            # Gradient: Cyan/Green -> Yellow -> Red
            grad = QLinearGradient(1, 0, w - 1, 0)
            grad.setColorAt(0.0, QColor("#00d2ff"))
            grad.setColorAt(0.65, QColor("#10b981"))
            grad.setColorAt(0.85, QColor("#f59e0b"))
            grad.setColorAt(1.0, QColor("#ef4444"))

            painter.fillRect(1, 1, fill_w, h - 2, grad)

        # True Peak marker line
        if self._true_peak > -40.0:
            clamped_tp = max(-40.0, min(6.0, self._true_peak))
            tp_ratio = (clamped_tp + 40.0) / 46.0
            tp_x = int(tp_ratio * (w - 2)) + 1
            tp_color = QColor("#ef4444") if self._true_peak > 0.0 else QColor("#ffffff")
            painter.setPen(QPen(tp_color, 2))
            painter.drawLine(tp_x, 1, tp_x, h - 2)

        # Text Overlay
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        text = f"{self._lufs:.1f} LUFS  |  TP: {self._true_peak:+.1f} dBTP"
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(4, 0, w - 8, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)


class QualityDiagnosisDialog(QDialog):
    """Detailed modal diagnosis and loudness normalization dialog for single tracks."""

    normalization_applied = Signal(str)  # Emits filepath when normalized

    def __init__(
        self,
        filepath: str,
        db: Optional[Database] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.filepath = filepath
        self.db = db
        self.report: Optional[QualityReport] = None
        self.normalizer = VolumeNormalizer(db=self.db)

        self.setWindowTitle(f"🔊 Audio Quality & Loudness Normalizer — {Path(filepath).name}")
        self.resize(680, 520)
        self.setStyleSheet("""
            QDialog { background-color: #111318; color: #cbd5e1; }
            QLabel { color: #cbd5e1; font-size: 12px; }
            QGroupBox {
                border: 1px solid #232838;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #00d2ff;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)

        self._init_ui()
        self._run_analysis()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        # Header Info
        header = QLabel(f"<b>File:</b> {Path(self.filepath).name}")
        header.setStyleSheet("font-size: 13px; color: #ffffff;")
        layout.addWidget(header)

        # Meter Bar
        self.meter_bar = LoudnessMeterBar(self)
        layout.addWidget(self.meter_bar)

        # 1. Diagnostics Group
        grp_diag = QGroupBox("📊 Metriche di Conformità EBU R128 / ITU-R BS.1770-4")
        diag_layout = QVBoxLayout(grp_diag)
        diag_layout.setSpacing(8)

        self.lbl_lufs = QLabel("Integrated Loudness: Calcolo in corso...")
        self.lbl_tp = QLabel("True Peak: Calcolo in corso...")
        self.lbl_lra = QLabel("Loudness Range (LRA): Calcolo in corso...")
        self.lbl_status = QLabel("Stato Qualità: Calcolo in corso...")
        self.lbl_gain_needed = QLabel("Guadagno Necessario: ...")

        diag_layout.addWidget(self.lbl_lufs)
        diag_layout.addWidget(self.lbl_tp)
        diag_layout.addWidget(self.lbl_lra)
        diag_layout.addWidget(self.lbl_status)
        diag_layout.addWidget(self.lbl_gain_needed)
        layout.addWidget(grp_diag)

        # 2. Strategy Selector Group
        grp_action = QGroupBox("⚡ Strategia di Correzione & Normalizzazione")
        act_layout = QVBoxLayout(grp_action)
        act_layout.setSpacing(10)

        # Target LUFS selector
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target Loudness:"))
        self.cmb_target = QComboBox()
        self.cmb_target.addItem("-10.0 LUFS (DJ Club Standard)", -10.0)
        self.cmb_target.addItem("-14.0 LUFS (Spotify / AES Streaming)", -14.0)
        self.cmb_target.addItem("-16.0 LUFS (Apple Music / Podcast)", -16.0)
        self.cmb_target.addItem("-23.0 LUFS (EBU R128 Broadcast)", -23.0)
        self.cmb_target.currentIndexChanged.connect(self._on_target_changed)
        target_row.addWidget(self.cmb_target)
        target_row.addStretch()
        act_layout.addLayout(target_row)

        # Strategy Radio Buttons
        self.rad_replaygain = QRadioButton("🏷️ ReplayGain Non Distruttivo (Scrive tag Sound Check / Gain Offset nei metadati)")
        self.rad_replaygain.setChecked(True)
        self.rad_replaygain.setToolTip("Conserva il PCM originale senza toccare lo stream audio. Il player applica il guadagno al volo.")

        self.rad_loudnorm = QRadioButton("🛠️ Normalizzazione Fisica (De-Clipping & Re-encoding Two-Pass FFmpeg loudnorm)")
        self.rad_loudnorm.setToolTip("Ricalcola l'audio applicando True Peak Limiter a -1.0 dBTP e target LUFS.")

        act_layout.addWidget(self.rad_replaygain)
        act_layout.addWidget(self.rad_loudnorm)

        # Sub-options for Physical Normalization
        self.frame_loudnorm_opts = QFrame()
        loud_opts_layout = QVBoxLayout(self.frame_loudnorm_opts)
        loud_opts_layout.setContentsMargins(20, 0, 0, 0)
        loud_opts_layout.setSpacing(4)

        self.chk_save_fixed = QCheckBox("Salva con suffisso '_fixed.ext' (lascia intatto il file originale)")
        self.chk_save_fixed.setChecked(True)
        self.chk_backup_original = QCheckBox("Crea copia di sicurezza in cartella '_original/'")
        self.chk_backup_original.setChecked(True)

        loud_opts_layout.addWidget(self.chk_save_fixed)
        loud_opts_layout.addWidget(self.chk_backup_original)
        act_layout.addWidget(self.frame_loudnorm_opts)

        self.rad_replaygain.toggled.connect(lambda checked: self.frame_loudnorm_opts.setEnabled(not checked))
        self.frame_loudnorm_opts.setEnabled(False)

        layout.addWidget(grp_action)

        # Action Buttons
        btn_box = QHBoxLayout()
        self.btn_apply = QPushButton("🚀 Esegui Correzione / Normalizza")
        self.btn_apply.setStyleSheet("background-color: #0077b6; font-weight: bold; padding: 8px 16px; border-radius: 4px;")
        self.btn_apply.clicked.connect(self._on_apply_normalization)

        btn_close = QPushButton("Chiudi")
        btn_close.clicked.connect(self.close)

        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

    def _run_analysis(self) -> None:
        """Executes EBU R128 acoustic quality analysis."""
        try:
            target_lufs = self.cmb_target.currentData()
            self.report = AcousticQualityAnalyzer.analyze_file(self.filepath, target_lufs=target_lufs)

            # Update UI labels
            self.lbl_lufs.setText(f"<b>Integrated Loudness:</b> {self.report.integrated_lufs:.2f} LUFS")
            tp_color = "#ef4444" if self.report.true_peak_dbtp > 0.0 else "#10b981"
            self.lbl_tp.setText(f"<b>True Peak:</b> <span style='color: {tp_color};'>{self.report.true_peak_dbtp:+.2f} dBTP</span> (Sample Peak: {self.report.sample_peak_dbfs:+.2f} dBFS)")
            self.lbl_lra.setText(f"<b>Loudness Range (LRA):</b> {self.report.loudness_range_lra:.2f} LU")

            status_html = ""
            if self.report.status == "CLIPPING":
                status_html = "<span style='color: #ef4444; font-weight: bold;'>🔴 DISTORSIONE / CLIPPING RILEVATO (True Peak > 0 dBTP)</span>"
            elif self.report.status == "LOW_VOLUME":
                status_html = "<span style='color: #f59e0b; font-weight: bold;'>🟡 LIVELLO BASSO (< -18 LUFS)</span>"
            elif self.report.status == "BRICKWALL":
                status_html = "<span style='color: #f97316; font-weight: bold;'>🟠 IPERCOMPRESSIONE BRICKWALL (LRA < 3 LU)</span>"
            else:
                status_html = "<span style='color: #10b981; font-weight: bold;'>🟢 CONFORME (Ottima Dinamica & Nessun Clipping)</span>"

            self.lbl_status.setText(f"<b>Stato Qualità:</b> {status_html}")

            gain_sign = "+" if self.report.suggested_gain_db > 0 else ""
            self.lbl_gain_needed.setText(f"<b>Guadagno Raccomandato:</b> {gain_sign}{self.report.suggested_gain_db:.2f} dB (per raggiungere {target_lufs:.1f} LUFS)")

            self.meter_bar.set_metrics(self.report.integrated_lufs, self.report.true_peak_dbtp, self.report.status)

        except Exception as exc:
            self.lbl_status.setText(f"<span style='color: #ef4444;'>Errore durante l'analisi: {exc}</span>")

    def _on_target_changed(self) -> None:
        if self.report:
            target_lufs = self.cmb_target.currentData()
            diff = target_lufs - self.report.integrated_lufs
            sign = "+" if diff > 0 else ""
            self.lbl_gain_needed.setText(f"<b>Guadagno Raccomandato:</b> {sign}{diff:.2f} dB (per raggiungere {target_lufs:.1f} LUFS)")

    def _on_apply_normalization(self) -> None:
        """Executes normalization according to chosen strategy."""
        target_lufs = self.cmb_target.currentData()

        if self.rad_replaygain.isChecked():
            res = self.normalizer.apply_replaygain(self.filepath, target_lufs=target_lufs, report=self.report)
            if res.success:
                QMessageBox.information(
                    self,
                    "ReplayGain Applicato",
                    f"Metadati ReplayGain scritti con successo nel file:\n"
                    f"• Gain Offset: {res.gain_applied_db:+.2f} dB\n"
                    f"• Target: {target_lufs:.1f} LUFS\n\n"
                    f"Il player libVLC regolerà automaticamente il volume durante l'ascolto.",
                )
                self.normalization_applied.emit(self.filepath)
                self.accept()
            else:
                QMessageBox.critical(self, "Errore ReplayGain", f"Impossibile applicare ReplayGain:\n{res.error_message}")

        else:
            save_as_fixed = self.chk_save_fixed.isChecked()
            create_backup = self.chk_backup_original.isChecked()

            res = self.normalizer.apply_physical_loudnorm(
                self.filepath,
                target_lufs=target_lufs,
                save_as_fixed=save_as_fixed,
                create_backup=create_backup,
            )
            if res.success:
                msg = f"Normalizzazione fisica completata!\nFile salvato: {res.output_filepath}"
                if res.backup_path:
                    msg += f"\nBackup originale creato in: {res.backup_path}"
                QMessageBox.information(self, "Normalizzazione Completata", msg)
                self.normalization_applied.emit(res.output_filepath)
                self.accept()
            else:
                QMessageBox.critical(self, "Errore Normalizzazione", f"Impossibile normalizzare il file:\n{res.error_message}")


class BatchQualityWorker(QThread):
    """Background worker for mass library audio quality analysis."""

    progress = Signal(int, int, str)  # current, total, name
    finished = Signal(list)

    def __init__(self, tracks: List[Dict[str, Any]], target_lufs: float = -10.0) -> None:
        super().__init__()
        self.tracks = tracks
        self.target_lufs = target_lufs
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        reports = []
        total = len(self.tracks)
        for idx, tr in enumerate(self.tracks):
            if self._is_cancelled:
                break
            fp = tr.get("filepath", "")
            if not fp or not Path(fp).exists():
                continue

            try:
                rep = AcousticQualityAnalyzer.analyze_file(fp, target_lufs=self.target_lufs)
                reports.append(rep)
            except Exception:
                pass

            self.progress.emit(idx + 1, total, Path(fp).name)

        self.finished.emit(reports)
