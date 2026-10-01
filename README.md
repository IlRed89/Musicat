# 🐱🎧 Musicat

> **The Ultimate Desktop Music Catalog, DJ Tag Editor & Acoustic Smart Organizer.**  
> *Designed specifically for DJs, record collectors, and audio archivists managing massive libraries across internal and external storage.*

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%28Standard%20%26%20Portable%29-brightgreen.svg)]()
[![Target Repository](https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg)](https://github.com/IlRed89/Musicat)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

---

## 🌟 Vision & Overview

When managing collections of **50,000+ tracks** on high-capacity external SSDs, standard music players and generic taggers struggle: database paths break when Windows switches external drive letters, batch editing becomes sluggish, and critical DJ metadata (BPM, Camelot Keys, record labels, remixes, electronic subgenres) is treated as an afterthought.

**Musicat** combines eight foundational pillars into a unified, lightning-fast dark desktop interface:

1. ⚡ **DJ Catalog & Multi-Attribute Player:** Virtualized table architecture rendering tens of thousands of tracks with zero lag, instant filtering by BPM range, Camelot Key, and genre, plus a mini-player with interactive audio waveform scrubbing.
2. 🚀 **Voidtools Everything SDK & MFT Integration:** Instant Master File Table queries via IPC with transparent fallback to SQLite FTS5 (Full-Text Search).
3. 🎵 **Universal libVLC Audio Engine:** Native decoding for MP3, WAV, FLAC, AIFF, M4A, OGG, ALAC, and OPUS with DJ pitch rate bending ($\pm 8\%$) and waveform scrubbing.
4. 🏷️ **Advanced Mp3tag-Grade Metadata Engine:** Full support for MP3, FLAC, M4A, WAV, AIFF, and OGG containers with multi-selection batch tag editing and pattern conversions (`%artist% - %title% (%bpm% BPM)`).
5. 🌐 **Multi-Source Scraping & Discrepancy Reconciliation:** Scrapes Beatport, Traxsource, Discogs, MusicBrainz, and Social/Remix platforms (SoundCloud, YouTube Music, Hypeddit, Remix.audio). Reconciles conflicting metadata with field-by-field selective resolution.
6. 🖼️ **Studio HD Cover Art Injection:** Discovers lossless studio covers from 500x500 up to 3000x3000px (Apple Music / iTunes CDN, Beatport HD) and injects them directly into file tags (`APIC`, Picture block, `covr`) with optional local `cover.jpg` saving.
7. 🎛️ **Acoustic Analyzer & Smart Folder Dispatcher:** Automated non-destructive BPM and harmonic key detection (Camelot 1A–12B). Inbound file dispatcher that physically sorts tracks into customizable folder structures with **Dry Run** previews.
8. 💾 **Dual-Mode Setup (Standard & Portable):** Inno Setup wizard (`Musicat-Setup.exe`) allowing standard `%APPDATA%` installation or zero-installation portable extraction with `portable.lock` and Volume Serial Number (VSN) tracking.

---

## 🏗️ Architecture

```
Musicat/
├── installer/
│   └── setup.iss              # Inno Setup dual-mode installer (Standard vs Portable)
├── src/
│   ├── core/                  # Core Systems
│   │   ├── db.py              # SQLite WAL database & FTS5 full-text search engine
│   │   ├── everything_search.py # Voidtools Everything SDK (MFT IPC) + FTS fallback
│   │   ├── logger.py          # Structured logging (20MB compressed rotation, GUI console)
│   │   ├── path_resolver.py   # Volume Serial Number (VSN) & portable.lock resolver
│   │   └── scanner.py         # Multi-threaded recursive folder scanner
│   ├── audio/                 # Acoustic Analysis
│   │   ├── analyzer.py        # BPM autocorrelation & Camelot Wheel chromagram engine
│   │   └── waveform.py        # Downsampled audio peak extraction for mini-player
│   ├── player/                # Audio Engine
│   │   └── vlc_engine.py      # libVLC universal engine with DJ pitch rate bending (+/- 8%)
│   ├── tags/                  # Tag & Metadata Engine
│   │   ├── editor.py          # Unified Mutagen wrapper (ID3, Vorbis, MP4, RIFF)
│   │   └── patterns.py        # Pattern parser (%artist% - %title% (%bpm% BPM))
│   ├── scrapers/              # Online Metadata Scraping & Reconciliation
│   │   ├── beatport.py        # Beatport club & dance metadata + high-res artwork
│   │   ├── traxsource.py      # Traxsource house/club metadata scraper
│   │   ├── discogs.py         # Discogs vinyl/digital search & catalog numbers
│   │   ├── musicbrainz.py     # MusicBrainz canonical recording & release search
│   │   ├── social_remix.py    # SoundCloud, YouTube Music, Hypeddit, Remix.audio
│   │   ├── artwork_hd.py      # Studio HD artwork discovery (Apple Music up to 3000px)
│   │   ├── reconciler.py      # Multi-source discrepancy reconciliation engine
│   │   └── acoustid.py        # Chromaprint acoustic fingerprinting lookup
│   ├── organizer/             # Smart File Dispatcher
│   │   └── sorter.py          # Dynamic folder hierarchy sorter & Dry-Run planner
│   ├── gui/                   # Dark DJ Console Interface (PySide6)
│   │   ├── main_view.py       # Primary dashboard with filters, live log & table
│   │   ├── table_model.py     # High-performance virtual QAbstractTableModel
│   │   ├── player_widget.py   # VLC-backed player with waveform canvas & DJ pitch slider
│   │   ├── tag_editor_dialog.py # Inline & batch tag editor with cover manager
│   │   ├── reconciler_dialog.py # Multi-source discrepancy & HD cover dialog
│   │   ├── sorter_dialog.py   # Smart Organizer GUI with interactive dry-run table
│   │   ├── pattern_dialog.py  # Filename <-> Tag conversion dialog with live preview
│   │   ├── scraper_dialog.py  # "Before / After" split-table scraper comparison
│   │   ├── styles.py          # Dark DJ booth theme stylesheet (QSS)
│   │   └── app.py             # Qt application bootstrap
│   └── main.py                # Main executable entry point & CLI scanner
├── build/
│   ├── build_portable.bat     # Windows automated portable builder
│   └── musicat.spec           # PyInstaller bundle specification
├── tests/                     # Comprehensive test suite (30+ unit tests)
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 🚀 Key Features

### 1. Dual-Mode Installer & Portability (`setup.iss`)
- **Standard Mode:** Installs in `Program Files`, adds Start Menu/Desktop shortcuts, writes registry keys, and isolates data in `%APPDATA%\Musicat`.
- **Portable Mode:** Extracts into any folder (e.g. external SSD `E:\Musicat_Portable`), writes `portable.lock`, and keeps database, configuration, and logs strictly in `./musicat_data/`.

### 2. Voidtools Everything MFT Search
- Connects directly to `Everything64.dll` via IPC to search NTFS drives with 100,000+ files in milliseconds.
- If Everything is closed or not installed, falls back seamlessly to the internal SQLite FTS5 (Full-Text Search) index without UI freezing.

### 3. libVLC Integrated Player & DJ Pitch Control
- Native support for every audio format: **MP3, WAV, FLAC, AIFF, M4A, OGG, ALAC, OPUS**.
- **DJ Pitch / Tempo Slider:** Real-time speed/pitch bending from $-8.0\%$ to $+8.0\%$ for auditioning tracks at club tempos.
- Interactive waveform scrubbing with click-to-seek and looping.

### 4. Multi-Source Scraping & Discrepancy Reconciliation
- Aggregates metadata across:
  - **Club/DJ sources:** Beatport, Traxsource, Discogs, MusicBrainz.
  - **Social/Remix platforms:** SoundCloud, YouTube Music, Hypeddit, Remix.audio.
- **Reconciliation Engine:** Compares results side-by-side, detects conflicts (e.g., Beatport says "Melodic Techno", Discogs says "Progressive House"), and allows selective field-by-field merging.

### 5. Studio HD Cover Art Discovery (up to 3000x3000px)
- Fetches studio uncompressed artwork via Apple Music CDN upscaling, Beatport GeoMedia, and Traxsource.
- Injects artwork directly into audio tags (`APIC` for MP3, Picture block for FLAC, `covr` for M4A) and optionally writes `cover.jpg` in the folder.

### 6. Tag Editor & Pattern Engine (Stile Mp3tag)
- **Batch Editing:** Select 200 tracks, modify Genre or Year with `<keep existing>` safety for untouched fields.
- **Conversions:**
  - *Filename ➔ Tag:* `%artist% - %title% (%bpm% BPM)`
  - *Tag ➔ Filename:* Mass physical renaming based on database tags.
  - *Tag ➔ Tag:* Copy, swap, or merge fields.

### 7. Structured Logging with Compressed Rotation
- Centralized multi-level logger (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- Automatic 20MB file rotation with `.gz` compression.
- Live Log console dock in the GUI (`Ctrl+L`) for monitoring background tasks.

---

## 💻 Quickstart & Installation

### Requirements
- **OS:** Windows 10 / 11 (64-bit)
- **Python:** 3.11, 3.12, or 3.13

### 1. Clone & Setup
```powershell
git clone https://github.com/IlRed89/Musicat.git
cd Musicat
pip install -r requirements.txt
```

### 2. Run the Application
```powershell
python main.py
```

### 3. CLI Mode (Headless Folder Scan)
```powershell
python main.py --scan "E:\DJ_Music"
```

---

## 🧪 Running Unit Tests

Musicat includes 46 unit tests covering every subsystem:

```powershell
python -m unittest discover tests -v
```

---

## 🎛️ Live DJ Crate & Advanced Filtering Engine

Designed specifically for live performance in the DJ booth with sub-15ms query latency across 50,000+ tracks:

- **Multi-Genre OR Filtering:** Autocomplete search with simultaneous selection of multiple subgenres (e.g. *Tech House* OR *Afro House* OR *Melodic Techno*).
- **Target BPM ± % Tolerance:** Enter deck tempo (e.g. `126.0`) and choose tolerance (`±2%`, `±4%`, `±6%`, `±8%`) to automatically bound allowable BPM.
- **Harmonic Mixing Assistant:** Visual Camelot Wheel selector (`1A`-`12B`) with one-click filtering for harmonic matches (Smooth steps `±1`, Relative Major/Minor, Energy Boost `+2`, Semitone Lift `+7`).
- **Decades & Energy:** Instant filtering by Decade (80s, 90s, 2000s, 2010s, 2020s), Energy levels (Warmup, Mid, Peak Time), and quick DJ tags (*Intro*, *Vocal*, *Instrumental*, *Acapella*, *Club*).
- **Dynamic Smart Crates:** Save filter combinations as dynamic playlists that automatically update as new tracks are scanned.
- **Universal M3U8 Export:** Export any active crate with standard `#EXTM3U` and `#EXTINF` formatting compatible with Rekordbox, Traktor Pro, Serato DJ, and Denon Engine DJ.

---

## ⌨️ DJ Console Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + F` | Instant Focus on Quick Search (Everything MFT / SQLite FTS) |
| `Ctrl + G` | Quick Jump to Multi-Genre Selector |
| `Ctrl + B` | Focus on Target Deck BPM Input |
| `Ctrl + K` | Open Visual Camelot Wheel Harmonic Assistant Popup |
| `Esc` | Instant Reset of All Active Filters (View Entire Library) |
| `Enter` / `Return` | Load and Audition Selected Track into VLC Engine |
| `Space` | Play / Pause Preview of Active / Selected Track |
| `Ctrl + O` | Scan Music Directory |
| `F5` | Refresh Library & Filters |
| `Ctrl + E` | Open Batch / Single Tag Editor |
| `Ctrl + R` | Open Multi-Source Reconciler & HD Cover Injector |
| `Ctrl + A` | Run Batch Acoustic Analysis (BPM & Key) |
| `Ctrl + S` | Open Smart File Dispatcher & Organizer |
| `Ctrl + L` | Toggle Live System Log Console |
| `Double Click` | Load and Audition Track in Mini-Player |

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Developed with ❤️ for the DJ and music collector community by [IlRed89](https://github.com/IlRed89).
