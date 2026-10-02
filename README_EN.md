# 🐱🎧 Musicat

> **The Universal DJ Music Catalog, Mp3tag-Grade Metadata Workbench & Acoustic Smart Organizer.**  
> *Engineered specifically for DJs, electronic music collectors, and sound archivists managing massive libraries (50,000+ tracks) across external SSDs and local storage.*

[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](README_EN.md)
[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](README.md)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11%20x64%20%7C%20macOS%20Universal-brightgreen.svg)]()
[![Repository](https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg)](https://github.com/IlRed89/Musicat)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

---

## 🌟 Overview & Vision

Managing 50,000+ digital music tracks on high-capacity external drives introduces severe challenges for modern DJs and collectors:
- Operating system drive letters and mount points shuffle when switching USB ports or migrating between **Windows** and **macOS**, breaking standard software databases.
- Traditional DJ software (Rekordbox, Traktor, Serato, Engine DJ) lacks powerful bulk tag editing, studio cover retrieval, and deep metadata reconciliation.
- Generic tag editors (like Mp3tag) lack acoustic DSP analysis, live DJ Camelot harmonic filtering, audio quality diagnostics, and Spotify trend cross-checking.

**Musicat** unifies all these requirements into a lightning-fast, hardware-accelerated dark desktop workstation available natively for **Windows (10/11 x64)** and **macOS (Apple Silicon M-Series + Intel x64)**.

---

## 🚀 Key Functional Modules

```
+----------------------------------------------------------------------------------------------------+
|                                              MUSICAT                                               |
+----------------------------------------------------------------------------------------------------+
|  [Live DJ Crates]   |  [Mp3tag Workbench]  |  [Acoustic Engine]  |  [Loudnorm Plugin]  | [Trends]  |
|  - <15ms RAM Filter |  - Spreadsheet Grid  |  - Multiprocess DSP |  - EBU R128 LUFS    | - Spotify |
|  - Camelot Wheel    |  - Multi-tag Batch   |  - BPM & Key FFT    |  - True Peak dBTP   | - Cosine  |
|  - Multi-Genre (OR) |  - Patterns %tag%    |  - L1 RAM Cache     |  - Auto-Normalize   | - Similars|
+----------------------------------------------------------------------------------------------------+
|           Unified Search Engine (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)         |
+----------------------------------------------------------------------------------------------------+
|                    libVLC Audio Engine with +/-8% Pitch Bending & Waveform Scrubbing               |
+----------------------------------------------------------------------------------------------------+
|               Cross-Platform Path Resolver ([VOL:XXXXXXXX] & portable.lock Drive Migration)        |
+----------------------------------------------------------------------------------------------------+
```

### 1. 🎛️ Live DJ Crates & Advanced Filter Engine (<15ms Latency)
- **Multi-Genre Selector:** Auto-complete dropdown supporting multiple simultaneous genres with `OR` filtering (e.g. *Tech House* OR *Afro House* OR *Melodic Techno*).
- **Dynamic BPM Targeting:** Target BPM input with pitch tolerance presets (`±2%`, `±4%`, `±6%`, `±8%`), as well as explicit Min/Max ranges.
- **Harmonic Camelot Wheel Assistant:** Visual 12-column interactive Camelot Wheel (`1A`–`12B`) supporting:
  - $\pm 1$ Smooth Transitions (Energy stability)
  - Relative Key (Major $\leftrightarrow$ Minor mood change)
  - $+2$ Energy Boost transitions
  - $+7$ Semitone Peak Energy Lift
- **Smart Crates & Universal M3U8 Export:** Instant saving of complex filter conditions into dynamic crates; export playlists to extended `.m3u8` for immediate import into Pioneer CDJs, Rekordbox, Traktor, Serato, and Engine DJ.

### 2. 🏷️ Dedicated Mp3tag Workbench
- **Spreadsheet Table View:** Inline editing and multi-row batch editing for single or grouped tracks.
- **Tag <-> Filename Pattern Converter:** Bidirectional pattern engine supporting tokens like `%artist% - %title% (%bpm% BPM) [%camelot%]`.
- **HD Studio Album Art Injection:** Embeds high-resolution cover artwork (up to 3000x3000px from Apple Music / Beatport HD) into ID3v2.4 `APIC`, FLAC picture blocks, and MP4 `covr` atoms.
- **Universal Container Support:** MP3, FLAC, WAV (up to 32-bit float), AIFF, M4A/ALAC, OGG Vorbis, and OPUS.

### 3. ⚡ Ultra-Fast Search Engine (`SearchEngine`)
- **Windows (NTFS MFT):** Direct Ctypes IPC binding to `Everything64.dll` querying the Master File Table in microseconds.
- **macOS (APFS/HFS+):** Native driver calling macOS Metadata Spotlight CLI (`mdfind`) with `kMDItemContentTypeTree == 'public.audio'`.
- **Automatic Fallback:** Seamless fallback to indexed SQLite FTS5 (Full-Text Search) with zero user configuration.

### 4. 🎛️ Multiprocessing Acoustic Engine & L1 RAM Cache
- **CPU Saturation:** Dynamically allocates logical CPU cores via `ProcessPoolExecutor` with batch scheduling.
- **Streaming Window Reads:** Analyzes the central high-energy drop window at 22,050 Hz, skipping quiet intros/outros and cutting STFT load by ~80%.
- **L1 In-Memory RAM Cache:** Staging buffer in RAM (`:memory:`) eliminates SSD wear during bulk library analysis; thread-safe LRU waveform cache for instant visual scrubbing.

### 5. 🔊 Audio Quality Normalizer & Loudnorm Plugin
- **EBU R128 / ITU-R BS.1770-4 Standards:** Integrated Loudness (LUFS), Loudness Range (LRA), and True Peak (dBTP) with 4x oversampling.
- **Anomaly Detection:** Flags clipped tracks ($>0$ dBTP), quiet tracks ($<-18$ LUFS), and squashed brickwall masters ($\text{LRA} < 3$ LU).
- **Dual Correction:**
  - *Non-destructive:* ReplayGain metadata tagging (`REPLAYGAIN_TRACK_GAIN`, `REPLAYGAIN_TRACK_PEAK`).
  - *Destructive:* Physical re-encoding with FFmpeg two-pass `loudnorm` filter (target: $-14$ LUFS, $-1.0$ dBTP).

### 6. 🏠 Spotify Top Trends & Smart Recommendations
- **Live Spotify DJ Charts:** Category trends (Dance/Electro, Tech House, Techno, Global Top 50) with 24-hour local caching.
- **Collection Cross-Check:** Instant visual badge indicating whether a trending track is owned locally (`✓ In Library`) or missing (`+ Missing`).
- **Cosine Similarity Engine:** Deep discovery via Cosine.club, Chosic, and Last.fm matching acoustic vectors against your local library files.

### 7. 💾 Dual-Mode Installation & Drive Migration
- **Standard Mode:** Installs into `Program Files`, adds Start Menu shortcuts, and stores data in `%APPDATA%\Musicat`.
- **Portable Mode (`portable.lock`):** Extracts cleanly to any external SSD or USB drive; database and config remain entirely self-contained.
- **Volume Serial Resolver (`[VOL:XXXXXXXX]`):** Converts physical drive paths into volume-serial-relative URIs, allowing identical SSDs to move between Windows machines and macOS mount points without database breakage.

### 8. 🌐 Bilingual Localization (Italian / English)
- **Italian (Default):** Native default localization out of the box (`it`).
- **English (Secondary):** Complete English translation set (`en`).
- **Dynamic Hot-Switching:** Switch language directly in Preferences with immediate UI update without restarting.

---

## ⌨️ DJ Console Keyboard Shortcuts

| Shortcut | Action | Description |
|---|---|---|
| `Ctrl + F` | Quick Search | Focuses unified search bar (Everything MFT / Spotlight / FTS) |
| `Ctrl + G` | Genre Filter | Focuses multi-genre autocompleter |
| `Ctrl + B` | BPM Filter | Focuses Target BPM input box |
| `Ctrl + K` | Camelot Wheel | Opens visual Camelot Harmonic Mixing assistant |
| `Escape` | Reset Filters | Instantly clears all active filters and restores full library |
| `Space` | Play / Pause | Auditions selected track or toggles mini-player deck |
| `Enter` | Load Deck | Double-click or Enter loads track into the preview player |
| `Ctrl + T` | Mp3tag Workbench | Opens dedicated Mp3tag workspace |
| `Ctrl + E` | Quick Tag Editor | Opens batch tag editing modal |
| `Ctrl + R` | Reconciler | Multi-source discrepancy reconciliation |
| `Ctrl + Q` | Quality Diagnosis | Opens EBU R128 loudness and clipping analyzer |
| `Ctrl + Shift + S`| Find Similar | Discovers acoustically and harmonically similar tracks |
| `Ctrl + S` | Smart Organizer | Launches file dispatcher and dry-run mover |
| `Ctrl + L` | Live Log | Toggles bottom real-time diagnostic log dock |
| `Ctrl + ,` | Settings | Opens modular preferences dialog |
| `Alt + 1` / `Alt + 2` | View Switcher | Switches between DJ Library and Home Trends views |

---

## 📦 Releases & Downloads

Pre-built binaries and standalone portable packages are generated automatically on every release via GitHub Actions:

| Platform | Format | Description |
|---|---|---|
| **Windows 10/11 x64** | `Musicat-Setup-Windows-x64.exe` | Dual-mode Inno Setup installer (Standard or Portable) |
| **Windows 10/11 x64** | `Musicat-Windows-Portable.zip` | Standalone zero-install portable folder (`portable.lock`) |
| **macOS Universal** | `Musicat-macOS.dmg` | Native styled DMG with Drag & Drop to `/Applications` |
| **macOS Universal** | `Musicat-macOS-Portable.zip` | Standalone portable bundle for external APFS/HFS+ SSDs |

👉 **[Download Latest Release (v1.0.0)](https://github.com/IlRed89/Musicat/releases)**

---

## 🛠️ Building From Source

### Prerequisites
- Python 3.11, 3.12, or 3.13 (64-bit)
- `git`
- libVLC (or VLC Media Player installed on system)
- (Windows only, optional) Inno Setup 6.2+ for compiling the installer

### Setup Steps

```bash
# 1. Clone repository
git clone https://github.com/IlRed89/Musicat.git
cd Musicat

# 2. Create virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Run full test suite (124+ unit tests)
python -m unittest discover tests -v

# 5. Launch application
python main.py
```

### Compiling Standalone Executables

```bash
# Windows Standalone Executable
pyinstaller --clean build_windows.spec

# Windows Portable Bundle Batch Script
.\build\build_portable.bat

# macOS Application Bundle & DMG
pyinstaller --clean build_mac.spec
./build/build_mac_dmg.sh
```

---

## 📄 License & Attribution

Musicat is distributed under the open-source **MIT License**.  
See [LICENSE](LICENSE) for full legal text.

Developed for the global DJ and music collector community. Contributions, feature requests, and pull requests are welcomed!
