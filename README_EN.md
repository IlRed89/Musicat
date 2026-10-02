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
  <img src="https://img.shields.io/badge/tests-130%20passing-brightgreen.svg" alt="Test Suite">
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
| [Analysis / Home] | [DJ Library]   | [Mp3tag Space]  | [Smart Crates] | [Find Similars] | [Organize]   |
| - Startup Default | - RAM Filters  | - Cell Grid     | - Workbench    | - Cosine.club   | - Dry Run    |
| - Spotify Trends  | - 1A-12B Wheel | - Multi-Tag     | - Dynamic Crate| - Web Vectors   | - Collision  |
| - EBU Diagnostics | - Pitch +/-8%  | - Pattern %tag% | - Export M3U8  | - Hard Drive    | - Rule Tree  |
+----------------------------------------------------------------------------------------------------+
|           Unified Search Engine (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)         |
+----------------------------------------------------------------------------------------------------+
|                    libVLC Audio Engine with +/-8% Pitch Bending & Waveform Scrubbing               |
+----------------------------------------------------------------------------------------------------+
|       Structured Logging Suite (20MB Rotating .zip, Diagnostic Support Bundle, Domain Tracking)    |
+----------------------------------------------------------------------------------------------------+
|               Cross-Platform Path Resolver ([VOL:XXXXXXXX] & portable.lock Drive Migration)        |
+----------------------------------------------------------------------------------------------------+
```

### 1. ⚪ Modern Light Theme Default & Clean Modular Navbar
- **High-Contrast Light Theme:** Modern palette (`#FFFFFF` / `#F8F9FA`, text `#212529`, accents `#0D6EFD`) engineered for pristine legibility in clubs, studios, and high-glare environments. Instant switch to Dark Theme available in Settings.
- **Minimal Top Bar with No Ambiguous Icons:** No isolated shortcut icons. The top navbar solely features explicit navigation buttons to full modules:
  - **[Analysis / Home]** (Default initial screen on application startup)
  - **[Library]**
  - **[Tag Editor (Mp3tag)]**
  - **[Smart Crates]**
  - **[Find Similars]**
  - **[Organize Files]**
  - **[Settings]**

### 2. 🗃️ Dedicated "Smart Crates" Workbench
- Full-screen dedicated workbench replacing small cluttered sidebars.
- Visual rule builder for complex multi-attribute queries (BPM ranges, Camelot Key, multi-genres, rating, energy profile).
- 1-click dynamic export to extended `.m3u8` playlists for Pioneer CDJ, Rekordbox, Traktor, Serato, and Engine DJ.

### 3. 🎛️ Live DJ Crates & Advanced Filter Engine (<15ms Latency)
- **Multi-Genre Selector:** Auto-complete dropdown supporting multiple simultaneous genres with `OR` filtering (e.g. *Tech House* OR *Afro House* OR *Melodic Techno*).
- **Dynamic BPM Targeting:** Target BPM input with pitch tolerance presets (`±2%`, `±4%`, `±6%`, `±8%`), as well as explicit Min/Max ranges.
- **Harmonic Camelot Wheel Assistant:** Visual 12-column interactive Camelot Wheel (`1A`–`12B`) supporting:
  - $\pm 1$ Smooth Transitions (Energy stability)
  - Relative Key (Major $\leftrightarrow$ Minor mood change)
  - $+2$ Energy Boost transitions
  - $+7$ Semitone Peak Energy Lift

### 4. 🏷️ Dedicated Mp3tag Workbench
- **Spreadsheet Table View:** Inline editing and multi-row batch editing for single or grouped tracks.
- **Tag <-> Filename Pattern Converter:** Bidirectional pattern engine supporting tokens like `%artist% - %title% (%bpm% BPM) [%camelot%]`.
- **HD Studio Album Art Injection:** Embeds high-resolution cover artwork (up to 3000x3000px from Apple Music / Beatport HD) into ID3v2.4 `APIC`, FLAC picture blocks, and MP4 `covr` atoms.
- **Universal Container Support:** MP3, FLAC, WAV (up to 32-bit float), AIFF, M4A/ALAC, OGG Vorbis, and OPUS.

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
- **Anomaly Detection:** Flags clipped tracks ($>0$ dBTP), quiet tracks ($<-18$ LUFS), and squashed brickwall masters ($\text{LRA} < 3$ LU).
- **Dual Correction:**
  - *Non-destructive:* ReplayGain metadata tagging (`REPLAYGAIN_TRACK_GAIN`, `REPLAYGAIN_TRACK_PEAK`).
  - *Physical re-encode:* Physical re-encoding with FFmpeg two-pass `loudnorm` filter (target: $-14$ LUFS, $-1.0$ dBTP).

### 8. 🏠 Spotify Top Trends & Smart Recommendations
- **Live Spotify DJ Charts:** Category trends (Dance/Electro, Tech House, Techno, Global Top 50) with local caching.
- **Collection Cross-Check:** Instant visual badge indicating whether a trending track is owned locally (`✓ In Library`) or missing (`+ Missing`).
- **Cosine Similarity Engine:** Deep discovery via Cosine.club, Chosic, and Last.fm matching acoustic vectors against your local library files.

### 9. ⚖️ Multi-Source Scraping & Conflict Reconciliation
- Simultaneous queries to **Beatport**, **Traxsource**, **Discogs**, **MusicBrainz**, and social platforms (**SoundCloud**, **YouTube Music**, **Hypeddit**, **Remix.audio**).
- Discrepancy comparison matrix with field-by-field selective resolution checkboxes.

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

👉 **[Download the Latest Official Release (v1.0.0)](https://github.com/IlRed89/Musicat/releases)**

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

# 4. Run full test suite (130 tests)
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

## 📄 License

Musicat is open-source software licensed under the **MIT** License.  
See [LICENSE](LICENSE) for full details.
