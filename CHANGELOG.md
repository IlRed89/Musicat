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

#### 📊 Acoustic Analysis & Harmonic Mixing
- Non-destructive BPM detection via onset envelope spectral flux and autocorrelation.
- Camelot Wheel Key detection (`1A`–`12B`) via 12-bin chromagram and Krumhansl-Schmuckler profiles.
- Harmonic mixing compatibility finder (relative keys, $\pm 1$, $+2$ energy boosts).

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

