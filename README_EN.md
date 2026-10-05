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
| [📁 Library]   | [🏠 Home]       | [🏷️ Mp3tag]     | [📦 Crates]    | [🔍 Similar]    | [📂 Organize]  |
| - Startup View | - Multi-Platform| - Number Wizard | - Workbench    | - Cosine.club   | - In-App Stack |
| - 2-Row Filters| - Stream Preview| - Pattern %tag% | - Guide & M3U8 | - Web Vectors   | - Collision    |
| - Drag & Drop  | - EBU Loudness  | - $num() Live   | - Dynamic Crate| - Hard Drive    | - Dry Run      |
+----------------------------------------------------------------------------------------------------+
|           Unified Search Engine (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)         |
+----------------------------------------------------------------------------------------------------+
|                    libVLC Audio Engine with +/-8% Pitch Bending & Waveform Scrubbing               |
+----------------------------------------------------------------------------------------------------+
|        Status Bar with Dynamic Hardware Resource Progress Bars (CPU & RAM Thresholds)              |
+----------------------------------------------------------------------------------------------------+
|       Structured Logging Suite (20MB Rotating .zip, Diagnostic Support Bundle, Domain Tracking)    |
+----------------------------------------------------------------------------------------------------+
|               Cross-Platform Path Resolver ([VOL:XXXXXXXX] & portable.lock Drive Migration)        |
+----------------------------------------------------------------------------------------------------+
```

### 1. ⚪ Modern Light Theme Default, Embedded Workspaces & Modular Top Bar
- **6 Embedded Workspaces Architecture (`QStackedWidget`):** Key modules no longer open detached modal dialogs; they are cleanly integrated within the central view stack preserving selection state:
  - **Index 0: [📁 Library] (Default Startup View)** (High-performance DJ catalog with 2-row filter bar, drag & drop column reordering, dedicated `[⚡ Analizza Selezionate]` toolbar action, and drive tree explorer)
  - **Index 1: [🏠 Home / Analysis]** (Trending charts dashboard across Spotify/SoundCloud/Beatport with 30s stream audio previews and high-contrast white cards)
  - **Index 2: [🏷️ Tag Editor (Mp3tag)]** (Full-featured spreadsheet tagging workspace with numbering wizard, pattern engine, and case transformations)
  - **Index 3: [📦 Smart Crates]** (Rule-based crate builder with interactive user guide and extended M3U8 playlist export for Serato, Rekordbox, Traktor, and Engine DJ)
  - **Index 4: [🔍 Find Similars]** (Local acoustic matching and Cosine.club / Chosic web discovery with harmonic key transitions)
  - **Index 5: [📂 Organize Files]** (Physical disk re-organization tool integrated in-app with collision safety and dry-run preview)
- **High-Contrast Light Theme:** Modern crisp palette (`#FFFFFF` / `#F8F9FA`, text `#212529`, accents `#0D6EFD`) with instant Dark Mode switch available in Settings.
- **Native Taskbar Icon:** Windows `AppUserModelID` registration ensures high-resolution application branding on the taskbar even when running portably from USB drives.

### 2. 📊 Visual Hardware Monitor in Status Bar (Dynamic Progress Bars)
- **Embedded Graphical Progress Bars:** Replaced plain monochrome text with two sleek, horizontal `QProgressBar` widgets for CPU and RAM.
- **Dynamic Load Color Thresholds:**
  - **Green (`#28A745`):** Optimal and smooth operation (0% – 60%);
  - **Yellow / Orange (`#FD7E14`):** Moderate to heavy workload (61% – 84%);
  - **Red (`#DC3545`):** High stress or memory/compute saturation (85% – 100%).
- **64-bit Memory Transparency:** No artificial 2 GB memory ceilings; Musicat queries total physical installed RAM and reports `RAM X.X / YY GB` asynchronously every 1.5 seconds.

### 3. 🗂️ Collapsible Drive Explorer, Drag & Drop Column Customizer & 2-Row Filters
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

### 7. 🔊 Audio Quality Normalizer & Loudnorm Plugin (EBU R128)
- **EBU R128 / ITU-R BS.1770-4 Standards:** Integrated Loudness (LUFS), Loudness Range (LRA), and True Peak (dBTP) with 4x oversampling interpolation.
- **Loudness Meter Deactivated on Unanalyzed Tracks:** Replaces dummy `-70 LUFS / -100 dBTP` readings with a neutral deactivated placeholder `"— LUFS | TP: — dBTP (Non analizzato)"`.
- **Native Light Theme "Correggi Audio" Dialog:** Crisp `#ffffff` canvas, dark text `#212529`, and an educational callout explaining metadata ReplayGain versus physical FFmpeg loudnorm re-encoding (-1.0 dBTP headroom) with interactive target sliders (-9/-10 LUFS for club, -14 LUFS for streaming).

### 8. 🏠 Multi-Platform Trends Dashboard & Smart Recommendations
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
