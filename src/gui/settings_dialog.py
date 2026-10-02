"""
Modular Settings & Preferences Dialog for Musicat.

Features:
- Category navigation sidebar (UI/Graphics, Audio/VLC, Performance/GPU, Scrapers, Plugins).
- High-DPI zoom, theme selection, table column toggles, row height/font size.
- Audio output device selection, buffer latency, player behavior.
- Multiprocessing CPU allocation, RAM buffer sizing, GPU acceleration toggle with hardware badge.
- Scraper tokens & credentials with instant connection verification.
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
from src.core.i18n import I18n, _t
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

        self.setWindowTitle(_t("settings_title", "Musicat — Preferenze di Sistema"))
        self.resize(840, 600)
        self.setMinimumSize(780, 520)

        self._init_ui()
        self._load_values()
        self._retranslate_ui()
        I18n.get_instance().language_changed.connect(self._retranslate_ui)

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 1. Left Sidebar Navigation
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
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
            QListWidget::item:selected {
                background-color: #00d2ff;
                color: #0b0c10;
                font-weight: bold;
            }
        """)

        categories = [
            ("🎨  Grafica & UI", 0),
            ("🎵  Audio & libVLC", 1),
            ("⚡  Prestazioni & Hardware", 2),
            ("🌐  Scrapers & API Keys", 3),
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
        self.stack.setStyleSheet("QStackedWidget { background-color: #12141a; }")

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

        self.btn_reset = QPushButton("Ripristina Predefiniti")
        self.btn_reset.clicked.connect(self._on_reset_defaults)
        btn_bar.addWidget(self.btn_reset)

        btn_bar.addStretch()

        self.btn_cancel = QPushButton("Annulla")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Salva ed Applica")
        self.btn_save.setStyleSheet("background-color: #0077b6; border-color: #0096c7; font-weight: bold;")
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_bar.addWidget(self.btn_save)

        right_container.addLayout(btn_bar)
        main_layout.addLayout(right_container)

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
        self.cmb_theme.addItems(["Dark DJ Console (Predefinito)", "High-Contrast Club Booth", "Light Studio Mode"])
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

        # Columns Group
        self.grp_cols = QGroupBox("📋 Colonne Visibili della Tabella Brani")
        cols_grid = QGridLayout(self.grp_cols)

        self.col_checkboxes: Dict[str, QCheckBox] = {}
        all_columns = [
            ("title", "Titolo"),
            ("artist", "Artista"),
            ("album", "Album"),
            ("genre", "Genere"),
            ("year", "Anno"),
            ("bpm", "BPM"),
            ("camelot_key", "Camelot Key"),
            ("duration", "Durata"),
            ("bitrate", "Bitrate"),
            ("label", "Etichetta (Label)"),
            ("remixer", "Remixer"),
            ("energy_level", "Energy Level"),
            ("lufs", "LUFS"),
            ("true_peak", "True Peak (dBTP)"),
            ("audio_status", "Qualità Audio"),
        ]

        for idx, (col_id, col_name) in enumerate(all_columns):
            cb = QCheckBox(col_name)
            self.col_checkboxes[col_id] = cb
            cols_grid.addWidget(cb, idx // 3, idx % 3)

        layout.addWidget(grp_cols)
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

        self.slider_perf_ram = QSlider(Qt.Orientation.Horizontal)
        self.slider_perf_ram.setRange(128, 2048)
        self.slider_perf_ram.setSingleStep(128)
        self.slider_perf_ram.setValue(512)
        self.lbl_perf_ram = QLabel("512 MB")
        self.slider_perf_ram.valueChanged.connect(lambda v: self.lbl_perf_ram.setText(f"{v} MB"))

        r_box = QHBoxLayout()
        r_box.addWidget(self.slider_perf_ram)
        r_box.addWidget(self.lbl_perf_ram)
        form_cpu.addRow("Dimensione RAM Cache L1 (DB & Waveform):", r_box)

        layout.addWidget(grp_cpu)

        # GPU Card Box
        grp_gpu = QGroupBox("🎮 Accelerazione Hardware GPU")
        gpu_layout = QVBoxLayout(grp_gpu)

        self.chk_gpu = QCheckBox("Abilita accelerazione spettrale su scheda grafica GPU")
        self.chk_gpu.setChecked(self.gpu_info.is_available)
        gpu_layout.addWidget(self.chk_gpu)

        # Status badge
        badge_frame = QFrame()
        badge_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1e2a;
                border: 1px solid #2e354a;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        badge_layout = QVBoxLayout(badge_frame)

        lbl_device = QLabel(f"<b>Dispositivo Rilevato:</b> {self.gpu_info.device_name}")
        lbl_backend = QLabel(f"<b>Backend Computazionale:</b> {self.gpu_info.backend}")
        lbl_status = QLabel(f"<b>Stato:</b> {self.gpu_info.status_message}")
        lbl_status.setStyleSheet("color: #00d2ff;" if self.gpu_info.is_available else "color: #94a3b8;")

        badge_layout.addWidget(lbl_device)
        badge_layout.addWidget(lbl_backend)
        badge_layout.addWidget(lbl_status)
        gpu_layout.addWidget(badge_frame)

        layout.addWidget(grp_gpu)
        layout.addStretch()
        return widget

    # -------------------------------------------------------------
    # Category 4: Scrapers & API Keys
    # -------------------------------------------------------------
    def _create_scrapers_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        grp_discogs = QGroupBox("💽 Discogs API")
        form_discogs = QFormLayout(grp_discogs)
        self.txt_discogs_token = QLineEdit()
        self.txt_discogs_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_discogs_token.setPlaceholderText("Inserisci il tuo Personal Access Token di Discogs...")

        btn_test_discogs = QPushButton("Test Connessione")
        btn_test_discogs.clicked.connect(self._on_test_discogs)

        h_disc = QHBoxLayout()
        h_disc.addWidget(self.txt_discogs_token)
        h_disc.addWidget(btn_test_discogs)
        form_discogs.addRow("User Token:", h_disc)
        layout.addWidget(grp_discogs)

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

        h_spot = QHBoxLayout()
        h_spot.addWidget(self.txt_spotify_secret)
        h_spot.addWidget(btn_test_spotify)
        form_spotify.addRow("Client Secret:", h_spot)
        layout.addWidget(grp_spotify)

        grp_beatport = QGroupBox("🎧 Beatport Access")
        form_beatport = QFormLayout(grp_beatport)
        self.txt_bp_user = QLineEdit()
        self.txt_bp_user.setPlaceholderText("Username opzionale...")
        form_beatport.addRow("Username / Account:", self.txt_bp_user)
        self.txt_bp_pass = QLineEdit()
        self.txt_bp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_beatport.addRow("Password:", self.txt_bp_pass)
        layout.addWidget(grp_beatport)

        layout.addStretch()
        return widget

    def _on_test_discogs(self) -> None:
        token = self.txt_discogs_token.text().strip()
        if not token:
            QMessageBox.warning(self, "Token Mancante", "Inserisci un token prima del test.")
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
                QMessageBox.information(self, "Connessione Riuscita", f"Autenticazione Discogs valida per l'utente: {user}")
            else:
                QMessageBox.critical(self, "Errore", f"Token Discogs non valido (Status {r.status_code})")
        except Exception as e:
            QMessageBox.critical(self, "Errore di Rete", f"Impossibile contattare Discogs:\n{e}")

    def _on_test_spotify(self) -> None:
        cid = self.txt_spotify_id.text().strip()
        sec = self.txt_spotify_secret.text().strip()
        if not cid or not sec:
            QMessageBox.warning(self, "Credenziali Mancanti", "Inserisci Client ID e Secret.")
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
                QMessageBox.information(self, "Connessione Riuscita", "Autenticazione Spotify API confermata con successo!")
            else:
                QMessageBox.critical(self, "Errore", f"Credenziali Spotify errate (Status {r.status_code})")
        except Exception as e:
            QMessageBox.critical(self, "Errore di Rete", f"Impossibile contattare Spotify:\n{e}")

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
        header_lbl.setStyleSheet("color: #94a3b8; font-size: 13px;")
        layout.addWidget(header_lbl)

        all_plugins = self.plugin_manager.discover_plugins()
        self.plugin_controls: Dict[str, Dict[str, Any]] = {}

        for plugin in all_plugins:
            grp = QGroupBox(f"🧩 {plugin.name} (v{plugin.version})")
            grp_layout = QVBoxLayout(grp)

            desc = QLabel(f"<i>{plugin.description}</i> — Autore: {plugin.author}")
            desc.setStyleSheet("color: #cbd5e1; font-size: 12px;")
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

        theme = self.settings.get("ui", "theme", "dark_dj")
        if "high" in theme or "contrast" in theme:
            self.cmb_theme.setCurrentIndex(1)
        elif "light" in theme:
            self.cmb_theme.setCurrentIndex(2)
        else:
            self.cmb_theme.setCurrentIndex(0)

        dpi = self.settings.get("ui", "dpi_scale", "auto")
        dpi_map = {"auto": 0, "100%": 1, "125%": 2, "150%": 3}
        self.cmb_dpi.setCurrentIndex(dpi_map.get(dpi, 0))

        self.spin_font_size.setValue(self.settings.get("ui", "font_size", 12))
        self.spin_row_height.setValue(self.settings.get("ui", "row_height", 28))

        vis_cols = self.settings.get("ui", "visible_columns", [])
        for col_id, cb in self.col_checkboxes.items():
            cb.setChecked(col_id in vis_cols)

        # Audio
        self.slider_buffer.setValue(self.settings.get("audio", "buffer_ms", 150))
        self.chk_autoplay.setChecked(self.settings.get("audio", "autoplay_on_click", True))
        pitch_r = self.settings.get("audio", "pitch_range", 8)
        self.cmb_pitch_range.setCurrentIndex(1 if pitch_r == 16 else 2 if pitch_r == 50 else 0)

        # Performance
        self.slider_perf_cores.setValue(self.settings.get("performance", "cpu_cores", max(1, (os.cpu_count() or 4) - 1)))
        self.slider_perf_ram.setValue(self.settings.get("performance", "ram_cache_mb", 512))
        self.chk_gpu.setChecked(self.settings.get("performance", "gpu_acceleration", True))

        # Scrapers
        self.txt_discogs_token.setText(self.settings.get("scrapers", "discogs_token", ""))
        self.txt_spotify_id.setText(self.settings.get("scrapers", "spotify_client_id", ""))
        self.txt_spotify_secret.setText(self.settings.get("scrapers", "spotify_client_secret", ""))
        self.txt_bp_user.setText(self.settings.get("scrapers", "beatport_username", ""))
        self.txt_bp_pass.setText(self.settings.get("scrapers", "beatport_password", ""))

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
            _t("settings_tab_scrapers", "🌐  Scrapers & API Keys"),
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
        if hasattr(self, "grp_cols"):
            self.grp_cols.setTitle(_t("settings_visible_cols", "📋 Colonne Visibili della Tabella Brani"))

    def _on_save_clicked(self) -> None:
        """Persists all UI settings into SettingsManager."""
        # UI
        lang = self.cmb_language.currentData() or "it"
        self.settings.set("ui", "language", lang)
        self._current_saved_lang = lang
        I18n.get_instance().set_language(lang)

        theme_names = ["dark_dj", "high_contrast", "light"]
        self.settings.set("ui", "theme", theme_names[self.cmb_theme.currentIndex()])

        dpi_vals = ["auto", "100%", "125%", "150%"]
        self.settings.set("ui", "dpi_scale", dpi_vals[self.cmb_dpi.currentIndex()])
        self.settings.set("ui", "font_size", self.spin_font_size.value())
        self.settings.set("ui", "row_height", self.spin_row_height.value())

        visible_cols = [col_id for col_id, cb in self.col_checkboxes.items() if cb.isChecked()]
        self.settings.set("ui", "visible_columns", visible_cols)

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
        self.settings.set("scrapers", "beatport_username", self.txt_bp_user.text().strip())
        self.settings.set("scrapers", "beatport_password", self.txt_bp_pass.text().strip())

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
