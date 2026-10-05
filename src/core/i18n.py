"""
Internationalization (i18n) & Localization Engine for Musicat.

Features:
- Native bilingual support: Italian (default) and English.
- Automatic system language detection on initial startup with Italian fallback.
- Thread-safe singleton with dynamic Qt signal emission on language change.
- Zero-downtime dynamic UI translation reloading.
- Dual-layer storage: embedded fallback dictionary + external JSON definitions (`locales/*.json`).
"""

from __future__ import annotations

import json
import locale
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QLocale, QObject, Signal

from src.core.path_resolver import PathResolver


SUPPORTED_LANGUAGES: List[Tuple[str, str]] = [
    ("it", "Italiano"),
    ("en", "English"),
]

DEFAULT_LANGUAGE = "it"


# Embedded fallback dictionaries for standalone/frozen binary safety
EMBEDDED_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "it": {
        "app_name": "Musicat",
        "app_title": "Musicat — DJ Catalog & Smart Organizer",
        "nav_analysis": "Analisi / Home",
        "nav_library": "Libreria",
        "nav_mp3tag": "Tag Editor (Mp3tag)",
        "nav_crates": "Smart Crates",
        "nav_similar": "Trova Simili",
        "nav_organizer": "Organizza File",
        "nav_settings": "Impostazioni",
        "nav_scan": "📂 Scansiona",
        "nav_refresh": "🔄 Aggiorna",
        "nav_sidebar": "📁 Barra laterale",
        "sidebar_title": "📁 LIBRERIA & CRATES",
        "sidebar_smart_crates": "🎛️ SMART CRATES",
        "sidebar_folders": "📁 CARTELLE FILESYSTEM",
        "nav_trends": "🏠 Top Trends & Classifiche",
        "ready": "Pronto",
        "library_status": "Libreria: {count} tracce ({hours}h {mins}m) | Database: {db}",
        "showing_tracks": "Visualizzate {filtered} di {total} tracce",
        "found_tracks": "Trovate {count} tracce tramite {engine}",
        "tb_sidebar": "📁 Barra laterale",
        "tb_scan": "📂 Scansiona cartella",
        "tb_refresh": "🔄 Aggiorna",
        "tb_mp3tag": "🏷️ Spazio Mp3tag",
        "tb_quick_tag": "✏️ Tag Rapidi",
        "tb_filename_tag": "🔀 Nome File <-> Tag",
        "tb_reconcile": "⚖️ Riconciliazione & Cover HD",
        "tb_analyze": "🎵 Analizza BPM & Key",
        "tb_audio_quality": "🔊 Qualità Audio",
        "tb_find_similar": "✨ Trova Simili",
        "tb_organizer": "📦 Organizzatore Smart",
        "tb_settings": "⚙️ Impostazioni",
        "tb_live_log": "📜 Log in Tempo Reale",
        "tb_stats": "📊 Statistiche",
        "col_id": "#",
        "col_has_cover": "Cover",
        "col_title": "Titolo",
        "col_artist": "Artista",
        "col_remixer": "Remixer",
        "col_bpm": "BPM",
        "col_camelot_key": "Camelot",
        "col_musical_key": "Key",
        "col_genre": "Genere",
        "col_year": "Anno",
        "col_album": "Album",
        "col_label": "Etichetta",
        "col_duration": "Durata",
        "col_bitrate": "Bitrate",
        "col_energy_level": "Energia",
        "col_lufs": "LUFS",
        "col_true_peak": "True Peak",
        "col_audio_status": "Qualità Audio",
        "col_filepath": "Percorso",
        "filter_search_placeholder": "🔍 Ricerca Rapida / {engine} (Ctrl+F)...",
        "filter_genre_placeholder": "Seleziona / Cerca Generi (Ctrl+G)...",
        "filter_all_genres": "Tutti i Generi",
        "filter_one_genre": "1 Genere",
        "filter_multi_genres": "{count} Generi (OR)",
        "filter_clear_genres": "Rimuovi Selezione Generi",
        "filter_bpm": "BPM:",
        "filter_target_bpm": "Target",
        "filter_min_bpm": "Min",
        "filter_max_bpm": "Max",
        "filter_target_label": "Target:",
        "filter_min_label": "Min:",
        "filter_max_label": "Max:",
        "filter_key": "Key:",
        "filter_all_keys": "Tutte le Chiavi",
        "filter_harmonic_only": "Solo Armonici",
        "filter_wheel_btn": "🎡 Ruota",
        "filter_folder": "📁 Cartella:",
        "filter_all_folders": "Tutte le Cartelle / Drive",
        "filter_cover": "🖼️ Cover:",
        "filter_all_covers": "Tutte",
        "filter_with_cover": "Con Cover",
        "filter_without_cover": "Senza Cover",
        "filter_year": "Anno:",
        "filter_any_year": "Qualsiasi Anno",
        "filter_energy": "Energia:",
        "filter_any_energy": "⚡ Qualsiasi Energia",
        "filter_warmup": "⚡ Warmup Basso (1-2)",
        "filter_building": "⚡ Costruzione Media (3)",
        "filter_peak_time": "⚡ Peak Time (4-5)",
        "filter_rating": "Valutazione:",
        "filter_any_rating": "⭐ Tutte",
        "filter_audio": "Audio:",
        "filter_all_audio": "🔊 Tutto l'Audio",
        "filter_clipping": "⚠️ Clipping (>0 dBTP)",
        "filter_low_vol": "🔈 Basso Vol (<-18 LUFS)",
        "filter_brickwall": "🧱 Brickwall (LRA < 3)",
        "filter_problematic": "⚡ Tracce Problematiche",
        "filter_conforme": "✅ Conforme (OK)",
        "filter_smart_crates": "📁 Smart Crates...",
        "filter_save_crate": "💾 Salva Crate",
        "filter_export_m3u": "📤 Esporta M3U8",
        "filter_reset": "✕ Ripristina (ESC)",
        "player_no_track": "Nessuna traccia in riproduzione",
        "player_select_prompt": "Seleziona una traccia da ascoltare",
        "player_normalize": "⚡ Correggi",
        "player_similar": "✨ Simili",
        "player_pitch": "Pitch: {val}",
        "player_show_in_folder": "📂 Mostra nella cartella",
        "ctx_play": "▶ Riproduci nel Mini-Player",
        "ctx_find_similar": "✨ Trova Tracce Simili (Cosine & Library)...",
        "ctx_cut": "✂️ Taglia Traccia(e) (Ctrl+X)",
        "ctx_copy": "📋 Copia Traccia(e) (Ctrl+C)",
        "ctx_paste": "📥 Incolla Traccia(e) Qui (Ctrl+V)",
        "ctx_mp3tag": "🏷️ Apri nello Spazio Mp3tag (Ctrl+T)...",
        "ctx_edit_tags": "✏️ Modifica Tag (Batch)...",
        "ctx_reconcile": "⚖️ Riconciliazione Metadati & Cover HD...",
        "ctx_patterns": "🔀 Pattern Nome File <-> Tag...",
        "ctx_analyze": "🎵 Calcola BPM & Chiave Camelot",
        "ctx_quality": "🔊 Diagnosi Qualità Audio & Normalizza...",
        "ctx_sorter": "📁 Smista & Sposta in Cartella...",
        "ctx_show_folder": "📂 Mostra nella cartella (Show in Folder)",
        "settings_title": "Musicat — Preferenze di Sistema",
        "settings_tab_ui": "🎨  Grafica & UI",
        "settings_tab_audio": "🎵  Audio & libVLC",
        "settings_tab_perf": "⚡  Prestazioni & Hardware",
        "settings_tab_scrapers": "🌐  Scrapers & API Keys",
        "settings_tab_accounts": "🌐  Account & Servizi",
        "settings_accounts_desc": "Collega i tuoi account musicali con un click tramite autenticazione rapida nel browser.<br>I servizi connessi consentono di accedere a playlist, cronologie, stream audio di anteprima e metadati completi.",
        "settings_accounts_group": "Account Connessi (Accesso Rapido nel Browser)",
        "settings_dev_api_title": "🛠️ Opzioni Sviluppatore / API Custom & Token Manuali",
        "settings_btn_connect": "Connetti Account",
        "settings_btn_disconnect": "Disconnetti",
        "nav_top_charts": "🔥  Top Charts",
        "folder_filter_applied": "Cartella: {path} ({count} tracce)",
        "folder_no_audio": "Nessun file audio trovato nella cartella: {path}",
        "auto_scan_complete": "Scansione completata: {found} file audio indicizzati in '{folder}'",
        "scan_already_running": "Scansione già in corso...",
        "settings_tab_plugins": "🧩  Plugin & Estensioni",
        "settings_lang_label": "Lingua dell'Interfaccia:",
        "settings_theme_label": "Tema Interfaccia:",
        "settings_dpi_label": "Scala Display (HiDPI Zoom):",
        "settings_font_size": "Dimensione Font Tabelle:",
        "settings_row_height": "Altezza Righe Tabella (px):",
        "settings_visible_cols": "📋 Colonne Visibili della Tabella Brani",
        "settings_btn_reset": "Ripristina Predefiniti",
        "settings_btn_cancel": "Annulla",
        "settings_btn_save": "Salva ed Applica",
        "settings_saved_msg": "Preferenze salvate con successo!",
        "similar_dialog_title": "✨ Tracce Simili & Raccomandazioni DJ",
        "similar_tab_local": "Tracce Simili nella Tua Libreria",
        "similar_tab_discovery": "Scoperte Online & Tracce Mancanti",
        "similar_affinity_col": "Affinità",
        "similar_reasons_col": "Criteri Compatibilità",
        "similar_links_col": "Ascolta / Cerca",
        "similar_in_library": "✓ In Libreria",
        "similar_missing": "+ Mancante",
        "trends_header": "🏠 Top Trends & Classifiche DJ del Momento",
        "trends_refresh": "🔄 Aggiorna Classifiche",
        "trends_search": "Cerca nelle classifiche...",
        "trends_listen": "▶ Ascolta",
        "trends_similar": "✨ Simili",
        "trends_cached_badge": "Cache Locale",
        "trends_live_badge": "Live Spotify",
        "crates_workbench_title": "SMART CRATES WORKBENCH",
        "crates_workbench_sub": "Costruttore di casse intelligenti basate su regole logiche per DJ set",
        "crates_btn_new": "+ Nuovo Crate",
        "crates_btn_save": "Salva Regole",
        "crates_btn_export": "Esporta Playlist DJ",
        "crates_list_header": "I Tuoi Smart Crates",
        "crates_search_placeholder": "Cerca tra i Crates...",
        "crates_btn_dup": "Duplica",
        "crates_btn_ren": "Rinomina",
        "crates_btn_del": "Elimina",
        "crates_name_label": "Nome Crate:",
        "crates_rule_search": "Ricerca Testuale & Parole Chiave",
        "crates_rule_genre": "Generi Musicali (Logica OR)",
        "crates_rule_bpm": "BPM & Compatibilità Tempo",
        "crates_rule_key": "Chiave Armonica (Camelot Wheel)",
        "crates_rule_year": "Anno di Uscita",
        "crates_rule_quality": "Qualità Audio & Tag DJ",
        "crates_preview_title": "Anteprima Tracce Incluse",
        "crates_btn_export_m3u8": "Esporta M3U8 (Rekordbox / Serato / Traktor)",
        "crates_btn_reset_rules": "Ripristina Regole",
        "live_log_title": "Musicat — Console di Log Live & Diagnostica",
        "btn_export_support_logs": "📦 Esporta Log per Assistenza (.zip)",
        "btn_clear_log": "✕ Pulisci",
        "chk_auto_scroll": "Auto-scroll",
        "filter_all_levels": "Tutti i Livelli (DEBUG+)",
        "filter_info": "Solo INFO, WARNING, ERROR",
        "filter_warning": "Solo WARNING & ERROR",
        "filter_error": "Solo ERROR",
        "export_logs_title": "Salva Pacchetto Log per Assistenza",
        "export_logs_success_title": "Log Esportati con Successo",
        "export_logs_success_msg": "Il pacchetto di diagnostica è stato salvato in:\n{path}\n\nPuoi allegarlo alla richiesta di supporto o issue GitHub."
    },
    "en": {
        "app_name": "Musicat",
        "app_title": "Musicat — DJ Catalog & Smart Organizer",
        "nav_analysis": "Analysis / Home",
        "nav_library": "Library",
        "nav_mp3tag": "Tag Editor (Mp3tag)",
        "nav_crates": "Smart Crates",
        "nav_similar": "Find Similar",
        "nav_organizer": "Organize Files",
        "nav_settings": "Settings",
        "nav_scan": "📂 Scan",
        "nav_refresh": "🔄 Refresh",
        "nav_sidebar": "📁 Sidebar",
        "sidebar_title": "📁 LIBRARY & CRATES",
        "sidebar_smart_crates": "🎛️ SMART CRATES",
        "sidebar_folders": "📁 FOLDER TREE",
        "nav_trends": "🏠 Home Trends & Top Charts",
        "ready": "Ready",
        "library_status": "Library: {count} tracks ({hours}h {mins}m) | Database: {db}",
        "showing_tracks": "Showing {filtered} of {total} tracks",
        "found_tracks": "Found {count} tracks via {engine}",
        "tb_sidebar": "📁 Sidebar",
        "tb_scan": "📂 Scan Folder",
        "tb_refresh": "🔄 Refresh",
        "tb_mp3tag": "🏷️ Mp3tag Workspace",
        "tb_quick_tag": "✏️ Quick Tag",
        "tb_filename_tag": "🔀 Filename <-> Tag",
        "tb_reconcile": "⚖️ Reconciler & HD Cover",
        "tb_analyze": "🎵 Analyze BPM & Key",
        "tb_audio_quality": "🔊 Audio Quality",
        "tb_find_similar": "✨ Find Similar",
        "tb_organizer": "📦 Smart Organizer",
        "tb_settings": "⚙️ Settings",
        "tb_live_log": "📜 Live Log",
        "tb_stats": "📊 Stats",
        "col_id": "#",
        "col_has_cover": "Cover",
        "col_title": "Title",
        "col_artist": "Artist",
        "col_remixer": "Remixer",
        "col_bpm": "BPM",
        "col_camelot_key": "Camelot",
        "col_musical_key": "Key",
        "col_genre": "Genre",
        "col_year": "Year",
        "col_album": "Album",
        "col_label": "Label",
        "col_duration": "Time",
        "col_bitrate": "Bitrate",
        "col_energy_level": "Energy",
        "col_lufs": "LUFS",
        "col_true_peak": "True Peak",
        "col_audio_status": "Audio Quality",
        "col_filepath": "Path",
        "filter_search_placeholder": "🔍 Quick Search / {engine} (Ctrl+F)...",
        "filter_genre_placeholder": "Select / Search Genres (Ctrl+G)...",
        "filter_all_genres": "All Genres",
        "filter_one_genre": "1 Genre",
        "filter_multi_genres": "{count} Genres (OR)",
        "filter_clear_genres": "Clear Genre Selection",
        "filter_bpm": "BPM:",
        "filter_target_bpm": "Target",
        "filter_min_bpm": "Min",
        "filter_max_bpm": "Max",
        "filter_target_label": "Target:",
        "filter_min_label": "Min:",
        "filter_max_label": "Max:",
        "filter_key": "Key:",
        "filter_all_keys": "All Keys",
        "filter_harmonic_only": "Harmonic Only",
        "filter_wheel_btn": "🎡 Wheel",
        "filter_folder": "📁 Folder:",
        "filter_all_folders": "All Folders / Drives",
        "filter_cover": "🖼️ Cover:",
        "filter_all_covers": "All",
        "filter_with_cover": "With Cover",
        "filter_without_cover": "No Cover",
        "filter_year": "Year:",
        "filter_any_year": "Any Year",
        "filter_energy": "Energy:",
        "filter_any_energy": "⚡ Any Energy",
        "filter_warmup": "⚡ Warmup Low (1-2)",
        "filter_building": "⚡ Building Mid (3)",
        "filter_peak_time": "⚡ Peak Time (4-5)",
        "filter_rating": "Rating:",
        "filter_any_rating": "⭐ Any",
        "filter_audio": "Audio:",
        "filter_all_audio": "🔊 All Audio",
        "filter_clipping": "⚠️ Clipping (>0 dBTP)",
        "filter_low_vol": "🔈 Low Vol (<-18 LUFS)",
        "filter_brickwall": "🧱 Brickwall (LRA < 3)",
        "filter_problematic": "⚡ Problematic Tracks",
        "filter_conforme": "✅ Compliant (OK)",
        "filter_smart_crates": "📁 Smart Crates...",
        "filter_save_crate": "💾 Save Crate",
        "filter_export_m3u": "📤 Export M3U8",
        "filter_reset": "✕ Reset (ESC)",
        "player_no_track": "No track playing",
        "player_select_prompt": "Select a track to audition",
        "player_normalize": "⚡ Fix",
        "player_similar": "✨ Similar",
        "player_pitch": "Pitch: {val}",
        "player_show_in_folder": "📂 Show in folder",
        "ctx_play": "▶ Play in Mini-Player",
        "ctx_find_similar": "✨ Find Similar Tracks (Cosine & Library)...",
        "ctx_cut": "✂️ Cut Track(s) (Ctrl+X)",
        "ctx_copy": "📋 Copy Track(s) (Ctrl+C)",
        "ctx_paste": "📥 Paste Track(s) Here (Ctrl+V)",
        "ctx_mp3tag": "🏷️ Open in Mp3tag Workbench (Ctrl+T)...",
        "ctx_edit_tags": "✏️ Edit Tags (Batch)...",
        "ctx_reconcile": "⚖️ Reconcile Multi-Source Metadata & HD Cover...",
        "ctx_patterns": "🔀 Filename <-> Tag Patterns...",
        "ctx_analyze": "🎵 Calculate BPM & Camelot Key",
        "ctx_quality": "🔊 Audio Quality Diagnosis & Normalize...",
        "ctx_sorter": "📁 Organize & Dispatch to Folder...",
        "ctx_show_folder": "📂 Show in folder",
        "settings_title": "Musicat — System Preferences",
        "settings_tab_ui": "🎨  Graphics & UI",
        "settings_tab_audio": "🎵  Audio & libVLC",
        "settings_tab_perf": "⚡  Performance & Hardware",
        "settings_tab_scrapers": "🌐  Scrapers & API Keys",
        "settings_tab_accounts": "🌐  Accounts & Services",
        "settings_accounts_desc": "Connect your music accounts in one click using quick browser authentication.<br>Connected services allow access to playlists, playback history, preview audio streams, and complete metadata.",
        "settings_accounts_group": "Connected Accounts (Quick Browser Login)",
        "settings_dev_api_title": "🛠️ Developer Options / Custom API Keys & Manual Tokens",
        "settings_btn_connect": "Connect Account",
        "settings_btn_disconnect": "Disconnect",
        "nav_top_charts": "🔥  Top Charts",
        "folder_filter_applied": "Folder: {path} ({count} tracks)",
        "folder_no_audio": "No audio files found in directory: {path}",
        "auto_scan_complete": "Scan complete: {found} audio files indexed in '{folder}'",
        "scan_already_running": "A directory scan is already running...",
        "settings_tab_plugins": "🧩  Plugins & Extensions",
        "settings_lang_label": "Interface Language:",
        "settings_theme_label": "UI Theme:",
        "settings_dpi_label": "Display Scale (HiDPI Zoom):",
        "settings_font_size": "Table Font Size:",
        "settings_row_height": "Table Row Height (px):",
        "settings_visible_cols": "📋 Visible Columns in Track Table",
        "settings_btn_reset": "Restore Defaults",
        "settings_btn_cancel": "Cancel",
        "settings_btn_save": "Save & Apply",
        "settings_saved_msg": "Preferences saved successfully!",
        "similar_dialog_title": "✨ Similar Tracks & DJ Recommendations",
        "similar_tab_local": "Similar Tracks in Your Library",
        "similar_tab_discovery": "Online Discoveries & Missing Tracks",
        "similar_affinity_col": "Affinity",
        "similar_reasons_col": "Match Criteria",
        "similar_links_col": "Listen / Search",
        "similar_in_library": "✓ In Library",
        "similar_missing": "+ Missing",
        "trends_header": "🏠 Top Trends & Current DJ Charts",
        "trends_refresh": "🔄 Refresh Charts",
        "trends_search": "Search in charts...",
        "trends_listen": "▶ Listen",
        "trends_similar": "✨ Similar",
        "trends_cached_badge": "Local Cache",
        "trends_live_badge": "Live Spotify",
        "crates_workbench_title": "SMART CRATES WORKBENCH",
        "crates_workbench_sub": "Intelligent rules-based crate builder for DJ performance",
        "crates_btn_new": "+ New Crate",
        "crates_btn_save": "Save Rules",
        "crates_btn_export": "Export DJ Playlist",
        "crates_list_header": "Your Smart Crates",
        "crates_search_placeholder": "Search Crates...",
        "crates_btn_dup": "Duplicate",
        "crates_btn_ren": "Rename",
        "crates_btn_del": "Delete",
        "crates_name_label": "Crate Name:",
        "crates_rule_search": "Text Search & Keywords",
        "crates_rule_genre": "Music Genres (OR Logic)",
        "crates_rule_bpm": "BPM & Tempo Compatibility",
        "crates_rule_key": "Harmonic Key (Camelot Wheel)",
        "crates_rule_year": "Release Year",
        "crates_rule_quality": "Audio Quality & DJ Tags",
        "crates_preview_title": "Included Tracks Preview",
        "crates_btn_export_m3u8": "Export M3U8 (Rekordbox / Serato / Traktor)",
        "crates_btn_reset_rules": "Reset Rules",
        "live_log_title": "Musicat — Live System Log & Diagnostics",
        "btn_export_support_logs": "📦 Export Logs for Support (.zip)",
        "btn_clear_log": "✕ Clear",
        "chk_auto_scroll": "Auto-scroll",
        "filter_all_levels": "All Levels (DEBUG+)",
        "filter_info": "INFO, WARNING, ERROR only",
        "filter_warning": "WARNING & ERROR only",
        "filter_error": "ERROR only",
        "export_logs_title": "Save Support Diagnostics Bundle",
        "export_logs_success_title": "Logs Exported Successfully",
        "export_logs_success_msg": "The support diagnostic bundle was saved to:\n{path}\n\nYou can attach this file to a GitHub issue or support request."
    }
}


def detect_system_language() -> str:
    """Detects system language, defaulting to Italian if not English.

    Returns:
        str: 'it' or 'en'.
    """
    try:
        q_name = QLocale.system().name().lower()
        if q_name.startswith("en"):
            return "en"
        if q_name:
            return DEFAULT_LANGUAGE
    except Exception:
        pass

    try:
        sys_loc = (locale.getlocale()[0] or "").lower()
        if sys_loc.startswith("en"):
            return "en"
        if sys_loc:
            return DEFAULT_LANGUAGE
    except Exception:
        pass

    env_lang = (os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")).lower()
    if env_lang.startswith("en"):
        return "en"

    return DEFAULT_LANGUAGE


class I18n(QObject):
    """Central localization manager with Qt signal emission and translation caching."""

    language_changed = Signal(str)

    _instance: Optional["I18n"] = None
    _lock = threading.Lock()

    def __init__(self, initial_lang: Optional[str] = None) -> None:
        super().__init__()
        self._current_lang = initial_lang or DEFAULT_LANGUAGE
        self._translations: Dict[str, Dict[str, str]] = {}
        self._load_all_translations()

    @classmethod
    def get_instance(cls, initial_lang: Optional[str] = None, default_lang: Optional[str] = None) -> "I18n":
        """Singleton accessor for I18n."""
        lang = initial_lang or default_lang
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(lang)
            return cls._instance

    @property
    def language(self) -> str:
        """Returns active language code ('it' or 'en')."""
        return self._current_lang

    @property
    def current_language(self) -> str:
        """Returns active language code ('it' or 'en')."""
        return self._current_lang

    @property
    def available_languages(self) -> List[Tuple[str, str]]:
        """Returns list of (code, display_name)."""
        return list(SUPPORTED_LANGUAGES)

    def set_language(self, lang_code: str) -> bool:
        """Switches active language and emits language_changed signal."""
        code = lang_code.lower()[:2]
        if code not in [c for c, _ in SUPPORTED_LANGUAGES]:
            code = DEFAULT_LANGUAGE

        if code != self._current_lang:
            self._current_lang = code
            self.language_changed.emit(code)
            return True
        return False

    def _locate_locales_dir(self) -> Optional[Path]:
        """Locates external locales directory across dev and frozen environments."""
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "locales",
            Path.cwd() / "locales",
            PathResolver.get_data_dir() / "locales",
        ]
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.insert(0, Path(sys._MEIPASS) / "locales")

        for c in candidates:
            if c.exists() and c.is_dir():
                return c
        return None

    def _load_all_translations(self) -> None:
        """Loads translations from embedded dictionaries and overrides with external JSON files if present."""
        # 1. Base embedded dictionary
        for code, table in EMBEDDED_TRANSLATIONS.items():
            self._translations[code] = dict(table)

        # 2. Try loading external JSON files
        locales_dir = self._locate_locales_dir()
        if locales_dir:
            for code, _ in SUPPORTED_LANGUAGES:
                fpath = locales_dir / f"{code}.json"
                if fpath.exists():
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                self._translations.setdefault(code, {}).update(data)
                    except Exception:
                        pass

    def t(self, key: str, default: Optional[str] = None, **kwargs: Any) -> str:
        """Retrieves translated text for key in current language, formatting with kwargs."""
        lang_dict = self._translations.get(self._current_lang, {})
        val = lang_dict.get(key)

        if val is None:
            # Fallback to default language dictionary
            val = self._translations.get(DEFAULT_LANGUAGE, {}).get(key)

        if val is None:
            val = default if default is not None else key

        if kwargs:
            try:
                return val.format(**kwargs)
            except Exception:
                return val

        return val

    def _load_locale(self, code: str) -> Dict[str, str]:
        """Returns loaded translation dictionary for specified language code."""
        return self._translations.get(code, {})


def _t(key: str, default: Optional[str] = None, **kwargs: Any) -> str:
    """Global convenience translator."""
    return I18n.get_instance().t(key, default=default, **kwargs)


# Alias
tr = _t
