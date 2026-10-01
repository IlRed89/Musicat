# 🐱🎧 Musicat

> **The Ultimate Desktop Music Catalog, DJ Tag Editor & Acoustic Smart Organizer.**  
> *Designed specifically for DJs, record collectors, and audio archivists managing massive libraries across internal and external storage.*

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%28Standalone%20Portable%29-brightgreen.svg)]()
[![Target Repository](https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg)](https://github.com/IlRed89/Musicat)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

---

## 🌟 Vision & Overview

When managing collections of **50,000+ tracks** on high-capacity external SSDs, standard music players and generic taggers struggle: database paths break when Windows switches external drive letters, batch editing becomes sluggish, and critical DJ metadata (BPM, Camelot Keys, record labels, remixes, electronic subgenres) is treated as an afterthought.

**Musicat** combines three foundational pillars into a unified, lightning-fast dark desktop interface:

1. ⚡ **DJ Catalog & Multi-Attribute Player:** Virtualized table architecture rendering tens of thousands of tracks with zero lag, instant filtering by BPM range, Camelot Key, and genre, plus a mini-player with interactive audio waveform scrubbing.
2. 🏷️ **Advanced Mp3tag-Grade Metadata Engine:** Full support for MP3, FLAC, M4A, WAV, AIFF, and OGG containers. Batch editing, cover art embedding, bidirectional filename <-> tag conversion patterns, and online metadata scraping (**Beatport**, **Discogs**, **MusicBrainz**, **AcoustID**) with side-by-side Before/After diffs.
3. 🎛️ **Acoustic Analyzer & Smart Folder Dispatcher:** Automated non-destructive BPM and harmonic key detection (Camelot 1A–12B). Inbound file dispatcher that physically sorts tracks into customizable folder structures (e.g., `{Genre}/BPM {bpm_range}/{Camelot} - {Artist} - {Title}.ext`) with **Dry Run** previews and collision resolution.
4. 💾 **Zero-Installation Portability:** SQLite database configured with WAL mode and Windows Volume Serial Number (VSN) resolver—run Musicat directly from a USB stick without losing library paths regardless of drive letter reassignments (`D:`, `E:`, `F:`, etc.).

---

## 🏗️ Architecture

```
Musicat/
├── src/
│   ├── core/                  # Engine Core
│   │   ├── db.py              # SQLite WAL database & index query engine (50k+ tracks)
│   │   ├── scanner.py         # Multi-threaded recursive folder scanner
│   │   └── path_resolver.py   # Volume Serial Number (VSN) & USB portability resolver
│   ├── audio/                 # Acoustic Analysis
│   │   ├── analyzer.py        # BPM autocorrelation & Camelot Wheel chromagram engine
│   │   └── waveform.py        # Downsampled audio peak extraction for mini-player
│   ├── tags/                  # Tag & Metadata Engine
│   │   ├── editor.py          # Unified Mutagen wrapper (ID3, Vorbis, MP4, RIFF)
│   │   └── patterns.py        # Pattern parser (%artist% - %title% (%bpm% BPM))
│   ├── scrapers/              # Online Metadata Scraping
│   │   ├── beatport.py        # Beatport club & dance metadata + high-res artwork
│   │   ├── acoustid.py        # Chromaprint acoustic fingerprinting lookup
│   │   ├── musicbrainz.py     # MusicBrainz canonical recording & release search
│   │   └── discogs.py         # Discogs vinyl/digital search & catalog numbers
│   ├── organizer/             # Smart File Dispatcher
│   │   └── sorter.py          # Dynamic folder hierarchy sorter & Dry-Run planner
│   ├── gui/                   # Dark DJ Console Interface (PySide6)
│   │   ├── main_view.py       # Primary dashboard with filters & virtual table
│   │   ├── table_model.py     # High-performance virtual QAbstractTableModel
│   │   ├── player_widget.py   # Mini-player with custom waveform canvas & seekbar
│   │   ├── tag_editor_dialog.py # Inline & batch tag editor with cover manager
│   │   ├── sorter_dialog.py   # Smart Organizer GUI with interactive dry-run table
│   │   ├── pattern_dialog.py  # Filename <-> Tag conversion dialog with live preview
│   │   ├── scraper_dialog.py  # "Before / After" split-table scraper comparison
│   │   ├── styles.py          # Dark DJ booth theme stylesheet (QSS)
│   │   └── app.py             # Qt application bootstrap
│   └── main.py                # Main executable entry point & CLI scanner
├── build/
│   ├── build_portable.bat     # Windows automated portable builder
│   └── musicat.spec           # PyInstaller bundle specification
├── tests/                     # Comprehensive test suite
├── requirements.txt
└── README.md
```

---

## 🚀 Key Features

### 1. Tag Editor & Pattern Engine (Stile Mp3tag)
- **Batch Editing:** Select 100 tracks, change Genre to `Melodic Techno` and Year to `2024` without overwriting individual titles.
- **Bidirectional Conversions:**
  - *Filename ➔ Tag:* Extract metadata using patterns like `%artist% - %title% (%bpm% BPM)` or `%year% - %genre%/%track% - %title%`.
  - *Tag ➔ Filename:* Mass-rename physical files using database tags (e.g. `[%camelot%] %artist% - %title%`).
  - *Tag ➔ Tag:* Copy, swap, or merge fields (e.g. copy Comment to Key or combine Artist + Label).
- **Artwork Engine:** View embedded covers, embed high-resolution JPEGs/PNGs, export to `cover.jpg`, or batch-remove artwork.
- **DJ-Specific Fields:** Native fields for `BPM`, `Camelot Key` (`1A` - `12B`), `Musical Key`, `Remixer`, `Label`, `Energy Level` (`1` - `10`), and `Comments`.

### 2. Acoustic Analysis & Harmonic Mixing
- **BPM Engine:** Analyzes onset envelopes and spectral flux with dance-music octave disambiguation (60–185 BPM).
- **Key Extraction:** Calculates 12-bin chromagram and correlates with Krumhansl-Schmuckler profiles to produce Musical Keys and Camelot codes (e.g., `8A` for A minor, `8B` for C major).
- **Harmonic Compatibility:** Instantly identifies harmonic match options (adjacent $\pm 1$, relative major/minor, and $+2$ energy boost).
- **Peak & Loudness:** Calculates True Peak dBFS, RMS, and suggested ReplayGain adjustments.

### 3. Online Metadata Scraping & Auto-Tagging
- **Beatport Scraping:** Retrieves official electronic track titles, mix names (`Extended Mix`, `Club Mix`), subgenres, release dates, labels, and 500x500 artwork.
- **AcoustID & Chromaprint:** Identifies tracks with mangled or missing filenames through acoustic audio fingerprinting.
- **MusicBrainz & Discogs:** Comprehensive release lookups, vinyl catalog numbers, and ISRC codes.
- **"Before / After" Diff Window:** Side-by-side comparison of metadata changes before writing anything to disk.

### 4. Smart Organizer & Inbound Dispatcher
- Point Musicat to an inbound or disorganized folder and dispatch files into structured directories:
  - **By Genre:** `Destination/{genre}/{artist} - {title}.ext`
  - **By Year:** `Destination/{year}/{artist} - {title}.ext`
  - **By BPM Range:** `Destination/BPM {bpm_range} (e.g. 120-124 BPM)/{artist} - {title}.ext`
  - **By Camelot Key:** `Destination/Key {camelot_key}/{artist} - {title}.ext`
  - **Composite Hierarchy:** `Destination/{genre}/BPM {bpm_range}/{camelot_key} - {artist} - {title}.ext`
- **Dry Run Mode:** Simulates the complete operation and reports collisions, missing tags, and planned file targets before moving or copying.
- **Collision Handling:** Choose between `Auto-Rename (1)`, `Overwrite`, or `Skip`.

### 5. High-Performance Virtual Table & Player
- Smooth 60 FPS scrolling and instantaneous sorting across 50,000+ tracks.
- Mini-player with native audio playback and interactive waveform peak scrubbing.
- Multi-attribute filter bar: Instant full-text search, BPM range slider, Camelot key dropdown, and genre filter.

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

## 📦 Building the Portable Windows Executable

To generate a standalone `.exe` that runs without requiring Python or installation:

1. Double-click `build/build_portable.bat` or run:
   ```powershell
   pyinstaller --clean build/musicat.spec
   ```
2. The compiled standalone binary will be available at:
   ```
   dist/Musicat.exe
   ```
3. Copy `Musicat.exe` to your external hard drive or USB thumb drive. On first launch, it will create a `musicat_data/` folder next to the executable to store its database and settings portably.

---

## 🧪 Running Unit Tests

Musicat includes a comprehensive test suite covering tagging, pattern parsing, acoustic analysis, and SQLite operations:

```powershell
python -m unittest discover tests
```

---

## ⌨️ DJ Console Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + O` | Scan Music Directory |
| `F5` | Refresh Library & Filters |
| `Ctrl + E` | Open Batch / Single Tag Editor |
| `Ctrl + K` | Open Filename ⇄ Tag Pattern Converter |
| `Ctrl + B` | Search Online Metadata (Beatport Scraper) |
| `Ctrl + A` | Run Batch Acoustic Analysis (BPM & Key) |
| `Ctrl + S` | Open Smart File Dispatcher & Organizer |
| `Space` | Play / Pause Selected Track |
| `Double Click` | Load and Audition Track in Mini-Player |

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Developed with ❤️ for the DJ and music collector community by [IlRed89](https://github.com/IlRed89).
