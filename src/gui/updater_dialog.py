"""
Musicat Update Notification Dialog.

Presents available update information, release notes markdown viewer,
and one-click in-app stream downloader with real-time progress bar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.core.i18n import I18n, _t
from src.core.logger import MusicatLogger
from src.core.path_resolver import PathResolver
from src.core.settings import SettingsManager
from src.core.updater import UpdateDownloadWorker, UpdateInfo


class UpdateNotificationDialog(QDialog):
    """Non-blocking modal/window displaying update details and integrated downloader."""

    def __init__(self, update_info: UpdateInfo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.update_info = update_info
        self.download_worker: Optional[UpdateDownloadWorker] = None
        self._downloaded_file_path: Optional[str] = None

        self.setWindowTitle(_t("updater_dialog_title", "Aggiornamento Disponibile — Musicat"))
        self.resize(640, 520)
        self.setMinimumSize(540, 420)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header Card
        header_frame = QFrame()
        header_frame.setObjectName("updaterHeaderCard")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(6)

        title_lbl = QLabel(_t("updater_lbl_new_version", "È disponibile una nuova versione di Musicat!"))
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        title_lbl.setObjectName("updaterTitle")
        header_layout.addWidget(title_lbl)

        version_info_str = _t(
            "updater_lbl_current_version",
            "Versione corrente: v{current}  ➔  Nuova versione: v{remote}",
            current=self.update_info.local_version,
            remote=self.update_info.remote_version,
        )
        self.lbl_version_info = QLabel(version_info_str)
        self.lbl_version_info.setObjectName("updaterVersionInfo")
        header_layout.addWidget(self.lbl_version_info)

        size_str = f"{self.update_info.asset_size_mb:.1f}" if self.update_info.asset_size else "--"
        asset_info_str = _t(
            "updater_lbl_asset_info",
            "Pacchetto rilevato: {asset} ({size} MB)",
            asset=self.update_info.asset_name,
            size=size_str,
        )
        self.lbl_asset_info = QLabel(asset_info_str)
        self.lbl_asset_info.setObjectName("updaterAssetInfo")
        header_layout.addWidget(self.lbl_asset_info)

        layout.addWidget(header_frame)

        # 2. Release Notes Area
        lbl_notes_title = QLabel(_t("updater_lbl_release_notes", "Note di Rilascio:"))
        notes_font = QFont()
        notes_font.setBold(True)
        lbl_notes_title.setFont(notes_font)
        layout.addWidget(lbl_notes_title)

        self.txt_notes = QTextBrowser()
        self.txt_notes.setOpenExternalLinks(True)
        # Render markdown release notes cleanly
        self.txt_notes.setMarkdown(self.update_info.release_notes or "Nessuna nota di rilascio fornita.")
        layout.addWidget(self.txt_notes)

        # 3. Download Progress Area
        self.progress_container = QWidget()
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(22)
        progress_layout.addWidget(self.progress_bar)

        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.lbl_progress_status)

        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)

        # 4. Action Buttons Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_browser = QPushButton(_t("updater_btn_open_browser", "🌐 Apri nel Browser"))
        self.btn_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browser.clicked.connect(self._on_open_browser)
        btn_bar.addWidget(self.btn_browser)

        btn_bar.addStretch()

        self.btn_later = QPushButton(_t("updater_btn_remind_later", "Ricordamelo più tardi"))
        self.btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_later.clicked.connect(self.close)
        btn_bar.addWidget(self.btn_later)

        self.btn_action = QPushButton(_t("updater_btn_download_now", "🚀 Scarica Ora"))
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setObjectName("updaterActionBtn")
        self.btn_action.clicked.connect(self._on_action_clicked)
        btn_bar.addWidget(self.btn_action)

        layout.addLayout(btn_bar)

    def _apply_theme(self) -> None:
        """Adapts styling according to the active application theme."""
        theme_id = SettingsManager.get_instance().get("ui", "theme", "light")
        is_light = "light" in theme_id

        if is_light:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8f9fa;
                    color: #212529;
                }
                #updaterHeaderCard {
                    background-color: #ffffff;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                }
                #updaterTitle {
                    color: #0d6efd;
                }
                #updaterVersionInfo {
                    color: #495057;
                    font-size: 13px;
                    font-weight: 600;
                }
                #updaterAssetInfo {
                    color: #6c757d;
                    font-size: 12px;
                }
                QTextBrowser {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 6px;
                    padding: 8px;
                    color: #212529;
                    font-size: 13px;
                }
                QProgressBar {
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #e9ecef;
                    color: #212529;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #0d6efd;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 5px;
                    padding: 7px 16px;
                    font-size: 13px;
                    color: #212529;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    border-color: #0d6efd;
                    color: #0d6efd;
                }
                #updaterActionBtn {
                    background-color: #0d6efd;
                    color: #ffffff;
                    border: none;
                    font-weight: bold;
                }
                #updaterActionBtn:hover {
                    background-color: #0b5ed7;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #121316;
                    color: #e0e2ec;
                }
                #updaterHeaderCard {
                    background-color: #1a1c24;
                    border: 1px solid #2c303f;
                    border-radius: 8px;
                }
                #updaterTitle {
                    color: #00d2ff;
                }
                #updaterVersionInfo {
                    color: #9da3b5;
                    font-size: 13px;
                    font-weight: 600;
                }
                #updaterAssetInfo {
                    color: #717789;
                    font-size: 12px;
                }
                QTextBrowser {
                    background-color: #16181f;
                    border: 1px solid #2a2d3a;
                    border-radius: 6px;
                    padding: 8px;
                    color: #e0e2ec;
                    font-size: 13px;
                }
                QProgressBar {
                    border: 1px solid #2a2d3a;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #1a1c24;
                    color: #ffffff;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #00d2ff;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #1a1c24;
                    border: 1px solid #2c303f;
                    border-radius: 5px;
                    padding: 7px 16px;
                    font-size: 13px;
                    color: #e0e2ec;
                }
                QPushButton:hover {
                    background-color: #242731;
                    border-color: #00d2ff;
                    color: #00d2ff;
                }
                #updaterActionBtn {
                    background-color: #00d2ff;
                    color: #0b0c10;
                    border: none;
                    font-weight: bold;
                }
                #updaterActionBtn:hover {
                    background-color: #33dcff;
                }
            """)

    def _on_open_browser(self) -> None:
        """Opens GitHub Releases web page in default system browser."""
        target_url = self.update_info.html_url or "https://github.com/IlRed89/Musicat/releases"
        QDesktopServices.openUrl(QUrl(target_url))

    def _on_action_clicked(self) -> None:
        """Handles download start, cancellation, or opening destination folder."""
        # Case 1: Download already completed -> Open file in file manager
        if self._downloaded_file_path and Path(self._downloaded_file_path).exists():
            PathResolver.show_in_file_manager(self._downloaded_file_path)
            return

        # Case 2: Currently downloading -> Request cancellation
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.requestInterruption()
            self.btn_action.setEnabled(False)
            self.lbl_progress_status.setText("Annullamento download...")
            return

        # Case 3: Start download
        download_url = self.update_info.download_url
        if not download_url:
            self._on_open_browser()
            return

        # Resolve system Downloads directory
        downloads_dir_str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        if downloads_dir_str and Path(downloads_dir_str).exists():
            dest_dir = Path(downloads_dir_str)
        else:
            dest_dir = Path.home() / "Downloads"
            dest_dir.mkdir(parents=True, exist_ok=True)

        dest_file = dest_dir / self.update_info.asset_name

        self.progress_container.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setText("Connessione a GitHub...")
        self.btn_action.setText(_t("updater_btn_cancel_download", "✕ Annulla Download"))
        self.btn_later.setEnabled(False)

        self.download_worker = UpdateDownloadWorker(
            download_url=download_url,
            destination_path=dest_file,
            expected_size=self.update_info.asset_size,
            parent=self,
        )
        self.download_worker.download_progress.connect(self._on_download_progress)
        self.download_worker.download_finished.connect(self._on_download_finished)
        self.download_worker.download_failed.connect(self._on_download_failed)
        self.download_worker.start()

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        """Updates progress bar and byte counters."""
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            cur_mb = downloaded / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            self.lbl_progress_status.setText(f"{cur_mb:.1f} MB / {tot_mb:.1f} MB ({pct}%)")
        else:
            cur_mb = downloaded / (1024 * 1024)
            self.lbl_progress_status.setText(f"{cur_mb:.1f} MB scaricati...")

    def _on_download_finished(self, dest_path: str) -> None:
        """Notifies user upon completion, highlights file in Explorer/Finder."""
        self._downloaded_file_path = dest_path
        self.progress_bar.setValue(100)
        self.lbl_progress_status.setText(
            _t("updater_download_complete", "Download completato! Il file è pronto nella cartella Download.")
        )
        self.lbl_progress_status.setStyleSheet("color: #28a745; font-weight: bold;")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("📂 Mostra nel File Manager")
        self.btn_later.setText("Chiudi")
        self.btn_later.setEnabled(True)

        # Highlight file in native OS file explorer
        try:
            PathResolver.show_in_file_manager(dest_path)
        except Exception as exc:
            MusicatLogger.warning("UPDATER", f"Could not highlight downloaded file: {exc}")

    def _on_download_failed(self, error_msg: str) -> None:
        """Handles download failure or cancellation."""
        self.btn_action.setEnabled(True)
        self.btn_action.setText(_t("updater_btn_download_now", "🚀 Scarica Ora"))
        self.btn_later.setEnabled(True)
        self.lbl_progress_status.setText(
            _t("updater_download_error", "Errore durante il download: {error}", error=error_msg)
        )
        self.lbl_progress_status.setStyleSheet("color: #dc3545; font-weight: bold;")

    def closeEvent(self, event) -> None:
        """Ensures worker thread is safely interrupted when dialog is closed."""
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.requestInterruption()
            self.download_worker.wait(1500)
        event.accept()
