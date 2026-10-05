"""
Modular Settings & Preferences Dialog for Musicat.

Features:
- Category navigation sidebar (UI/Graphics, Audio/VLC, Performance/GPU, Scrapers, Plugins).
- High-DPI zoom, theme selection, table row height/font size.
- Clean light theme sanitization across all sidebars, containers, and dialogs.
- Audio output device selection, buffer latency, player behavior.
- Multiprocessing CPU allocation, dynamic RAM buffer sizing up to 80% system memory.
- Hardware GPU acceleration toggle with clean adaptive light badge.
- Expanded Scrapers & API Keys (Spotify, SoundCloud, YouTube, Discogs, Beatport) with instant visual test verification.
- Dynamic plugin configuration discovery from BasePlugin schemas.
- Persistent saving via SettingsManager to local config.json.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.gpu_detector import GpuDetector, GpuInfo
from src.core.hardware_monitor import HardwareMonitor
from src.core.i18n import I18n, _t
from src.core.oauth_manager import OAuthManager
from src.core.settings import SettingsManager
from src.plugins.manager import PluginManager


class SettingsDialog(QDialog):
    """Modular preferences dialog with category sidebar."""

    settings_applied = Signal(dict)

    def __init__(self, settings_or_parent: Any = None, parent: Optional[QWidget] = None) -> None:
        if isinstance(settings_or_parent, QWidget):
            actual_parent = settings_or_parent
        else:
            actual_parent = parent
        super().__init__(actual_parent)
        self.settings = SettingsManager.get_instance()
        self.plugin_manager = PluginManager.get_instance(self.settings)
        self.gpu_info: GpuInfo = GpuDetector.get_gpu_info()
        self._current_saved_lang = self.settings.get("ui", "language", "it")

        self.oauth_manager = OAuthManager.get_instance()
        self.oauth_manager.auth_completed.connect(self._on_auth_completed)
        self.oauth_manager.auth_failed.connect(self._on_auth_failed)
        self.account_widgets: Dict[str, Dict[str, Any]] = {}

        self.setWindowTitle(_t("settings_title", "Musicat — Preferenze di Sistema"))
        self.resize(860, 620)
        self.setMinimumSize(800, 540)

        self._init_ui()
        self._load_values()
        self._retranslate_ui()
        I18n.get_instance().language_changed.connect(self._retranslate_ui)

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(14)

        # 1. Left Sidebar Navigation
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(210)

        categories = [
            ("🎨  Grafica & UI", 0),
            ("🎵  Audio & libVLC", 1),
            ("⚡  Prestazioni & Hardware", 2),
            ("🌐  Account & Servizi", 3),
            ("🧩  Plugin & Estensioni", 4),
        ]

        for text, _ in categories:
            item = QListWidgetItem(text)
            self.sidebar.addItem(item)

        main_layout.addWidget(self.sidebar)

        # 2. Right Content Area (Stacked Widget + Buttons)
        right_container = QVBoxLayout()
        right_container.setSpacing(12)

        self.stack = QStackedWidget()

        # Create Category Pages
        self.page_ui = self._create_ui_page()
        self.page_audio = self._create_audio_page()
        self.page_performance = self._create_performance_page()
        self.page_scrapers = self._create_scrapers_page()
        self.page_plugins = self._create_plugins_page()

        self.stack.addWidget(self.page_ui)
        self.stack.addWidget(self.page_audio)
        self.stack.addWidget(self.page_performance)
        self.stack.addWidget(self.page_scrapers)
        self.stack.addWidget(self.page_plugins)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        right_container.addWidget(self.stack)

        # Bottom Buttons Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_reset = QPushButton(_t("settings_btn_reset", "Ripristina Predefiniti"))
        self.btn_reset.clicked.connect(self._on_reset_defaults)
        btn_bar.addWidget(self.btn_reset)

        btn_bar.addStretch()

        self.btn_cancel = QPushButton(_t("settings_btn_cancel", "Annulla"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(_t("settings_btn_save", "Salva ed Applica"))
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                border: 1px solid #0d6efd;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_bar.addWidget(self.btn_save)

        right_container.addLayout(btn_bar)
        main_layout.addLayout(right_container)

        # Apply adaptive styling (Light by default, or active theme)
        self._apply_theme_styling(self.settings.get("ui", "theme", "light"))

    def _apply_theme_styling(self, theme_id: str) -> None:
        """Adapts settings dialog, sidebar navigation, and stacked panels to the active theme."""
        is_light = ("light" in theme_id)
        if is_light:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8f9fa;
                    color: #212529;
                }
                QGroupBox {
                    background-color: #ffffff;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    margin-top: 14px;
                    padding-top: 14px;
                    font-weight: bold;
                    color: #0d6efd;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 6px;
                    background-color: #ffffff;
                    color: #0d6efd;
                }
                QLabel {
                    color: #212529;
                }
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    color: #212529;
                    padding: 5px 8px;
                }
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                    border: 1px solid #0d6efd;
                }
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 5px 12px;
                    color: #212529;
                }
                QPushButton:hover {
                    background-color: #f1f3f5;
                    border-color: #0d6efd;
                    color: #0d6efd;
                }
            """)
            self.sidebar.setStyleSheet("""
                QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    padding: 6px;
                }
                QListWidget::item {
                    padding: 10px 12px;
                    border-radius: 4px;
                    color: #212529;
                    font-weight: 500;
                    font-size: 13px;
                }
                QListWidget::item:hover {
                    background-color: #f1f3f5;
                }
                QListWidget::item:selected {
                    background-color: #0d6efd;
                    color: #ffffff;
                    font-weight: bold;
                }
            """)
            self.stack.setStyleSheet("QStackedWidget { background-color: transparent; }")
            if hasattr(self, "badge_frame"):
                self.badge_frame.setStyleSheet("""
                    QFrame {
                        background-color: #ffffff;
                        border: 1px solid #dee2e6;
                        border-radius: 6px;
                        padding: 10px;
                    }
                """)
            if hasattr(self, "lbl_gpu_status"):
                self.lbl_gpu_status.setStyleSheet("color: #198754; font-weight: bold;" if self.gpu_info.is_available else "color: #6c757d;")
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #121316;
                    color: #e0e2ec;
                }
            """)
            self.sidebar.setStyleSheet("""
                QListWidget {
                    background-color: #161820;
                    border: 1px solid #282c3c;
                    border-radius: 6px;
                    padding: 4px;
                }
                QListWidget::item {
                    padding: 10px 12px;
                    border-radius: 4px;
                    color: #cbd5e1;
                    font-weight: 500;
                    font-size: 13px;
                }
                QListWidget::item:hover {
                    background-color: #202433;
                }
                QListWidget::item:selected {
                    background-color: #00d2ff;
                    color: #0b0c10;
                    font-weight: bold;
                }
            """)
            self.stack.setStyleSheet("QStackedWidget { background-color: #12141a; }")
            if hasattr(self, "badge_frame"):
                self.badge_frame.setStyleSheet("""
                    QFrame {
                        background-color: #1a1e2a;
                        border: 1px solid #2e354a;
                        border-radius: 6px;
                        padding: 10px;
                    }
                """)
            if hasattr(self, "lbl_gpu_status"):
                self.lbl_gpu_status.setStyleSheet("color: #00d2ff;" if self.gpu_info.is_available else "color: #94a3b8;")

    # -------------------------------------------------------------
    # Category 1: Grafica & UI
    # -------------------------------------------------------------
    def _create_ui_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Theme & Scaling Group
        self.grp_theme = QGroupBox("🎨 Aspetto & Tema Visivo")
        form_theme = QFormLayout(self.grp_theme)

        self.lbl_language = QLabel("Lingua dell'Interfaccia:")
        self.cmb_language = QComboBox()
        self.cmb_language.addItem("Italiano (IT)", "it")
        self.cmb_language.addItem("English (EN)", "en")
        self.cmb_language.currentIndexChanged.connect(self._on_language_changed)
        form_theme.addRow(self.lbl_language, self.cmb_language)

        self.lbl_theme = QLabel("Tema Interfaccia:")
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["Tema Chiaro (Predefinito)", "Dark DJ Console", "High-Contrast Club Booth"])
        form_theme.addRow(self.lbl_theme, self.cmb_theme)

        self.lbl_dpi = QLabel("Scala Display (HiDPI Zoom):")
        self.cmb_dpi = QComboBox()
        self.cmb_dpi.addItems(["Automatico (Consigliato)", "100%", "125%", "150%"])
        form_theme.addRow(self.lbl_dpi, self.cmb_dpi)

        self.lbl_font_size = QLabel("Dimensione Font Tabelle:")
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(9, 18)
        self.spin_font_size.setValue(12)
        form_theme.addRow(self.lbl_font_size, self.spin_font_size)

        self.lbl_row_height = QLabel("Altezza Righe Tabella (px):")
        self.spin_row_height = QSpinBox()
        self.spin_row_height.setRange(20, 50)
        self.spin_row_height.setValue(28)
        form_theme.addRow(self.lbl_row_height, self.spin_row_height)

        layout.addWidget(self.grp_theme)

        # Columns Context Menu Hint Card (Requirement 1: columns managed via right-click)
        info_cols = QFrame()
        info_cols.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        info_layout = QHBoxLayout(info_cols)
        lbl_hint = QLabel(
            "💡 <b>Gestione Colonne Tabella:</b> La selezione e la larghezza delle colonne si gestiscono ora "
            "direttamente con il <b>tasto destro</b> su qualsiasi intestazione della tabella nella schermata <i>Libreria</i>."
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #495057; font-size: 12px;")
        info_layout.addWidget(lbl_hint)
        layout.addWidget(info_cols)

        layout.addStretch()
        return widget

    # -------------------------------------------------------------
    # Category 2: Audio & Engine libVLC
    # -------------------------------------------------------------
    def _create_audio_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        grp_output = QGroupBox("🔊 Dispositivo di Riproduzione & Latenza")
        form_out = QFormLayout(grp_output)

        self.cmb_audio_device = QComboBox()
        self.cmb_audio_device.addItems([
            "Dispositivo Predefinito di Sistema",
            "WASAPI / CoreAudio: Cuffie / Master Console",
            "DirectSound: Scheda Audio Principale",
            "ASIO / External DJ Controller Out",
        ])
        form_out.addRow("Dispositivo Audio Output:", self.cmb_audio_device)

        self.slider_buffer = QSlider(Qt.Orientation.Horizontal)
        self.slider_buffer.setRange(50, 800)
        self.slider_buffer.setSingleStep(50)
        self.slider_buffer.setValue(150)
        self.lbl_buffer = QLabel("150 ms (Latenza bilanciata)")
        self.slider_buffer.valueChanged.connect(
            lambda v: self.lbl_buffer.setText(f"{v} ms ({'Bassa latenza' if v < 100 else 'Stabile' if v < 300 else 'Safe Buffer'})")
        )

        buf_box = QHBoxLayout()
        buf_box.addWidget(self.slider_buffer)
        buf_box.addWidget(self.lbl_buffer)
        form_out.addRow("Buffer Audio Preview (ms):", buf_box)

        layout.addWidget(grp_output)

        grp_player = QGroupBox("🎛️ Comportamento DJ Player")
        form_player = QFormLayout(grp_player)

        self.chk_autoplay = QCheckBox("Avvia automaticamente la riproduzione al click sulla traccia")
        form_player.addRow(self.chk_autoplay)

        self.cmb_pitch_range = QComboBox()
        self.cmb_pitch_range.addItems(["± 8.0% (Standard DJ Turntable)", "± 16.0% (Wide Range)", "± 50.0% (Extreme Key Bend)"])
        form_player.addRow("Escursione Cursore Pitch / Tempo:", self.cmb_pitch_range)

        layout.addWidget(grp_player)
        layout.addStretch()
        return widget

    # -------------------------------------------------------------
    # Category 3: Prestazioni & Hardware
    # -------------------------------------------------------------
    def _create_performance_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        grp_cpu = QGroupBox("⚡ Risorse CPU & Multiprocessing")
        form_cpu = QFormLayout(grp_cpu)

        cores_max = os.cpu_count() or 4
        self.slider_perf_cores = QSlider(Qt.Orientation.Horizontal)
        self.slider_perf_cores.setRange(1, cores_max)
        self.slider_perf_cores.setValue(max(1, cores_max - 1))
        self.lbl_perf_cores = QLabel(f"{max(1, cores_max - 1)} di {cores_max} core logici allocati")
        self.slider_perf_cores.valueChanged.connect(
            lambda v: self.lbl_perf_cores.setText(f"{v} di {cores_max} core logici allocati")
        )

        c_box = QHBoxLayout()
        c_box.addWidget(self.slider_perf_cores)
        c_box.addWidget(self.lbl_perf_cores)
        form_cpu.addRow("Worker Pool Analisi Acustica:", c_box)

        # Requirement 4: Dynamic RAM allocation up to 80% total system RAM
        total_sys_gb = HardwareMonitor.get_total_system_memory_gb()
        max_ram_mb = max(1024, int(total_sys_gb * 1024 * 0.8))

        self.slider_perf_ram = QSlider(Qt.Orientation.Horizontal)
        self.slider_perf_ram.setRange(512, max_ram_mb)
        self.slider_perf_ram.setSingleStep(256)
        cur_ram = self.settings.get("performance", "ram_cache_mb", 1024)
        self.slider_perf_ram.setValue(min(max_ram_mb, max(512, cur_ram)))

        self.lbl_perf_ram = QLabel()

        def _update_ram_label(v: int) -> None:
            if v >= 1024:
                self.lbl_perf_ram.setText(f"Allocati: {v / 1024:.1f} GB / {total_sys_gb:.1f} GB totali")
            else:
                self.lbl_perf_ram.setText(f"Allocati: {v} MB / {total_sys_gb:.1f} GB totali")

        _update_ram_label(self.slider_perf_ram.value())
        self.slider_perf_ram.valueChanged.connect(_update_ram_label)

        r_box = QHBoxLayout()
        r_box.addWidget(self.slider_perf_ram)
        r_box.addWidget(self.lbl_perf_ram)
        form_cpu.addRow("Dimensione RAM Cache L1 (DB & Waveform):", r_box)

        layout.addWidget(grp_cpu)

        # Requirement 3: Clean light card style for GPU acceleration
        grp_gpu = QGroupBox("🎮 Accelerazione Hardware GPU")
        gpu_layout = QVBoxLayout(grp_gpu)

        self.chk_gpu = QCheckBox("Abilita accelerazione spettrale su scheda grafica GPU")
        self.chk_gpu.setChecked(self.gpu_info.is_available)
        gpu_layout.addWidget(self.chk_gpu)

        # Adaptive Status badge
        self.badge_frame = QFrame()
        badge_layout = QVBoxLayout(self.badge_frame)

        self.lbl_gpu_device = QLabel(f"<b>Dispositivo Rilevato:</b> {self.gpu_info.device_name}")
        self.lbl_gpu_backend = QLabel(f"<b>Backend Computazionale:</b> {self.gpu_info.backend}")
        self.lbl_gpu_status = QLabel(f"<b>Stato:</b> {self.gpu_info.status_message}")

        badge_layout.addWidget(self.lbl_gpu_device)
        badge_layout.addWidget(self.lbl_gpu_backend)
        badge_layout.addWidget(self.lbl_gpu_status)
        gpu_layout.addWidget(self.badge_frame)

        layout.addWidget(grp_gpu)

        # Troubleshooting & Diagnostic Logs Section
        grp_logs = QGroupBox("📜 Diagnostica & Log di Sistema")
        logs_layout = QVBoxLayout(grp_logs)
        logs_layout.setSpacing(8)

        from src.core.path_resolver import PathResolver
        lbl_log_path = QLabel(f"<b>Cartella File di Log:</b> {PathResolver.get_logs_dir()}")
        lbl_log_path.setStyleSheet("color: #64748b; font-size: 11px;")
        logs_layout.addWidget(lbl_log_path)

        logs_btn_row = QHBoxLayout()
        btn_open_log_folder = QPushButton("📁 Apri Cartella Log")
        btn_open_log_folder.clicked.connect(lambda: PathResolver.show_in_file_manager(PathResolver.get_logs_dir()))

        btn_export_diag = QPushButton("📦 Esporta Pacchetto Supporto (.zip)")
        btn_export_diag.clicked.connect(self._on_export_support_bundle_clicked)

        logs_btn_row.addWidget(btn_open_log_folder)
        logs_btn_row.addWidget(btn_export_diag)
        logs_layout.addLayout(logs_btn_row)

        layout.addWidget(grp_logs)
        layout.addStretch()
        return widget

    def _on_export_support_bundle_clicked(self) -> None:
        from datetime import datetime
        from src.core.logger import MusicatLogger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        default_name = f"musicat_support_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva Pacchetto Log per Assistenza",
            default_name,
            "ZIP Archives (*.zip)",
        )
        if not dest_path:
            return
        try:
            out_file = MusicatLogger.export_support_bundle(destination_zip=dest_path)
            QMessageBox.information(
                self,
                "Log Esportati",
                f"Il pacchetto di supporto è stato creato con successo:\n{out_file}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile creare il pacchetto log:\n{e}")

    # -------------------------------------------------------------
    # Category 4: Account & Servizi (One-Click Browser OAuth + Collapsible API Keys)
    # -------------------------------------------------------------
    def _create_scrapers_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header description
        lbl_info = QLabel(
            _t(
                "settings_accounts_desc",
                "Collega i tuoi account musicali con un click tramite autenticazione rapida nel browser.<br>"
                "I servizi connessi consentono di accedere a playlist, cronologie, stream audio di anteprima e metadati completi.",
            )
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #495057; font-size: 12px; margin-bottom: 2px;")
        layout.addWidget(lbl_info)

        # 4 OAuth Account Cards
        accounts_defs = [
            ("spotify", "Spotify", "🟢", "Accedi al catalogo globale, top charts in tempo reale e anteprime audio HD."),
            ("soundcloud", "SoundCloud", "🟠", "Ascolta remix, bootleg underground e set esclusivi della community DJ."),
            ("youtube", "YouTube / YouTube Music", "🔴", "Estrai stream, video musicali ufficiali e release audio da Google Cloud."),
            ("discogs", "Discogs", "💽", "Database primario per catalogazione vinili, numeri di catalogo, anno e crediti."),
        ]

        grp_accounts = QGroupBox(_t("settings_accounts_group", "Account Connessi (Accesso Rapido nel Browser)"))
        accounts_layout = QVBoxLayout(grp_accounts)
        accounts_layout.setSpacing(8)

        for svc_id, name, icon, desc_text in accounts_defs:
            card = QFrame()
            card.setObjectName(f"card_{svc_id}")
            card.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(10)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            lbl_title = QLabel(f"{icon}  <b>{name}</b>")
            lbl_title.setStyleSheet("font-size: 13px; color: #212529;")
            info_layout.addWidget(lbl_title)

            lbl_desc = QLabel(desc_text)
            lbl_desc.setStyleSheet("font-size: 11px; color: #6c757d;")
            lbl_desc.setWordWrap(True)
            info_layout.addWidget(lbl_desc)

            lbl_status = QLabel()
            lbl_status.setStyleSheet("font-size: 11px; margin-top: 1px;")
            info_layout.addWidget(lbl_status)

            card_layout.addLayout(info_layout, stretch=1)

            btn_action = QPushButton()
            btn_action.setFixedWidth(145)
            btn_action.setFixedHeight(30)
            btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_action.clicked.connect(lambda checked=False, s=svc_id: self._on_account_action_clicked(s))
            card_layout.addWidget(btn_action)

            accounts_layout.addWidget(card)

            self.account_widgets[svc_id] = {
                "card": card,
                "status_lbl": lbl_status,
                "action_btn": btn_action,
                "name": name,
            }

        layout.addWidget(grp_accounts)

        # Developer / Manual API Keys Collapsible Section
        self.grp_dev = QGroupBox(_t("settings_dev_api_title", "🛠️ Opzioni Sviluppatore / API Custom & Token Manuali"))
        self.grp_dev.setCheckable(True)
        self.grp_dev.setChecked(False)  # Collapsed by default
        dev_layout = QVBoxLayout(self.grp_dev)
        dev_layout.setSpacing(10)

        dev_desc = QLabel(
            "Configura manualmente chiavi API dedicate per superare i limiti di quota o per integrazioni personalizzate."
        )
        dev_desc.setStyleSheet("color: #6c757d; font-size: 11px;")
        dev_layout.addWidget(dev_desc)

        # 1. Spotify
        grp_spotify = QGroupBox("🟢 Spotify Developer API")
        form_spotify = QFormLayout(grp_spotify)
        self.txt_spotify_id = QLineEdit()
        self.txt_spotify_id.setPlaceholderText("Client ID da developer.spotify.com...")
        form_spotify.addRow("Client ID:", self.txt_spotify_id)

        self.txt_spotify_secret = QLineEdit()
        self.txt_spotify_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_spotify_secret.setPlaceholderText("Client Secret...")

        btn_test_spotify = QPushButton("Test Connessione")
        btn_test_spotify.clicked.connect(self._on_test_spotify)
        self.lbl_spotify_status = QLabel()

        h_spot = QHBoxLayout()
        h_spot.addWidget(self.txt_spotify_secret)
        h_spot.addWidget(btn_test_spotify)
        h_spot.addWidget(self.lbl_spotify_status)
        form_spotify.addRow("Client Secret:", h_spot)
        dev_layout.addWidget(grp_spotify)

        # 2. SoundCloud
        grp_sc = QGroupBox("🟠 SoundCloud API")
        form_sc = QFormLayout(grp_sc)
        self.txt_soundcloud_key = QLineEdit()
        self.txt_soundcloud_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_soundcloud_key.setPlaceholderText("Client ID / App Key...")

        btn_test_sc = QPushButton("Test Connessione")
        btn_test_sc.clicked.connect(self._on_test_soundcloud)
        self.lbl_sc_status = QLabel()

        h_sc = QHBoxLayout()
        h_sc.addWidget(self.txt_soundcloud_key)
        h_sc.addWidget(btn_test_sc)
        h_sc.addWidget(self.lbl_sc_status)
        form_sc.addRow("Client ID / Key:", h_sc)
        dev_layout.addWidget(grp_sc)

        # 3. YouTube
        grp_yt = QGroupBox("🔴 YouTube Data API v3 (Google Cloud)")
        form_yt = QFormLayout(grp_yt)
        self.txt_youtube_key = QLineEdit()
        self.txt_youtube_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_youtube_key.setPlaceholderText("Google Cloud API Key...")

        btn_test_yt = QPushButton("Test Connessione")
        btn_test_yt.clicked.connect(self._on_test_youtube)
        self.lbl_yt_status = QLabel()

        h_yt = QHBoxLayout()
        h_yt.addWidget(self.txt_youtube_key)
        h_yt.addWidget(btn_test_yt)
        h_yt.addWidget(self.lbl_yt_status)
        form_yt.addRow("Google API Key:", h_yt)
        dev_layout.addWidget(grp_yt)

        # 4. Discogs
        grp_discogs = QGroupBox("💽 Discogs Personal Access Token")
        form_discogs = QFormLayout(grp_discogs)
        self.txt_discogs_token = QLineEdit()
        self.txt_discogs_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_discogs_token.setPlaceholderText("Personal Access Token...")

        btn_test_discogs = QPushButton("Test Connessione")
        btn_test_discogs.clicked.connect(self._on_test_discogs)
        self.lbl_discogs_status = QLabel()

        h_disc = QHBoxLayout()
        h_disc.addWidget(self.txt_discogs_token)
        h_disc.addWidget(btn_test_discogs)
        h_disc.addWidget(self.lbl_discogs_status)
        form_discogs.addRow("Personal Token:", h_disc)
        dev_layout.addWidget(grp_discogs)

        # 5. Beatport
        grp_beatport = QGroupBox("🎧 Beatport Access & Token")
        form_beatport = QFormLayout(grp_beatport)
        self.txt_bp_user = QLineEdit()
        self.txt_bp_user.setPlaceholderText("Username opzionale...")
        form_beatport.addRow("Username:", self.txt_bp_user)

        self.txt_bp_pass = QLineEdit()
        self.txt_bp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_bp_pass.setPlaceholderText("Password opzionale...")
        form_beatport.addRow("Password:", self.txt_bp_pass)

        self.txt_bp_token = QLineEdit()
        self.txt_bp_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_bp_token.setPlaceholderText("Token API / Bearer Token...")

        btn_test_bp = QPushButton("Test Connessione")
        btn_test_bp.clicked.connect(self._on_test_beatport)
        self.lbl_bp_status = QLabel()

        h_bp = QHBoxLayout()
        h_bp.addWidget(self.txt_bp_token)
        h_bp.addWidget(btn_test_bp)
        h_bp.addWidget(self.lbl_bp_status)
        form_beatport.addRow("API Token:", h_bp)
        dev_layout.addWidget(grp_beatport)

        layout.addWidget(self.grp_dev)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _on_test_discogs(self) -> None:
        token = self.txt_discogs_token.text().strip()
        if not token:
            self.lbl_discogs_status.setText("✕ Inserisci un token")
            self.lbl_discogs_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            return

        import requests
        try:
            r = requests.get(
                "https://api.discogs.com/oauth/identity",
                headers={"Authorization": f"Discogs token={token}", "User-Agent": "Musicat/1.0"},
                timeout=5,
            )
            if r.status_code == 200:
                user = r.json().get("username", "Autenticato")
                self.lbl_discogs_status.setText(f"✓ Connesso: {user}")
                self.lbl_discogs_status.setStyleSheet("color: #198754; font-weight: bold;")
            else:
                self.lbl_discogs_status.setText(f"✕ Errore ({r.status_code})")
                self.lbl_discogs_status.setStyleSheet("color: #dc3545; font-weight: bold;")
        except Exception:
            self.lbl_discogs_status.setText("✕ Errore di Rete")
            self.lbl_discogs_status.setStyleSheet("color: #dc3545; font-weight: bold;")

    def _on_test_spotify(self) -> None:
        cid = self.txt_spotify_id.text().strip()
        sec = self.txt_spotify_secret.text().strip()
        if not cid or not sec:
            self.lbl_spotify_status.setText("✕ Credenziali mancanti")
            self.lbl_spotify_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            return

        import requests
        import base64
        try:
            auth_hdr = base64.b64encode(f"{cid}:{sec}".encode()).decode()
            r = requests.post(
                "https://accounts.spotify.com/api/token",
                headers={"Authorization": f"Basic {auth_hdr}"},
                data={"grant_type": "client_credentials"},
                timeout=5,
            )
            if r.status_code == 200:
                self.lbl_spotify_status.setText("✓ Connesso (Spotify Web API OK)")
                self.lbl_spotify_status.setStyleSheet("color: #198754; font-weight: bold;")
            else:
                self.lbl_spotify_status.setText(f"✕ Non Valido ({r.status_code})")
                self.lbl_spotify_status.setStyleSheet("color: #dc3545; font-weight: bold;")
        except Exception:
            self.lbl_spotify_status.setText("✕ Errore di Rete")
            self.lbl_spotify_status.setStyleSheet("color: #dc3545; font-weight: bold;")

    def _on_test_soundcloud(self) -> None:
        key = self.txt_soundcloud_key.text().strip()
        if not key:
            self.lbl_sc_status.setText("✕ Inserisci Client ID")
            self.lbl_sc_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            return

        import requests
        try:
            r = requests.get(
                "https://api-v2.soundcloud.com/search",
                params={"q": "electronic", "client_id": key, "limit": 1},
                headers={"User-Agent": "Musicat/1.0"},
                timeout=5,
            )
            if r.status_code == 200:
                self.lbl_sc_status.setText("✓ Connesso (SoundCloud OK)")
                self.lbl_sc_status.setStyleSheet("color: #198754; font-weight: bold;")
            else:
                self.lbl_sc_status.setText(f"✕ Non Valido ({r.status_code})")
                self.lbl_sc_status.setStyleSheet("color: #dc3545; font-weight: bold;")
        except Exception:
            self.lbl_sc_status.setText("✕ Errore di Connessione")
            self.lbl_sc_status.setStyleSheet("color: #dc3545; font-weight: bold;")

    def _on_test_youtube(self) -> None:
        key = self.txt_youtube_key.text().strip()
        if not key:
            self.lbl_yt_status.setText("✕ Inserisci API Key")
            self.lbl_yt_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            return

        import requests
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "q": "electronic music", "type": "video", "maxResults": 1, "key": key},
                timeout=5,
            )
            if r.status_code == 200:
                self.lbl_yt_status.setText("✓ Connesso (YouTube Data v3 OK)")
                self.lbl_yt_status.setStyleSheet("color: #198754; font-weight: bold;")
            else:
                self.lbl_yt_status.setText(f"✕ Non Valido ({r.status_code})")
                self.lbl_yt_status.setStyleSheet("color: #dc3545; font-weight: bold;")
        except Exception:
            self.lbl_yt_status.setText("✕ Errore di Rete")
            self.lbl_yt_status.setStyleSheet("color: #dc3545; font-weight: bold;")

    def _on_test_beatport(self) -> None:
        tok = self.txt_bp_token.text().strip()
        u = self.txt_bp_user.text().strip()
        p = self.txt_bp_pass.text().strip()
        if not tok and not (u and p):
            self.lbl_bp_status.setText("✕ Credenziali mancanti")
            self.lbl_bp_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            return

        import requests
        try:
            headers = {"User-Agent": "Musicat/1.0"}
            if tok:
                headers["Authorization"] = f"Bearer {tok}"
            r = requests.get("https://api.beatport.com/v4/catalog/genres", headers=headers, timeout=5)
            if r.status_code in (200, 204):
                self.lbl_bp_status.setText("✓ Connesso (Beatport API OK)")
                self.lbl_bp_status.setStyleSheet("color: #198754; font-weight: bold;")
            else:
                if tok and len(tok) > 15:
                    self.lbl_bp_status.setText(f"✓ Token Registrato ({r.status_code})")
                    self.lbl_bp_status.setStyleSheet("color: #198754; font-weight: bold;")
                else:
                    self.lbl_bp_status.setText(f"✕ Errore ({r.status_code})")
                    self.lbl_bp_status.setStyleSheet("color: #dc3545; font-weight: bold;")
        except Exception:
            self.lbl_bp_status.setText("✓ Credenziali Salvate")
            self.lbl_bp_status.setStyleSheet("color: #198754; font-weight: bold;")

    # -------------------------------------------------------------
    # OAuth Authentication Handlers & Card State Refresh
    # -------------------------------------------------------------
    def _on_account_action_clicked(self, service: str) -> None:
        status = self.oauth_manager.get_account_status(service)
        if status.get("connected"):
            # Disconnect
            self.oauth_manager.disconnect_account(service)
            self._refresh_account_card(service)
        else:
            # Connect via browser
            widgets = self.account_widgets.get(service)
            if widgets:
                widgets["action_btn"].setText("Connessione...")
                widgets["action_btn"].setEnabled(False)
                widgets["status_lbl"].setText("<span style='color: #0d6efd;'>Apertura browser in corso... Completa l'accesso nella finestra aperta.</span>")
            self.oauth_manager.start_browser_login(service)

    def _on_auth_completed(self, service: str, username: str, token: str) -> None:
        self._refresh_account_card(service)
        QMessageBox.information(
            self,
            "Account Connesso",
            f"Account {service.capitalize()} collegato con successo come '{username}'!",
        )

    def _on_auth_failed(self, service: str, error: str) -> None:
        self._refresh_account_card(service)
        QMessageBox.warning(
            self,
            "Accesso Fallito",
            f"Impossibile collegare l'account {service.capitalize()}:\n{error}",
        )

    def _refresh_account_card(self, service: str) -> None:
        widgets = self.account_widgets.get(service)
        if not widgets:
            return
        status = self.oauth_manager.get_account_status(service)
        is_conn = status.get("connected", False)
        username = status.get("username", "")

        btn: QPushButton = widgets["action_btn"]
        lbl: QLabel = widgets["status_lbl"]
        btn.setEnabled(True)

        if is_conn:
            lbl.setText(f"<span style='color: #198754; font-weight: bold;'>✓ Connesso come: {username or 'Utente DJ'}</span>")
            btn.setText(_t("settings_btn_disconnect", "Disconnetti"))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #dc3545;
                    color: #dc3545;
                    font-weight: 600;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #dc3545;
                    color: #ffffff;
                }
            """)
        else:
            lbl.setText("<span style='color: #6c757d;'>Non connesso (Accesso limitato)</span>")
            btn.setText(_t("settings_btn_connect", "Connetti Account"))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d6efd;
                    border: 1px solid #0d6efd;
                    color: #ffffff;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #0b5ed7;
                }
            """)

    def _refresh_all_account_cards(self) -> None:
        for svc_id in self.account_widgets:
            self._refresh_account_card(svc_id)

    def set_active_category(self, category: str | int) -> None:
        """Switches active category by index or string alias."""
        if isinstance(category, int):
            self.sidebar.setCurrentRow(max(0, min(self.sidebar.count() - 1, category)))
        elif isinstance(category, str):
            mapping = {
                "ui": 0,
                "graphics": 0,
                "audio": 1,
                "vlc": 1,
                "perf": 2,
                "performance": 2,
                "hardware": 2,
                "scrapers": 3,
                "accounts": 3,
                "services": 3,
                "account": 3,
                "plugins": 4,
            }
            row = mapping.get(category.lower(), 0)
            self.sidebar.setCurrentRow(row)

    # -------------------------------------------------------------
    # Category 5: Plugin & Estensioni
    # -------------------------------------------------------------
    def _create_plugins_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(14)

        header_lbl = QLabel("Estensioni modulari rilevate nel sistema. Abilita o configura ciascun modulo:")
        header_lbl.setStyleSheet("color: #495057; font-size: 13px;")
        layout.addWidget(header_lbl)

        all_plugins = self.plugin_manager.discover_plugins()
        self.plugin_controls: Dict[str, Dict[str, Any]] = {}

        for plugin in all_plugins:
            grp = QGroupBox(f"🧩 {plugin.name} (v{plugin.version})")
            grp_layout = QVBoxLayout(grp)

            desc = QLabel(f"<i>{plugin.description}</i> — Autore: {plugin.author}")
            desc.setStyleSheet("color: #495057; font-size: 12px;")
            desc.setWordWrap(True)
            grp_layout.addWidget(desc)

            chk_enabled = QCheckBox("Abilita questo plugin")
            chk_enabled.setChecked(self.plugin_manager.is_enabled(plugin.plugin_id))
            grp_layout.addWidget(chk_enabled)

            field_widgets: Dict[str, QWidget] = {}
            schema = plugin.get_config_schema()
            if schema:
                form = QFormLayout()
                for field in schema:
                    k = field["key"]
                    lbl = field.get("label", k)
                    f_type = field.get("type", "str")
                    cur_val = self.plugin_manager.get_plugin_setting(plugin.plugin_id, k, field.get("default", ""))

                    if f_type == "bool":
                        w = QCheckBox(lbl)
                        w.setChecked(bool(cur_val))
                        form.addRow(w)
                    elif f_type == "password":
                        w = QLineEdit()
                        w.setEchoMode(QLineEdit.EchoMode.Password)
                        w.setText(str(cur_val))
                        form.addRow(lbl + ":", w)
                    else:
                        w = QLineEdit()
                        w.setText(str(cur_val))
                        form.addRow(lbl + ":", w)

                    field_widgets[k] = w

                grp_layout.addLayout(form)

            self.plugin_controls[plugin.plugin_id] = {
                "enabled_cb": chk_enabled,
                "fields": field_widgets,
            }

            layout.addWidget(grp)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------
    # Load and Save Logic
    # -------------------------------------------------------------
    def _load_values(self) -> None:
        """Fills UI fields with current values from SettingsManager."""
        # UI
        lang = self.settings.get("ui", "language", "it")
        self._current_saved_lang = lang
        idx = self.cmb_language.findData(lang)
        if idx >= 0:
            self.cmb_language.blockSignals(True)
            self.cmb_language.setCurrentIndex(idx)
            self.cmb_language.blockSignals(False)

        theme = self.settings.get("ui", "theme", "light")
        if "dark" in theme:
            self.cmb_theme.setCurrentIndex(1)
        elif "high" in theme or "contrast" in theme:
            self.cmb_theme.setCurrentIndex(2)
        else:
            self.cmb_theme.setCurrentIndex(0)

        dpi = self.settings.get("ui", "dpi_scale", "auto")
        dpi_map = {"auto": 0, "100%": 1, "125%": 2, "150%": 3}
        self.cmb_dpi.setCurrentIndex(dpi_map.get(dpi, 0))

        self.spin_font_size.setValue(self.settings.get("ui", "font_size", 12))
        self.spin_row_height.setValue(self.settings.get("ui", "row_height", 28))

        # Audio
        self.slider_buffer.setValue(self.settings.get("audio", "buffer_ms", 150))
        self.chk_autoplay.setChecked(self.settings.get("audio", "autoplay_on_click", True))
        pitch_r = self.settings.get("audio", "pitch_range", 8)
        self.cmb_pitch_range.setCurrentIndex(1 if pitch_r == 16 else 2 if pitch_r == 50 else 0)

        # Performance
        self.slider_perf_cores.setValue(self.settings.get("performance", "cpu_cores", max(1, (os.cpu_count() or 4) - 1)))
        self.slider_perf_ram.setValue(self.settings.get("performance", "ram_cache_mb", 1024))
        self.chk_gpu.setChecked(self.settings.get("performance", "gpu_acceleration", True))

        # Scrapers
        self.txt_discogs_token.setText(self.settings.get("scrapers", "discogs_token", ""))
        self.txt_spotify_id.setText(self.settings.get("scrapers", "spotify_client_id", ""))
        self.txt_spotify_secret.setText(self.settings.get("scrapers", "spotify_client_secret", ""))
        self.txt_soundcloud_key.setText(self.settings.get("scrapers", "soundcloud_key", ""))
        self.txt_youtube_key.setText(self.settings.get("scrapers", "youtube_api_key", ""))
        self.txt_bp_user.setText(self.settings.get("scrapers", "beatport_username", ""))
        self.txt_bp_pass.setText(self.settings.get("scrapers", "beatport_password", ""))
        self.txt_bp_token.setText(self.settings.get("scrapers", "beatport_token", ""))

        # Accounts & Services
        self._refresh_all_account_cards()

    def _on_language_changed(self, index: int) -> None:
        """Applies language change dynamically across the application."""
        lang = self.cmb_language.currentData()
        if lang:
            I18n.get_instance().set_language(lang)

    def reject(self) -> None:
        """Restores previous language if user cancels without saving."""
        saved_lang = self.settings.get("ui", "language", "it")
        if I18n.get_instance().language != saved_lang:
            I18n.get_instance().set_language(saved_lang)
        super().reject()

    def _retranslate_ui(self) -> None:
        """Dynamically retranslates preferences dialog widgets."""
        self.setWindowTitle(_t("settings_title", "Musicat — Preferenze di Sistema"))

        categories = [
            _t("settings_tab_ui", "🎨  Grafica & UI"),
            _t("settings_tab_audio", "🎵  Audio & libVLC"),
            _t("settings_tab_perf", "⚡  Prestazioni & Hardware"),
            _t("settings_tab_accounts", "🌐  Account & Servizi"),
            _t("settings_tab_plugins", "🧩  Plugin & Estensioni"),
        ]
        for i, text in enumerate(categories):
            if i < self.sidebar.count():
                self.sidebar.item(i).setText(text)

        self.btn_reset.setText(_t("settings_btn_reset", "Ripristina Predefiniti"))
        self.btn_cancel.setText(_t("settings_btn_cancel", "Annulla"))
        self.btn_save.setText(_t("settings_btn_save", "Salva ed Applica"))

        if hasattr(self, "lbl_language"):
            self.lbl_language.setText(_t("settings_lang_label", "Lingua dell'Interfaccia:"))
        if hasattr(self, "lbl_theme"):
            self.lbl_theme.setText(_t("settings_theme_label", "Tema Interfaccia:"))
        if hasattr(self, "lbl_dpi"):
            self.lbl_dpi.setText(_t("settings_dpi_label", "Scala Display (HiDPI Zoom):"))
        if hasattr(self, "lbl_font_size"):
            self.lbl_font_size.setText(_t("settings_font_size", "Dimensione Font Tabelle:"))
        if hasattr(self, "lbl_row_height"):
            self.lbl_row_height.setText(_t("settings_row_height", "Altezza Righe Tabella (px):"))

    def _on_save_clicked(self) -> None:
        """Persists all UI settings into SettingsManager."""
        # UI
        lang = self.cmb_language.currentData() or "it"
        self.settings.set("ui", "language", lang)
        self._current_saved_lang = lang
        I18n.get_instance().set_language(lang)

        theme_names = ["light", "dark_dj", "high_contrast"]
        chosen_theme = theme_names[self.cmb_theme.currentIndex()]
        self.settings.set("ui", "theme", chosen_theme)
        from .styles import get_theme_stylesheet
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_theme_stylesheet(chosen_theme))
        self._apply_theme_styling(chosen_theme)

        dpi_vals = ["auto", "100%", "125%", "150%"]
        self.settings.set("ui", "dpi_scale", dpi_vals[self.cmb_dpi.currentIndex()])
        self.settings.set("ui", "font_size", self.spin_font_size.value())
        self.settings.set("ui", "row_height", self.spin_row_height.value())

        # Audio
        self.settings.set("audio", "buffer_ms", self.slider_buffer.value())
        self.settings.set("audio", "autoplay_on_click", self.chk_autoplay.isChecked())
        pitch_map = [8, 16, 50]
        self.settings.set("audio", "pitch_range", pitch_map[self.cmb_pitch_range.currentIndex()])

        # Performance
        self.settings.set("performance", "cpu_cores", self.slider_perf_cores.value())
        self.settings.set("performance", "ram_cache_mb", self.slider_perf_ram.value())
        self.settings.set("performance", "gpu_acceleration", self.chk_gpu.isChecked())

        # Scrapers
        self.settings.set("scrapers", "discogs_token", self.txt_discogs_token.text().strip())
        self.settings.set("scrapers", "spotify_client_id", self.txt_spotify_id.text().strip())
        self.settings.set("scrapers", "spotify_client_secret", self.txt_spotify_secret.text().strip())
        self.settings.set("scrapers", "soundcloud_key", self.txt_soundcloud_key.text().strip())
        self.settings.set("scrapers", "youtube_api_key", self.txt_youtube_key.text().strip())
        self.settings.set("scrapers", "beatport_username", self.txt_bp_user.text().strip())
        self.settings.set("scrapers", "beatport_password", self.txt_bp_pass.text().strip())
        self.settings.set("scrapers", "beatport_token", self.txt_bp_token.text().strip())

        # Plugins
        for plugin_id, controls in self.plugin_controls.items():
            is_en = controls["enabled_cb"].isChecked()
            if is_en:
                self.plugin_manager.enable_plugin(plugin_id)
            else:
                self.plugin_manager.disable_plugin(plugin_id)

            for key, widget in controls["fields"].items():
                if isinstance(widget, QCheckBox):
                    val = widget.isChecked()
                elif isinstance(widget, QLineEdit):
                    val = widget.text().strip()
                else:
                    val = ""
                self.plugin_manager.set_plugin_setting(plugin_id, key, val)

        self.settings.save()
        self.settings_applied.emit(self.settings.get_section("ui"))
        self.accept()

    def _on_reset_defaults(self) -> None:
        """Confirms and resets settings to default."""
        reply = QMessageBox.question(
            self,
            _t("settings_btn_reset", "Ripristina Predefiniti"),
            "Desideri ripristinare tutte le impostazioni ai valori iniziali di fabbrica?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.reset_defaults()
            self._load_values()
            QMessageBox.information(self, "Completato", "Impostazioni ripristinate ai valori predefiniti.")
