# 📋 Changelog

All notable changes to **Musicat** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)
[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)

---

## [1.1.0] - 2026-10-02

### 🚀 Major UI/UX Polish, Logging Suite, Code Documentation & Architectural Consolidation

#### ⚪ Default Light Theme & Minimalist Navigation
- **Light Theme Default:** Modern, high-contrast light theme (`#FFFFFF` / `#F8F9FA`, text `#212529`, accents `#0D6EFD`) set as the default on fresh start. Instant hot-switching to Dark Theme preserved in Settings.
- **Clean Modular Navbar:** Removed ambiguous single-action icons and fragmented header shortcuts. The top navbar now solely houses complete, clearly labeled navigation buttons:
  - `[Analisi / Home]`
  - `[Libreria]`
  - `[Tag Editor (Mp3tag)]`
  - `[Smart Crates]`
  - `[Trova Simili]`
  - `[Organizza File]`
  - `[Impostazioni]`
- **Startup Landing View:** Application now launches directly into the **Analysis / Home** view as the default startup screen.
- **Dedicated Smart Crates Workbench:** Extracted smart crate configuration from compressed main view into an independent, full-screen workbench (`src/gui/views/crates_view.py`) with visual rule builder and extended `.m3u8` playlist export.

#### 📜 Enterprise Logging Suite & Troubleshooting Tools
- **Zip-Compressed Rotating Handler (`ZipRotatingFileHandler`):**
  - Enforces a 20 MB file size limit on active log files (`musicat.log`).
  - Automatically rotates and compresses historical logs into `.zip` archives using `zipfile.ZIP_DEFLATED` (`musicat.log.1.zip`, ..., `musicat.log.10.zip`).
  - Retains the last 10 compressed archives, automatically purging older files.
- **Adaptive Log Paths:**
  - Portable mode (`portable.lock`): `./logs/` adjacent to the executable.
  - Standard mode: `%APPDATA%\Musicat\logs` on Windows or `~/Library/Application Support/Musicat/logs` on macOS.
- **Granular Domain Event Loggers (`src/core/logger.py`):**
  - **`log_scan`:** Tracks folder indexing, total files found, newly inserted, skipped files, and duration in milliseconds.
  - **`log_audio_engine`:** Records libVLC library initialization, file loads, play/pause/seek events, pitch bends, and decode errors.
  - **`log_tag_edit`:** Logs Mutagen tag write operations with pre/post JSON dumps, modified field diff inspection, and corrupted ID3 header interception.
  - **`log_http`:** Measures round-trip HTTP latency via `time.perf_counter()`, records request URLs, search parameters, response status codes, and exception details across Beatport, Spotify, Chosic/Cosine, Discogs, and MusicBrainz.
  - **`log_file_op`:** Tracks physical file transfers (`SRC -> DEST`), error states, and collision strategies (`RENAME`, `OVERWRITE`, `SKIP`).
- **Live GUI Log Console:**
  - Integrated level filter combobox (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
  - Auto-scroll toggle and instant log clearing.
  - **"Esporta Log per Assistenza (.zip)"** button producing an all-in-one diagnostic bundle containing logs, anonymized hardware metrics, database health statistics, and sanitized configurations.

#### 🧠 In-Line Algorithmic Documentation & Sphinx/Google Docstrings
- **Acoustic Analyzer (`src/audio/analyzer.py`):** Comprehensive step-by-step documentation detailing STFT windowing, spectral flux onset autocorrelation, parabolic sub-sample peak interpolation, 12-semitone chromagram binning via continuous MIDI note formulas, and Pearson correlation against Krumhansl-Schmuckler tonality profiles.
- **Audio Quality Analyzer (`src/plugins/quality_analyzer/analyzer.py`):** Mathematical and physical background on ITU-R BS.1770-4 Annex 2, 4x polyphase FIR resampling for inter-sample True Peak detection, digital flat-top clipping detection, and EBU R128 K-weighting filters with relative gating.
- **Metadata Reconciler (`src/scrapers/reconciler.py`):** Documented priority hierarchy (Beatport/Traxsource for DJ metadata, Discogs for catalogs, MusicBrainz for ISRCs, Apple Music for HD covers), frequency-based majority voting, and heuristic tie-breakers.
- **Everything MFT Search (`src/core/everything_search.py`):** Documented Voidtools Everything IPC mechanism via `Everything64.dll`, Win32 `WM_COPYDATA` messages, and ctypes struct/function bindings.

#### 🧪 Verification & Test Suite
- Full test suite expanded to **130 unit tests**, passing with 100% success rate (`Ran 130 tests in 8.8s OK`).

---

## [1.0.0] - 2026-10-01

### 🚀 Initial Public Release

Welcome to the first official release of **Musicat**, the ultimate desktop music cataloger, DJ tag editor, and acoustic smart organizer built for massive digital libraries (50,000+ tracks).

### ✨ Core Features & Enhancements

#### 🎛️ Dual-Mode Installer & Zero-Installation Portability
- **Inno Setup Script (`installer/setup.iss`):** Single unified `Musicat-Setup.exe` with interactive mode selection:
  - **Standard Mode:** Installs into `Program Files`, adds Start Menu/Desktop shortcuts, and isolates data in `%APPDATA%\Musicat`.
  - **Portable Mode:** Extracts into any folder/USB drive, creates `portable.lock`, and stores all databases, configurations, and logs locally in `./musicat_data/`.
- **Volume Serial Number (VSN) Resolver:** Windows drive-letter independent path translation (`[VOL:XXXXXXXX]`) ensuring external USB SSD libraries never break when letters change.

#### ⚡ Voidtools Everything SDK & SQLite FTS5 Fallback
- Direct IPC queries via `Everything64.dll` into the NTFS Master File Table (MFT) for sub-millisecond search across drives with 100,000+ files.
- Transparent, automatic fallback to local SQLite FTS5 (Full-Text Search) with insert/update/delete triggers.

#### 🎵 Universal libVLC Player & DJ Pitch Control
- Native libVLC audio engine supporting universal codecs without external filters: **MP3, WAV, FLAC, AIFF, M4A, OGG, ALAC, OPUS**.
- **DJ Pitch / Tempo Slider:** Real-time speed and pitch bending ($\pm 8.0\%$) with zero-reset detent.
- Interactive waveform peak scrubbing canvas with click-to-seek and continuous looping.

#### 🏷️ Mp3tag-Grade Metadata Engine & Pattern Translations
- Unified tagging across ID3v2.3/2.4, Vorbis Comments, and MP4 atoms with DJ-specific tags (`BPM`, `INITIALKEY`/Camelot, `GENRE`, `LABEL`, `REMIXER`, `ENERGYLEVEL`, `COMMENT`).
- Multi-selection batch editing with `<keep existing>` protection.
- Bidirectional pattern conversions:
  - *Filename ➔ Tag:* `%artist% - %title% (%bpm% BPM)`
  - *Tag ➔ Filename:* Mass physical renaming based on database tags.
  - *Tag ➔ Tag:* Copy, swap, or merge fields.

#### 🌐 Multi-Source Scraping & Discrepancy Reconciliation
- Dedicated club/electronic scrapers: **Beatport**, **Traxsource**, **Discogs**, **MusicBrainz**.
- Social/remix web discovery: **SoundCloud**, **YouTube Music**, **Hypeddit**, **Remix.audio**.
- **Metadata Reconciler Engine:** Side-by-side discrepancy matrix comparing all discovered candidates, detecting conflicting fields, and offering field-by-field selective checkboxes for precision auto-tagging.

#### 🖼️ Studio HD Cover Art Discovery (up to 3000x3000px)
- Lossless studio artwork extraction via Apple Music / iTunes CDN upscaling (`1400x1400` to `3000x3000px`), Beatport GeoMedia, and Traxsource.
- Tag injection (`APIC` for ID3, Picture block for FLAC, `covr` for MP4/M4A) with optional local `cover.jpg` saving.

#### 📊 High-Performance Parallel Acoustic Engine & L1 RAM Cache
- **Hardware-Aware Multiprocessing Pool (`src/audio/parallel_analyzer.py`):** Dynamic worker allocation saturated across logical CPU cores (`os.cpu_count() - 1`), with batch scheduling (20-50 tracks) to minimize inter-process communication overhead.
- **Accelerated Streaming Audio Worker (`src/audio/worker.py`):**
  - Fast partial-window streaming read (central 60s drop window at 22,050 Hz mono) skipping quiet intro/outro sections.
  - High-energy segment extraction for Camelot Key detection, cutting STFT CPU consumption by ~80%.
  - Downsampled peak envelope generation for instant waveform rendering.
- **In-Memory RAM Cache System (`src/core/memory_cache.py`):**
  - **`AnalysisMemoryCache`:** SQLite RAM buffer (`:memory:`) staging raw DSP results with periodic/threshold-based background flush to disk, eliminating physical SSD/USB drive wear.
  - **`WaveformMemoryCache`:** Thread-safe LRU cache with configurable size limit (e.g. 512MB / 1GB / 2GB) providing instant (<0.1ms) waveform loading during DJ track audition without reading physical files.

#### 📁 Smart Organizer & Inbound File Dispatcher
- Dynamic folder tree generation based on customizable rules: `{Genre}/BPM {bpm_range}/{Camelot} - {Artist} - {Title}.ext`.
- Mandatory **Dry Run Mode** simulating destination paths, collision detection (`Auto-Rename (1)`, `Overwrite`, `Skip`), and error checking before physical disk operations.

#### 🎛️ Live DJ Crate & Advanced Filtering Engine (<15ms Latency)
- **Live Multi-Criteria Filter Bar:** Keyboard-controllable console bar integrating Multi-Genre autocomplete (OR), Target BPM with `± %` tolerance presets (`±2%`, `±4%`, `±6%`, `±8%`), decade selector, and energy level filters.
- **Harmonic Mixing Assistant (`src/audio/camelot.py`):** Visual Camelot Wheel dialog (`1A`–`12B`) with harmonic matching (`±1`, relative major/minor, `+2` energy boost, `+7` semitone lift).
- **In-Memory RAM Query Acceleration (`src/core/filter_engine.py`):** Microsecond in-memory evaluation cache for instantaneous responses during live performance with active audio playback.
- **Dynamic Smart Crates & Universal M3U8 Export:** Save and auto-update custom filter combinations into SQLite `smart_crates` and export playlists compatible with Rekordbox, Traktor, Serato, and Engine DJ.
- **DJ Console Keybindings:** Instant access via `Ctrl+F` (Search), `Ctrl+G` (Genre), `Ctrl+B` (BPM), `Ctrl+K` (Camelot Wheel), `Esc` (Instant Reset), and `Enter` (Deck Load).

#### 🍏 Cross-Platform macOS Support & Multi-OS CI/CD Pipeline
- **Unified Fast Search Engine (`src/core/search_factory.py`):**
  - **macOS:** Native Spotlight Metadata Services (`mdfind`) APFS driver (`src/core/search_mac.py`) filtering `kMDItemContentTypeTree == 'public.audio'`.
  - **Windows:** Voidtools Everything SDK IPC querying NTFS Master File Table.
  - **Fallback:** Automatic transparent fallback to SQLite FTS5 across both platforms with dynamic UI engine badges (`[EVERYTHING MFT]`, `[SPOTLIGHT APFS]`, `[SQLITE FTS5]`).
- **Cross-Platform Audio Engine (`src/player/vlc_engine.py`):** Dynamic discovery of `libvlc.dylib` across `.app` bundles, `/Applications/VLC.app`, and Homebrew paths (`/opt/homebrew` and `/usr/local`). Full support for 32-bit float WAV, ALAC, AIFF, FLAC, and AAC on Apple Silicon (ARM64) and Intel Macs.
- **Cross-Platform Path Resolver (`src/core/path_resolver.py`):** Universal support for Windows Volume Serial Numbers (`[VOL:XXXXXXXX]`) and macOS mount points (`/Volumes/<DiskName>/...`), standard application data directories (`%APPDATA%` on Windows, `~/Library/Application Support/Musicat` on macOS), and portable USB SSD drives switching between Windows and Mac.
- **Multi-OS Release Pipeline (`.github/workflows/build-release.yml` & `release.yml`):** Automated GitHub Actions build matrix simultaneously generating:
  - `Musicat-Setup-Windows-x64.exe` (Inno Setup dual-mode installer)
  - `Musicat-Windows-Portable.zip` (standalone Windows portable archive)
  - `Musicat-macOS.dmg` (macOS Drag & Drop Applications installer DMG)
  - `Musicat-macOS-Portable.zip` (standalone macOS portable bundle)

#### 🌐 Bilingual Localization (IT/EN)
- **Localization Engine (`src/core/i18n.py`):** Full Italian (default) and English (secondary) translations loaded from `locales/it.json` and `locales/en.json` with embedded fallback safety.
- **Hot Language Switching:** Dynamic live retranslation across all widgets without restarting the application.
- **Bilingual Documentation:** Dual-language comprehensive guides in `README.md` (Italian), `README_EN.md` (English), and `ARCHITECTURE.md`.
