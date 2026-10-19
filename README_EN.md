<div align="center">
  <img src="assets/icon.png" width="128" height="128" alt="Musicat Icon" />
  <h1>Musicat</h1>
  <p>
    <strong>The Universal DJ Music Catalog, Mp3tag-Grade Metadata Workbench &amp; Acoustic Smart Organizer.</strong><br>
    <em>Engineered specifically for DJs, electronic music collectors, and sound archivists managing massive libraries (50,000+ tracks) across external SSDs and local storage.</em>
  </p>
</div>

<p align="center">
  <a href="README_EN.md"><img src="https://img.shields.io/badge/Language-English-blue.svg" alt="Language: English"></a>
  <a href="README.md"><img src="https://img.shields.io/badge/Lingua-Italiano-green.svg" alt="Lingua: Italiano"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python Version"></a>
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11%20x64%20%7C%20macOS%20Universal-brightgreen.svg" alt="Platform">
  <img src="https://img.shields.io/badge/tests-188%20passing-brightgreen.svg" alt="Test Suite">
  <a href="https://github.com/IlRed89/Musicat"><img src="https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg" alt="Repository"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-purple.svg" alt="License"></a>
</p>

---

## 🌟 Overview & Vision

Managing 50,000+ digital music tracks on high-capacity external drives introduces severe challenges for modern DJs and collectors:
- Operating system drive letters and mount points shuffle when switching USB ports or migrating between **Windows** and **macOS**, breaking standard software databases.
- Traditional DJ software (Rekordbox, Traktor, Serato, Engine DJ) lacks powerful bulk tag editing, studio cover retrieval, and deep metadata reconciliation.
- Generic tag editors (like Mp3tag) lack acoustic DSP analysis, live DJ Camelot harmonic filtering, audio quality diagnostics, and Spotify trend cross-checking.

**Musicat** unifies all these requirements into a modern, high-contrast light desktop workstation (with optional dark mode) available natively for **Windows (10/11 x64)** and **macOS (Apple Silicon M-Series + Intel x64)**.

---

## 🚀 Key Functional Modules

```
+----------------------------------------------------------------------------------------------------+
|                                              MUSICAT                                               |
+----------------------------------------------------------------------------------------------------+
| [📁 Library]   | [🔥 Charts]     | [🏷️ Mp3tag]     | [🔍 Similar]    | [📂 Organize]  | [📦 Crates]  [⚙️] |
| - Max Startup  | - Multi-Platform| - Number Wizard | - Cosine.club   | - In-App Stack | - Rule Guide |      |
| - Autofit +16  | - Stream Preview| - Pattern %tag% | - Web Vectors   | - Collision    | - Right Dock |      |
| - Drag & Drop  | - Reconcile     | - $num() Live   | - Key & BPM     | - Dry Run      | - Drag/Drop  |      |
+----------------------------------------------------------------------------------------------------+
|           Unified Search Engine (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)         |
+----------------------------------------------------------------------------------------------------+
|                    libVLC Audio Engine with +/-8% Pitch Bending & Waveform Scrubbing               |
+----------------------------------------------------------------------------------------------------+
|        Status Bar with Dynamic Hardware Resource Progress Bars (CPU & RAM Thresholds)              |
+----------------------------------------------------------------------------------------------------+
|      DSP Audio Engine (Spotify Pedalboard, FFmpeg libavfilter & JUCE VST3 Plugin Bridge)           |
+----------------------------------------------------------------------------------------------------+
|               Cross-Platform Path Resolver ([VOL:XXXXXXXX] & portable.lock Drive Migration)        |
+----------------------------------------------------------------------------------------------------+
```

### 1. ⚪ Default Fullscreen Maximized Boot, Embedded Workspaces & Streamlined Navbar
- **Default Fullscreen / Maximized Boot:** Automatically boots maximized on first launch (`window.showMaximized()`), ensuring optimal screen real estate utilization for DJ workflow.
- **6 Embedded Workspaces Architecture (`QStackedWidget`):** Key modules are integrated directly into the main window view stack without disruptive modal popups:
  - **Position 1: [📁 Library] (Default Startup View)**: High-performance DJ catalog with 2-row filter bar, automatic column content autofit (+16px safety margin), interactive drag & drop column reordering, and drive tree explorer.
  - **Position 2: [🔥 Top Charts]**: Multi-platform charts dashboard across Spotify/SoundCloud/Beatport with 30-second in-app audio preview streaming in libVLC and direct route to Similar Tracks.
  - **Position 3: [🏷️ Tag Editor (Mp3tag)]**: Spreadsheet tagging workspace with track numbering wizard, pattern engine, and case transformations.
  - **Position 4: [🔍 Find Similar]**: Local acoustic vector matching and online discovery on Cosine.club / Chosic with harmonic key transitions and context-safe similar button routing.
  - **Position 5: [📂 Organize Files]**: Physical disk file dispatcher with collision avoidance and dry-run preview.
  - **Position 6: [📦 Smart Crates]**: Positioned at the far right of the top navigation bar right before Settings, offering rule-based crate building and extended M3U8 playlist export.
  - **Position 7: [⚙️ Settings]**: General preferences, audio DSP options, performance, scrapers, and quick browser account authentication.
- **High-Contrast Light Theme:** Modern crisp palette (`#FFFFFF` / `#F8F9FA`, text `#212529`, accents `#0D6EFD`) with instant Dark Mode switch available in Settings.
- **Native Taskbar Icon:** Windows `AppUserModelID` registration ensures high-resolution application branding on the taskbar even when running portably from USB drives.

### 2. 📊 Visual Hardware Monitor in Status Bar (Dynamic Progress Bars)
- **Embedded Graphical Progress Bars:** Replaced plain monochrome text with two sleek, horizontal `QProgressBar` widgets for CPU and RAM.
- **Dynamic Load Color Thresholds:**
  - **Green (`#28A745`):** Optimal and smooth operation (0% – 60%);
  - **Yellow / Orange (`#FD7E14`):** Moderate to heavy workload (61% – 84%);
  - **Red (`#DC3545`):** High stress or memory/compute saturation (85% – 100%).
- **64-bit Memory Transparency:** No artificial 2 GB memory ceilings; Musicat queries total physical installed RAM and reports `RAM X.X / YY GB` asynchronously every 1.5 seconds.

### 3. 🗂️ Dynamic Column Content Autofit, Drag & Drop Reordering & 2-Row Filters
- **Dynamic Column Content Autofit (+16px Safety Margin):** On library load, refresh, and folder scan completion, all table columns automatically adapt to fit the longest content (`resizeColumnsToContents()`), with a 16px horizontal safety margin to prevent ellipsis truncation (...) on long titles, artists, albums, or paths. Users retain full freedom to resize and drag & drop columns without resets on selection or scrolling.
- **Collapsible Drive & Folder Explorer:** Integrated left sidebar (`QFileSystemModel`) in the Library view offering instant volume discovery and 1-click directory filtering.
- **Interactive Drag & Drop Column Reordering:** Movable table header (`setSectionsMovable(True)`, `setDragEnabled(True)`) for instant drag & drop sequence customization.
- **Hexadecimal State Persistence:** Column order, visibility, and widths are serialized via `saveState()` into hex strings in `config.json` (`ui.header_state`), restored automatically at startup via `restoreState()`.
- **Streamlined Default DJ Table:** Internal calculation fields (`energy_level`, `lufs`, `true_peak`, `audio_status`) are hidden by default, providing clean layout across the 12 core DJ columns. Right-clicking any column header allows toggling any of the 19 columns with a single click.
- **Dedicated Toolbar Button `[⚡ Analizza Selezionate]`:** Launches asynchronous background processing (`AsyncAnalysisWorker`) for acoustic DSP, metadata enrichment, and tag persistence with discrete status bar progress and instant cancellation.
- **Dynamic Genre ComboBox with Chevron Indicator:** Strictly populated from actual SQLite records (`SELECT DISTINCT genre FROM tracks`) with `"🏷️ Tutti i Generi"` at the top, alphabetical sorting, and `"Vario"` at the bottom. Features explicit CSS subcontrols (`QComboBox::drop-down` and `QComboBox::down-arrow`) for visible arrows in both light and dark themes.
- **Two-Row Ergonomic Filter Bar (<15ms):** Target BPM with fine steppers (`±2%`, `±4%`, `±6%`, `±8%`), 12-position interactive Camelot Wheel with harmonic paths ($\pm 1$, Relative Key, $+2$ Energy Boost, $+7$ Semitone Lift), decade, energy, and rating filters.

### 4. 🏷️ Advanced Mp3tag Workspace: Track Numbering Wizard & Live Patterns
- **Track Numbering Wizard (`TrackNumberingWizardDialog`):**
  - Sequential numbering with customizable starting index;
  - Optional leading-zero padding (`01, 02...`);
  - Optional total track count suffix (`01/12`);
  - Automatic counter reset per directory or album;
  - Real-time tabular preview before writing tags to disk.
- **Live Bidirectional Pattern Converters:**
  - **Filename ➔ Tag (`FilenameToTagDialog`):** Intelligent metadata extraction from file paths with live preview;
  - **Tag ➔ Filename (`TagToFilenameDialog`):** Physical disk renaming using flexible masks;
  - **Advanced `$num(%track%,2)` Token Support:** Formatting and parsing track numbers with custom digit width.
- **1-Click Case Transformation:** Quick toolbar buttons for *Title Case*, *UPPERCASE*, and *lowercase*.

### 5. ⚡ Ultra-Fast Search Engine (`SearchEngine`)
- **Windows (NTFS MFT):** Direct Ctypes IPC binding to `Everything64.dll` querying the Master File Table in microseconds.
- **macOS (APFS/HFS+):** Native driver calling macOS Metadata Spotlight CLI (`mdfind`) with `kMDItemContentTypeTree == 'public.audio'`.
- **Automatic Fallback:** Seamless fallback to indexed SQLite FTS5 (Full-Text Search) with zero user configuration.

### 6. 🎛️ Multiprocessing Acoustic Engine & L1 RAM Cache
- **CPU Saturation:** Dynamically allocates logical CPU cores via `ProcessPoolExecutor` with batch scheduling.
- **Streaming Window Reads:** Analyzes the central high-energy drop window at 22,050 Hz, skipping quiet intros/outros and cutting STFT load by ~80%.
- **L1 In-Memory RAM Cache:** Staging buffer in RAM (`:memory:`) eliminates SSD wear during bulk library analysis; thread-safe LRU waveform cache for instant visual scrubbing.

### 7. 🔊 DSP Audio Engine (Spotify Pedalboard, FFmpeg libavfilter & JUCE VST3)
- **Spotify Pedalboard & NumPy/SciPy Fallback:** Comprehensive `src/audio/dsp_engine.py` module delivering professional studio DSP effects (HighpassFilter, LowpassFilter, PeakFilter, Compressor, Limiter, Clipping/Saturation) with high-precision NumPy/SciPy fallback.
- **FFmpeg libavfilter Broadcast Pipeline:** High-performance audio processing for de-clipping (`adeclip`), noise reduction/de-click (`afftdn`), surgical EQ (`highpass`, `lowpass`, `equalizer`), dynamic EBU R128 loudness normalization (`loudnorm`), and lookahead broadcast safety limiting (`alimiter`).
- **JUCE VST3 Hosting Bridge:** Loads external compiled VST3 plugins using Pedalboard's native JUCE C++ wrapper (`load_plugin`) with resilient error handling on Windows.
- **5 Studio-Grade DSP Presets:**
  - *Club Master:* Sub-bass cut 30Hz, punchy bass boost at 60Hz (+2.5dB), glue compression, and brickwall peak limiting at -0.5 dBTP for club sound systems;
  - *Vocal Clarity:* High-pass at 80Hz, presence boost at 3.8kHz, de-essing at 6.5kHz, and transparent optical compression;
  - *Warm Analog:* Smooth high roll-off (18.5kHz), 120Hz body warmth, and subtle harmonic soft-clipping saturation;
  - *DJ Punch:* Kick transient punch (85Hz) and snare snap (2.2kHz) with assertive dynamic control;
  - *De-Clip & Clean:* Digital de-clipping reconstruction, background hiss noise reduction, and safe peak limiting at -1.5 dBTP.
- **MP3 (320 kbps CBR / V0 VBR) & Lossless FLAC Export:** Direct re-encoding with complete cloning of ID3v2.4 tags and HD artwork.
- **EBU R128 / ITU-R BS.1770-4 Standards:** Integrated Loudness (LUFS), Loudness Range (LRA), and True Peak (dBTP) with 4x oversampling interpolation.

### 8. 🏠 Multi-Platform Trends Dashboard & Smart Recommendations
- **Restored Player "Simili" Button & Strict Context Routing:** Mini-player "Simili" button routes loaded track to Trova Simili with a non-blocking tooltip when empty. Clicking "Simili" on Top Charts cards/rows strictly isolates and inspects the chart track (`set_target_track`), safely routing streaming previews when local audio is absent and providing `affinity_score`, `score`, and `affinity` attributes.
- **Multi-Source Charts:** Dedicated tabs for `Top Spotify`, `Top SoundCloud / Hype`, and `Top Beatport / Discogs` with category switching, rich offline fallbacks, and 30-second in-app audio preview playback.
- **Collection Cross-Check:** Instant visual badge indicating whether a trending track is owned locally (`✓ In Library`) or missing (`+ Missing`).
- **Cosine Similarity Engine:** Deep discovery via Cosine.club, Chosic, and Last.fm matching acoustic vectors against your local library files.

### 9. ⚖️ Cascading Multi-Source Scraping & Genre Normalization
- **Multi-Provider Fallback Cascade:**
  - **Discogs API:** Identifies original Master Release year and prioritizes granular electronic `styles` (e.g. Tech House, Melodic Techno, Afro House) over generic "Electronic".
  - **MusicBrainz / AcousticBrainz:** Retrieves earliest original release date and community-curated genre tags.
  - **Beatport & Traxsource:** Targets precise dance and club subgenres for accurate DJ classification.
  - **WebEnricher (Wikipedia & YouTube Search Fallback):** Queries `"[Artist] - [Title] genre year"` when music databases return no match.
- **Strict Genre Normalization:** Rejection of generic labels (*Other*, *Unknown*, *Soundtrack*, *Music*, *Various*, *General*), favoring specific subgenres and assigning `"Vario"` strictly as the last resort.
- **Conflict Reconciliation Dialog (`ReconcilerDialog`):** Clear four-column layout with generous 36px row height and asynchronous search execution.

### 10. 💾 Dual-Mode Installation & Drive Migration
- **Standard Mode:** Installs into `Program Files`, adds Start Menu shortcuts, and stores data in `%APPDATA%\Musicat`.
- **Portable Mode (`portable.lock`):** Extracts cleanly to any external SSD or USB drive; database, configurations, and logs remain entirely self-contained (`./logs/`, `./musicat_data/`).
- **Volume Serial Resolver (`[VOL:XXXXXXXX]`):** Converts physical drive paths into volume-serial-relative URIs, allowing identical SSDs to move between Windows machines and macOS mount points without database breakage.

---

## 🛠️ Advanced Logging Suite & Troubleshooting

Musicat includes an exhaustive logging and troubleshooting subsystem:

### 1. Automatic Rotation & Compressed `.zip` Archives
- Active logs are written to `musicat.log`.
- When reaching **20 MB**, the file rotates and compresses into `.zip` format (`musicat.log.1.zip`, `musicat.log.2.zip`, ...).
- Automatically preserves the last **10 compressed archives**, guarding disk space.

### 2. Granular Domain Event Tracking
All internal and external events are logged with precise domains and log levels:
- **I/O & Scans (`[SCAN]`):** Folders scanned, total files, inserted, skipped, and duration ms.
- **libVLC Audio Engine (`[PLAYER:VLC]`):** Initialization, playback, pause, seek, pitch adjustments, and decode failures.
- **Mutagen Tag Editor (`[TAG]` & `[TAG:DIFF]`):** Pre/post metadata dumps, modified field diffs, ID3 corruption alerts.
- **Scrapers & HTTP (`[HTTP:<Source>]`):** URLs queried, parameters, status codes (200, 403, 404), latency in milliseconds, and exceptions.
- **File Manager (`[DISPATCH:<OP>]`):** Source and target paths (`SRC -> DEST`), collision handling (`RENAME`, `OVERWRITE`, `SKIP`).

### 3. Support Diagnostic Bundle Export
Both in the **Live Log Console** (`Ctrl+L`) and **Settings > Performance**, users can click:
👉 **"Export Logs for Support (.zip)"**
Generates an all-in-one diagnostic `.zip` archive containing:
- All active and compressed log files.
- Anonymized hardware specifications (CPU, RAM, GPU, OS).
- Database health statistics (track counts, indexes, WAL size).
- Sanitized configuration file (API tokens and credentials stripped).

---

## 🔍 Troubleshooting Guide

### 1. Audio player fails to play or warns "libVLC not found"
- **Windows:** Ensure 64-bit VLC Media Player is installed (`C:\Program Files\VideoLAN\VLC`) or copy `libvlc.dll` and `plugins/` into the application executable folder.
- **macOS:** Install VLC via Homebrew (`brew install --cask vlc`) or install `VLC.app` into `/Applications`.

### 2. Voidtools Everything fast search is disabled on Windows
- Musicat connects to the **Everything desktop service** via IPC. Verify that Everything is running in the background.
- If Everything is absent, Musicat automatically falls back to **SQLite FTS5**, ensuring full-text search remains operational without interruption.

### 3. Drive letters change on external USB drives
- Musicat stores physical volume IDs (`[VOL:XXXXXXXX]`). If Windows reassigns a drive from `E:\` to `F:\`, Musicat automatically re-links all tracks upon the next startup.

### 4. Tag write permission error (File Locked)
- If an audio file is currently loaded in another DJ player (e.g., Rekordbox or Traktor), Windows locks write permissions. Close external players before running batch tag updates.

---

## ⌨️ DJ Console Keyboard Shortcuts

| Shortcut | Action | Description |
|---|---|---|
| `Ctrl + F` | Quick Search | Focuses unified search bar (Everything MFT / Spotlight / FTS) |
| `Ctrl + G` | Genre Filter | Focuses multi-genre autocompleter |
| `Ctrl + B` | BPM Filter | Focuses target BPM field |
| `Ctrl + K` | Camelot Wheel | Opens visual Camelot Wheel assistant |
| `Esc` | Clear Filters | Instantly resets all active filters and reveals entire library |
| `Space` | Play / Pause | Starts/stops playback of selected track |
| `Enter` | Load Deck | Loads selected track into player deck |
| `Ctrl + T` | Mp3tag Space | Opens dedicated Mp3tag spreadsheet workbench |
| `Ctrl + E` | Batch Tags | Opens quick tag editor dialog |
| `Ctrl + R` | Reconcile | Opens multi-source metadata reconciliation matrix |
| `Ctrl + Q` | Audio Quality | Opens EBU R128 loudness and clipping diagnostics |
| `Ctrl + Shift + S`| Find Similars | Finds acoustically matching tracks locally and online |
| `Ctrl + Shift + P` / `Alt + F` | Pattern Tagging | Opens advanced Mp3tag bulk pattern extraction dialog with live preview |
| `Ctrl + S` | Smart Organizer | Opens disk reorganization and physical dispatch tool |
| `Ctrl + L` | Live Log Console | Toggles system live log stream dock |
| `Ctrl + ,` | Settings | Opens system preferences modal |
| `Alt + 1` .. `Alt + 6` | View Switching | Quickly switches between top navbar modules |

---

## 📦 Official Releases & Downloads

Ready-to-use binaries are built on every GitHub tag via automated GitHub Actions:

| Platform | Release Artifact | Description |
|---|---|---|
| **Windows 10/11 x64** | `Musicat-Setup-Windows-x64.exe` | Inno Setup Dual-Mode Installer (Standard or Portable) |
| **Windows 10/11 x64** | `Musicat-Windows-Portable.zip` | Standalone portable archive with `portable.lock` |
| **macOS Universal** | `Musicat-macOS.dmg` | Native Drag & Drop Applications installer DMG |
| **macOS Universal** | `Musicat-macOS-Portable.zip` | Standalone portable archive for APFS/HFS+ external SSDs |

👉 **[Download the Latest Official Release (v1.1.0)](https://github.com/IlRed89/Musicat/releases/latest)**

---

## 🛠️ Building from Source

### Prerequisites
- Python 3.11, 3.12, or 3.13 (64-bit)
- `git`
- libVLC (or VLC Media Player installed)
- (Optional on Windows) Inno Setup 6.2+ for installer compilation

### Instructions

```bash
# 1. Clone repository
git clone https://github.com/IlRed89/Musicat.git
cd Musicat

# 2. Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Run full test suite (132 tests)
python -m unittest discover tests -v

# 5. Launch application
python main.py
```

### Local Standalone Builds

```bash
# Windows Standalone Executable
pyinstaller --clean build_windows.spec

# Windows Portable Package (Batch script)
.\build\build_portable.bat

# macOS App & DMG Creation
pyinstaller --clean build_mac.spec
./build/build_mac_dmg.sh
```

---

## 🍏 macOS Launch Diagnostics & Fast Debugging

To diagnose startup bottlenecks, Apple Silicon / Intel architecture compatibility, or native Cocoa/libVLC crashes on macOS, a dedicated diagnostic runner is provided:

```bash
# Diagnostic launch capturing full terminal stream and desktop debug logs
chmod +x run_mac_debug.sh
./run_mac_debug.sh

# Deep Qt Cocoa plugin debug mode
./run_mac_debug.sh --qt-debug
```

### Logs Automatically Generated at Pre-Bootstrap:
1. **Live Terminal Log (`~/Desktop/musicat_terminal.log`):** Complete stream of `stdout` and `stderr`.
2. **Desktop Debug Log (`~/Desktop/musicat_debug.log`):** Line-by-line flushed mirror for instant access.
3. **Boot System Log (`~/Library/Application Support/Musicat/logs/musicat_boot.log`):** Early diagnostic record featuring:
   - Host architecture and **Rosetta 2** translation detection (`sysctl.proc_translated`).
   - Diagnostic dynamic probing for **libVLC** (`dlopen` validation capturing exact `OSError`).
   - macOS sandbox & filesystem permissions check (`/Volumes`, `~/Music`, `~/Desktop`).
   - Native C/C++ Segfault trap via Python `faulthandler.enable()`.

---

## 📄 License

Musicat is open-source software licensed under the **MIT** License.  
See [LICENSE](LICENSE) for full details.
