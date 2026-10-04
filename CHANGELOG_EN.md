# 📋 Changelog

All notable changes to **Musicat** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)
[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)

---

## [1.4.0] - 2026-10-04

### 🚀 Visual Hardware Monitor (Dynamic Progress Bars), Advanced Mp3tag Toolset (Auto-Numbering & Live Patterns), Unified Dynamic Genre ComboBox & Fallback "Vario"

#### 📊 Visual Hardware Monitor in Status Bar
- **Integrated Dual Progress Bars (`HardwareProgressBar`):** Replaced plain status text with two compact horizontal progress bars for CPU and RAM.
- **Dynamic 3-Stage Load Coloring:**
  - **Green (`#28A745`):** Normal load (0% - 60%);
  - **Yellow / Orange (`#FD7E14`):** Medium-high load (61% - 84%);
  - **Red (`#DC3545`):** High stress / saturation (85% - 100%).
- **Centered Text & Asynchronous Polling:** Clean centered telemetry (`CPU XX%`, `RAM X.X/YY GB`) updated asynchronously every 1.5 seconds (1500 ms) with seamless light/dark theme adaptation.

#### 🏷️ Mp3tag Workspace: Advanced Tagging Toolset
- **Track Numbering Wizard (`TrackNumberingWizardDialog`):**
  - Dedicated *"🔢 Renumber Tracks..."* button;
  - Sequential track numbering with optional leading zeros (`01, 02...`);
  - Total track count denominator support (`01/12`);
  - Counter reset per folder or per album;
  - Real-time tabular preview before applying changes.
- **Pattern Converters with Live Tabular Preview:**
  - **Filename ➔ Tag (`FilenameToTagDialog`):** Interactive dialog with presets, quick token buttons (`%artist%`, `%title%`, `%album%`, `%track%`, `%year%`, `%bpm%`, `%genre%`), and live preview table.
  - **Tag ➔ Filename (`TagToFilenameDialog`):** Mass disk renaming with real-time target status indicators and conflict detection.
  - **`$num(%track%,2)` Token Support:** Advanced token parsing and padding generation in `PatternEngine`.
- **Quick Case Conversion Actions:**
  - One-click shortcuts on toolbar and left panel for *Title Case*, *UPPERCASE*, and *lowercase*.

#### 🎛️ Unified Dynamic Genre ComboBox & Fallback "Vario"
- **Editable Unified Control:** Merged separate text search and dropdown into a single editable `QComboBox` with autocompletion (`setEditable(True)`, `setInsertPolicy(NoInsert)`).
- **Dynamic Alphabetical List:** Starts with `🏷️ Tutti i Generi`, followed by all unique database genres sorted alphabetically, auto-refreshed after each scan.
- **Fallback "Vario":** Untagged tracks (empty or null ID3 genre) are grouped under `"Vario"`, displayed in the table as `"Vario"` and accurately matched by the in-memory and SQLite filter engines.

---

## [1.3.0] - 2026-10-04

### 🚀 Embedded Workspaces (QStackedWidget), Left Drive Explorer, Taskbar Icon Fix & Selection Synchronization

#### 🖥️ Embedded Workspaces in Main Window (Zero Modal Popups)
- **6 Integrated Views (`QStackedWidget`):** Core application tools are now directly embedded in the central window area without flying popup dialogs:
  - **Index 0:** Analysis / Home (`HomeTrendsView`)
  - **Index 1:** DJ Library (`library_container` with table, live filter bar, and left drive tree)
  - **Index 2:** Tag Editor (`Mp3tagWorkspaceWindow` embedded in-app)
  - **Index 3:** Smart Crates (`SmartCratesView`)
  - **Index 4:** Find Similar (`SimilarTracksView` with integrated harmonic affinity and web discovery)
  - **Index 5:** File Organizer (`OrganizerView` embedded in-app)
- **Seamless Navigation:** Switch instantly across workspaces via top navbar buttons without breaking user flow.

#### 🔄 Intelligent Cross-Workspace State Synchronization
- **Selection Forwarding:** Selecting tracks in the library table automatically populates *Tag Editor (Mp3tag)*, *Find Similar*, or *File Organizer* upon switching.
- **Guided Library Return:** Embedded workspaces feature clean back navigation buttons (`◀ Torna alla Libreria`) to return to the library while persisting database updates.

#### 🗂️ Filesystem Explorer / Drive Tree Moved to Left
- **Standard DJ/DAW Two-Pane Layout:** The folder and drive tree navigator has been moved to the **left** of the track table, featuring a collapsible header (`◀` / `▶`) and smooth splitter resizing.

#### 🖼️ Windows Taskbar Icon Fix (Cross-PC & Portable)
- **Explicit AppUserModelID:** Process registered with `ilred89.musicat.djcataloger.app.1.0` in `main.py` before `QApplication` instantiation.
- **Windows Icon Format Priority:** Fixed `PathResolver.get_icon_path()` on Windows to prioritize native `assets/icon.ico` and `assets/icon.png` over Apple `.icns` files, ensuring clean taskbar icons on portable devices and other PCs.

#### 🎨 Clean Navbar & Unified Button States
- **Active Workspace Highlighting:** All 6 module buttons now feature uniform active state highlighting (`btn_active` blue with white text) vs inactive state (`btn_inactive`).
- **Keyboard Shortcuts:** Direct navigation shortcuts `Alt+1` through `Alt+6` for all 6 workspaces.

#### 🛠️ SQLite Deadlock Resolution in File Manager
- **Cursor & Transaction Cleanup:** All SQLite cursor operations in `MusicFileManager` are wrapped in strict `try...finally` blocks, preventing hangs and resource locks during file copy/paste.

---

## [1.2.0] - 2026-10-04

### 🚀 Column Header Context Menu, 2-Row Filter Bar, Multi-Platform Trends, Discogs Priority & 80% RAM Allocation

#### 🎛️ Column Context Menu & Width Persistence
- **Header Context Menu:** Right-clicking any column header displays a popup menu with checkable items for all columns to show/hide in real time.
- **Automatic Persistence:** Column resizing (`ui.column_widths`) and visibility (`ui.visible_columns`) are persisted directly to `config.json` and restored on startup.
- **Settings Streamlined:** Removed redundant column checkboxes from Settings dialog, replaced by an informative help card.

#### ⚪ Light Theme Sanitization & GPU Card Fix
- **Complete Dark Theme Residual Purge:** Cleaned Settings sidebar, tabs, and sub-pages to clean `#F8F9FA` / `#FFFFFF` with `#DEE2E6` borders and `#212529` text.
- **Home/Analyze Cards:** Categorization cards updated with crisp white background (`#FFFFFF`), subtle border (`#D0D7DE`), 8px radius, and smooth hover state (`#F8F9FA`, border `#0D6EFD`).
- **GPU Hardware Acceleration Frame:** Converted from dark background to clean white styling with green hardware badge and readable text.

#### 🧠 Dynamic System RAM Allocation (up to 80%)
- **2 GB Limit Removed:** Eradicated the legacy 2 GB cap on cache memory.
- **Native Hardware Detection:** Accurately reads total installed system RAM (`GlobalMemoryStatusEx` on Windows, `psutil`).
- **Dynamic Slider:** Ranges from 512 MB up to **80% of total installed physical RAM** with live feedback label: `Allocated: X.X GB / Y.Y GB total`.

#### 🌐 Expanded Scrapers & API Credentials
- **Multi-Service Credentials:** Added dedicated inputs for Spotify, SoundCloud, YouTube Data API v3, Discogs (User-Agent + Token), and Beatport.
- **Live Connection Test:** Each service features a "Test Connection" button providing instantaneous green/red visual validation.

#### 💿 Discogs Primary Metadata Authority
- **Enhanced Discogs Parser:** Advanced extraction of formats (Vinyl/Digital), catalog numbers (`catno`), and primary record labels.
- **Reconciliation Hierarchy:** Discogs elevated to top authority priority for Year, Label, Catalog Number, Format, and Artist.
- **Default Scraper:** Discogs preset as primary choice in scraper dialog.

#### 📈 Multi-Platform Trends Dashboard
- **Platform Tabs:** Dedicated tabs for `Top Spotify`, `Top SoundCloud / Hype`, and `Top Beatport / Discogs`.
- **Source-Specific Categories:** Dynamically populated musical genres matching each platform's catalog.
- **Offline Datasets & Library Cross-Check:** Rich offline fallbacks and visual badge for tracks already found in the user's local collection.

#### 🎚️ Two-Row Live DJ Filter Bar
- **Row 1 (Library & Search):** Search query with engine indicator, folder/drive selector, multi-genre dropdown (OR logic), cover toggle, and reset ESC button.
- **Row 2 (Acoustic Parameters):**
  - Expanded BPM target with pitch presets (`±2%`, `±4%`, `±6%`, `±8%`) and min/max inputs.
  - Camelot Key selector with full text visibility without truncation, Harmonic Mix checkbox, and Camelot Wheel modal button.
  - Decade/Year, Audio Quality filter, DJ tag badges, and Smart Crates quick export.

#### ❓ Smart Crates Integrated Guide & Tooltips
- **Interactive Help Modal:** New `"❓ User Guide"` button opening `SmartCratesHelpDialog` explaining AND/OR logic and console-ready DJ presets (*Warm-up*, *Peak Time*, *Classic House*, *Harmonic Mixes*).
- **Comprehensive Tooltips:** Added descriptive hints across all crate rules and actions.

#### 🧭 Emoji Navbar Icons & Stability Hardening
- **Representative Icons:** Updated 7 navbar buttons (`[🏠 Home]`, `[📁 Library]`, `[🏷️ Mp3tag]`, `[📦 Smart Crates]`, `[🔍 Similar]`, `[📂 Organize]`, `[⚙️ Settings]`).
- **Crash Prevention:** Installed global exception hook (`sys.excepthook`) and hardened genre navigation when library is empty.
- **Test Suite:** 140 of 140 unit tests passing (100% OK in 8.9s).

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

#### 🎛️ Library Table Column Management & Real System Hardware Monitoring
- **Right-Click Column Selection:** Added header context menu (`horizontalHeader`) enabling users to selectively toggle visibility across all 19 columns (`#`, `Cover`, `Title`, `Artist`, `Remixer`, `BPM`, `Camelot`, `Key`, `Genre`, `Year`, `Album`, `Label`, `Duration`, `Bitrate`, `Energy`, `LUFS`, `True Peak`, `Audio Quality`, `Path`).
- **Persistent Column Configuration:** Column choices are permanently saved to `config.json` (`ui.visible_columns` and `ui.custom_columns_active`), preserved across reboots and window resizing with "Show All Columns" and "Reset Default Columns" quick actions.
- **True System RAM Telemetry:** Removed artificial 2 GB divisor (which was strictly the SQLite cache ceiling); integrated native hardware querying (`GlobalMemoryStatusEx` on Windows, `sysctl` on macOS) reporting total installed system memory (e.g. `RAM: 283 MB / 24 GB`) with informative tooltip highlighting unlimited 64-bit memory capability.
- **Light Theme BreadcrumbBar & MiniPlayer Fix:** Eliminated persistent dark strip below the player: breadcrumb filesystem trail dynamically reflects active theme (`#f8f9fa` in Light Theme).
- **Native macOS Icon & Windows Taskbar Icon:** Generated 10-tier `assets/icon.icns` for macOS PyInstaller app bundle and configured explicit Windows `AppUserModelID` (`ilred89.musicat.djcataloger.1.0`).

#### 🧪 Verification & Test Suite
- Full test suite expanded to **132 unit tests**, passing with 100% success rate (`Ran 132 tests in 9.5s OK`).

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
