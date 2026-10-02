# 📋 Changelog

All notable changes to **Musicat** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Interactive Telemetry Dialog (`src/gui/analysis_dialog.py`):** Dedicated non-blocking GUI dialog with `QThread` bridge, reactive progress bar, real-time throughput meter (`tracce/sec`), CPU cores allocation slider, RAM cache size slider, ETA counter, and Start/Pause/Cancel controls.

#### 📁 Smart Organizer & Inbound File Dispatcher
- Dynamic folder tree generation based on customizable rules: `{Genre}/BPM {bpm_range}/{Camelot} - {Artist} - {Title}.ext`.
- Mandatory **Dry Run Mode** simulating destination paths, collision detection (`Auto-Rename (1)`, `Overwrite`, `Skip`), and error checking before physical disk operations.

#### 🎛️ Live DJ Crate & Advanced Filtering Engine (<15ms Latency)
- **Live Multi-Criteria Filter Bar:** Keyboard-controllable console bar integrating Multi-Genre autocomplete (OR), Target BPM with `± %` tolerance presets (`±2%`, `±4%`, `±6%`, `±8%`), decade selector, and energy level filters.
- **Harmonic Mixing Assistant (`src/audio/camelot.py`):** Visual Camelot Wheel dialog (`1A`–`12B`) with harmonic matching (`±1`, relative major/minor, `+2` energy boost, `+7` semitone lift).
- **In-Memory RAM Query Acceleration (`src/core/filter_engine.py`):** Microsecond in-memory evaluation cache for instantaneous responses during live performance with active audio playback.
- **Dynamic Smart Crates & Universal M3U8 Export:** Save and auto-update custom filter combinations into SQLite `smart_crates` and export playlists compatible with Rekordbox, Traktor, Serato, and Engine DJ.
- **DJ Console Keybindings:** Instant access via `Ctrl+F` (Search), `Ctrl+G` (Genre), `Ctrl+B` (BPM), `Ctrl+K` (Camelot Wheel), `Esc` (Instant Reset), and `Enter` (Deck Load).

#### 📜 Structured Logging & Live Console
- Multi-level logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`) with automatic 20MB file rotation and gzip (`.gz`) archiving.
- Live Log console dock (`Ctrl+L`) in the GUI for monitoring background scanner and scraper operations.

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

#### ⚙️ Settings Architecture, File Management & Mp3tag Workspace
- **Modular Preferences Dialog (`src/gui/settings_dialog.py`):** Sidebar navigation across 5 categories: UI/Theme, Audio/libVLC, Performance/GPU, Scrapers/Tokens, Plugins.
- **Physical File Operations (`src/core/file_manager.py`):** OS-level Cut/Copy/Paste operations synchronized automatically with the SQLite library database.
- **Dedicated Mp3tag Workbench (`src/gui/mp3tag_workspace.py`):** Full-screen table editor for inline cell edits, multi-track batch modification, and album art injection.
- **Hardware Acceleration Telemetry (`src/core/gpu_detector.py`):** GPU detection badge (NVIDIA CUDA, Apple Metal, AMD ROCm, Direct3D).

#### 🔊 Audio Quality Normalizer, Clipping Detector & Loudnorm Plugin
- **Plugin Architecture (`src/plugins/quality_analyzer/`):** Extensible plugin architecture with schema discovery and dynamic activation.
- **Acoustic Standards (ITU-R BS.1770-4 / EBU R128):** Integrated Loudness (LUFS), True Peak (dBTP with 4x oversampling), and Loudness Range (LRA).
- **Quality Diagnostics Modal (`src/gui/views/quality_view.py`):** Visual loudness meters, clipping warnings, and non-destructive ReplayGain or physical FFmpeg two-pass normalization.

#### 🏠 Smart Recommendations, Spotify Trends Home & Breadcrumb Navigation
- **Home Dashboard (`src/gui/views/home_view.py`):** Live Spotify trending charts with local 24h caching and instant library ownership check (`✓ In Library` vs `+ Missing`).
- **Acoustic Similarity Engine (`src/scrapers/similarity_engine.py`):** Cosine similarity lookup via Cosine.club / Chosic / Last.fm with local library matching.
- **Breadcrumb Path Bar (`BreadcrumbBar`):** Interactive folder breadcrumbs in the mini-player for 1-click filtering of parent folders.

#### 🌐 Bilingual Localization (IT/EN) & Release Pipeline
- **Localization Engine (`src/core/i18n.py`):** Full Italian (default) and English (secondary) translations loaded from `locales/it.json` and `locales/en.json` with embedded fallback safety.
- **Hot Language Switching:** Dynamic live retranslation across all widgets without restarting the application.
- **Bilingual Documentation:** Dual-language comprehensive guides in `README.md` (Italian), `README_EN.md` (English), and `ARCHITECTURE.md`.

