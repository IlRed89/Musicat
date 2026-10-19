# 📋 Changelog

All notable changes and official features of **Musicat** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)
[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)

---

## [1.2.0] - 2026-10-19 — Official Consolidated Release

Official consolidated release of **Musicat**, introducing professional DSP audio mastering (Spotify Pedalboard, FFmpeg libavfilter & JUCE VST3), dynamic Library column autofit, maximized fullscreen boot, ergonomic top navbar reordering, and restored player "Simili" button with isolated Top Charts context.

### 🌟 New Features & Enhancements in v1.2.0

#### 1. 🎛️ Professional Audio DSP Processing Engine (`src/audio/dsp_engine.py`)
- **Native Spotify Pedalboard:** Direct integration of JUCE C++ framework components (`HighpassFilter`, `LowpassFilter`, `PeakFilter`, `Compressor`, `Limiter`, `Clipping`, `Distortion`, `NoiseGate`).
- **Vectorized NumPy/SciPy Fallback:** Automatic high-precision numerical DSP processor fallback using 2nd-order Butterworth filters and soft-saturation limiter (`tanh`) if native C++ wheels are absent.
- **FFmpeg libavfilter Broadcast Pipeline:** Professional filtering for de-clipping (`adeclip`), noise reduction/de-click (`afftdn`), surgical EQ (`highpass`, `lowpass`, `equalizer`), dynamic EBU R128 loudness normalization (`loudnorm`), and lookahead broadcast safety limiting (`alimiter`).
- **JUCE VST3 Plugin Hosting Bridge:** Load and execute external compiled VST3 plugins using Pedalboard's native JUCE C++ wrapper (`load_plugin`) with error suppression and resilience on Windows.
- **5 Studio-Grade DJ & Mastering Presets:**
  - *"Club Master":* Sub-bass cut 30Hz, punchy bass boost at 60Hz (+2.5dB), glue compression, and brickwall peak limiting at -0.5 dBTP for club sound systems;
  - *"Vocal Clarity":* High-pass 80Hz, presence boost 3.8kHz, de-essing 6.5kHz, and transparent optical compression;
  - *"Warm Analog":* Smooth high roll-off (18.5kHz), 120Hz body warmth, and subtle harmonic soft-clipping saturation;
  - *"DJ Punch":* Kick transient punch (85Hz) and snare snap (2.2kHz) with assertive dynamic control;
  - *"De-Clip & Clean:* Digital de-clipping reconstruction, background hiss noise reduction, and safe peak limiting at -1.5 dBTP.
- **MP3 (320 kbps CBR / V0 VBR) & Lossless FLAC Export:** Complete cloning and preservation of ID3v2.4 / Vorbis comment tags and HD cover art.

#### 2. 📐 Dynamic Table Column Autofit (+16px Safety Margin)
- **Automatic Content Width Adaptation:** On library load, refresh, and folder scan completion, all table columns automatically adapt to fit the longest cell content (`resizeColumnsToContents()`), with a 16px horizontal safety margin to prevent ellipsis truncation (...) on long titles, artists, albums, or paths.
- **User Preference Preservation:** Manual column resizing and drag-and-drop column reordering remain fully functional without unexpected resets during scrolling or row selection.

#### 3. 🖥️ Default Fullscreen Maximized Boot
- **Automatic Maximized Launch:** Launches directly in maximized fullscreen mode on boot (`window.showMaximized()`), instantly providing maximum display real estate for DJ library management.

#### 4. 🧭 Top Navigation Bar Reordering
- **"Smart Crates" Relocated to Far Right:** Optimized macro navigation hierarchy:
  1. *Library* (Default primary workstation)
  2. *Top Charts* (Multi-platform trends and stream previews)
  3. *Tag Editor* (Mp3tag spreadsheet)
  4. *Find Similar* (Vector discovery)
  5. *Organize Files* (Disk dispatcher)
  6. *Smart Crates* (Docked right before Settings)
  7. *Settings* (Configuration modal)

#### 5. 🎯 Restored Player "Simili" Button & Strict Top Charts Context
- **Player Deck "Simili" Button:** Re-enabled `btn_similar` in mini-player controls with a non-blocking tooltip when no track is loaded and immediate routing to Find Similar.
- **Top Charts Context Isolation:** Clicking "Simili" on chart cards or rows strictly targets the selected chart song (`set_target_track`), routing streaming previews when local audio is absent and ensuring compatibility with `affinity_score`, `score`, and `affinity` properties.
- **Crash Resolution:** Fixed missing signal attribute error (`play_requested` vs `play_track_requested`) and positional keyword argument collision in `_t()`.

#### 1. 🌐 Cascading Multi-Source Metadata Scraping Engine
- **Intelligent Multi-Provider Cascade:** Asynchronous parallel querying of the world's leading music databases:
  - **Discogs API:** Identifies original Master Release year and prioritizes granular electronic `styles` (e.g. *Tech House*, *Melodic Techno*, *Afro House*, *Deep House*) over generic *"Electronic"* classifications.
  - **MusicBrainz / AcousticBrainz:** Retrieves earliest original release date and community-curated genre tags.
  - **Beatport & Traxsource:** Targets precise dance and club subgenres for accurate DJ classification.
  - **WebEnricher Fallback (Wikipedia Knowledge Graph & YouTube Search):** When musical databases yield no exact match, executes web queries `"[Artist] - [Title] genre year"` to parse release date and verified music genres.
- **Strict Genre Normalization:** Automatically filters out vague, generic labels (*Other*, *Unknown*, *Soundtrack*, *Music*, *Various*, *General*), enforces granular subgenre priority, and assigns `"Vario"` strictly as the absolute last resort.
- **Asynchronous Reconciler Dialog (`ReconcilerDialog`):** Clear four-column layout (*Field*, *Current Value*, *Detected Value*, *Value to Apply*) with comfortable 36px row height, elastic responsiveness, and full Italian localization.

#### 2. 📁 High-Performance DJ Library & Drag & Drop Column Reordering
- **Default Startup Screen:** Launches directly into the main DJ Library view (Index 0 of the central workspace container).
- **Interactive Drag & Drop Column Reordering:** Movable table header (`setSectionsMovable(True)`, `setDragEnabled(True)`) for instant visual customization of column sequence.
- **Hexadecimal Header State Persistence:** Visual column order, column visibility, and individual pixel widths are serialized via `saveState()` into hex strings stored in `config.json` (`ui.header_state`), restored automatically on application launch.
- **Essential DJ Columns by Default:** Superfluous internal diagnostic fields (`energy_level`, `lufs`, `true_peak`, `audio_status`) are hidden by default, leaving maximum readable space for the 12 core DJ performance columns: `#`, `Cover`, `Titolo`, `Artista`, `Remixer`, `BPM`, `Camelot`, `Key`, `Genere`, `Anno`, `Durata`, `Bitrate`.
- **Header Context Menu (Right-Click):** Toggle visibility for all 19 library columns at will with a 1-click *"Mostra Tutte le Colonne"* action.
- **Left Collapsible Drive & Folder Explorer:** Built-in filesystem tree (`QFileSystemModel`) displaying all connected storage drives, external USB disks, and folders with instant two-way synchronization.
- **Two-Row High-Performance Live Filters (<15ms):** Instant full-text search with automatic path separator normalization (`/` and `\`), BPM target matching with fine percentage tolerances ($\pm 2\% \dots \pm 8\%$), 12-position Camelot wheel with harmonic mixing jumps ($\pm 1$, Relative, $+2$ Energy Boost, $+7$ Semitone Lift), decade ranges, energy, and star ratings.
- **Dynamic Genre ComboBox:** Strictly populated from actual tracks in the SQLite database; features `"🏷️ Tutti i Generi"` at the top, database genres in alphabetical order, and `"Vario"` anchored at the bottom. Enhanced with custom pure CSS chevron dropdown subcontrols (`QComboBox::drop-down` and `QComboBox::down-arrow`) for visible indicators across both Light and Dark themes.

#### 3. ⚡ Dedicated Toolbar "Analyze Selected" Button & Async Worker
- **Primary Toolbar Action `[⚡ Analizza Selezionate]`:** Prominently featured in the DJ Library command bar with distinct accent styling.
- **Flexible Batch Targeting:** Analyzes selected table rows; if no rows are selected, analyzes all tracks within the active folder; displays discrete feedback if neither is targeted.
- **Non-Blocking Multithreaded Worker (`AsyncAnalysisWorker`):** High-throughput acoustic DSP calculations (BPM, Camelot/Musical Key), pattern extraction, and physical tag persistence execute asynchronously in background without freezing the GUI.
- **Discrete Progress Bar & Instant Cancellation:** Status bar progress tracker with an immediate red `[✕ Annulla]` cancellation button.
- **Physical Tag Writing with Mutagen:** Automatically splits `"Artist - Title"` patterns when artist metadata is absent, releases OS file locks, and handles external drive latency gracefully.

#### 4. 🏷️ Embedded Mp3tag Workspace & Bulk Pattern Tagging
- **Full In-App Spreadsheet Workspace:** Comprehensive tabular metadata editing without modal popups.
- **Track Numbering Wizard (`TrackNumberingWizardDialog`):** Sequential track numbering with configurable padding (`01, 02...`), total track count suffix (`01/12`), start offsets, and auto-reset on folder/album boundaries.
- **Bidirectional Live Pattern Converters:**
  - **Filename to Tag (`FilenameToTagDialog`):** Extracts metadata tokens (`%artist%`, `%title%`, `%album%`, `%bpm%`, `%key%`, `%year%`, `%genre%`) with support for advanced `$num(%track%,2)` token formatting.
  - **Tag to Filename (`TagToFilenameDialog`):** Renames audio files on disk using pattern masks with real-time live preview.
- **1-Click Case Converters:** Instant buttons for *Title Case*, *UPPERCASE*, and *lowercase*.

#### 5. 📦 Dedicated Smart Crates Workbench & M3U8 Export
- **Integrated Crates Workbench:** Dedicated embedded section with interactive guidance for rule configuration.
- **Dynamic Filtering Rules:** Construct sophisticated crates matching genre, BPM ranges, compatible Camelot keys, release years, and quality ratings.
- **Universal Playlist Export:** Exports extended M3U / M3U8 playlists directly compatible with Serato DJ, Pioneer Rekordbox, Traktor Pro, and Engine DJ.

#### 6. 🔍 Fast Universal Search & Harmonic Similarity Matching
- **Ultra-Fast Disk Indexing:**
  - **Windows:** Native NTFS Master File Table (MFT) kernel querying via `Everything64.dll` (<1ms for 100,000 files).
  - **macOS:** Native Spotlight driver (`mdfind`) for instant audio file retrieval.
  - **Universal Fallback:** SQLite FTS5 full-text engine compatible with any filesystem or network volume.
- **Harmonic Similarity Discovery:** Local search matching euclidean and cosine similarity across acoustic vectors (BPM, Camelot Key, Loudness), complemented by online discovery on Chosic and Cosine.club.

#### 7. 🔊 libVLC Audio Player, EBU R128 Loudness Meter & Light "Correggi Audio" Dialog
- **Integrated libVLC Audio Engine:** Responsive mini-player with interactive waveform scrubbing, $\pm 8\%$ pitch bending, A-B looping, digital gain, and broad audio format decoding (MP3, WAV, FLAC, AIFF, M4A, OGG).
- **Online Trends Stream Preview:** Instantly plays 30-second audio previews from Spotify, SoundCloud, and Beatport without third-party dependencies.
- **Loudness Meter Deactivated on Unanalyzed Tracks:** Replaces dummy `-70 LUFS / -100 dBTP` readings with a neutral deactivated placeholder `"— LUFS | TP: — dBTP (Non analizzato)"`.
- **Native Light Theme "Correggi Audio" Dialog:** Crisp `#ffffff` canvas, dark text `#212529`, and an educational callout explaining metadata ReplayGain versus physical FFmpeg loudnorm re-encoding (-1.0 dBTP headroom) with interactive target sliders (-9/-10 LUFS for club, -14 LUFS for streaming).

#### 8. ⚪ High-Contrast Interface (Light Theme Default / Dark Mode)
- **Ergonomic Default Palette:** Standard enterprise styling based on high-contrast backgrounds (`#FFFFFF` / `#F8F9FA`), dark legible text (`#212529`), crisp borders (`#DEE2E6`), and electric blue accents (`#0D6EFD`).
- **Instant Dark Mode:** Full dark theme toggle available in Settings without application restarts.
- **Hardware Telemetry Bar:** Status bar progress meters with dynamic color thresholds (Green 0-60%, Orange 61-84%, Red 85-100%) for CPU and 64-bit RAM usage (`RAM X.X / YY GB`).

#### 9. 📂 Physical File Organizer on Disk
- **Massive Batch Dispatching:** Physically re-sorts audio directories by *Artist/Album*, *Genre/BPM*, or custom token schemes.
- **Safety Simulation & Collision Handling:** Built-in *Dry-Run* preview, safe file renaming on collisions, and detailed operation logging.

#### 10. 🩺 Early Bootstrap Diagnostics Suite & Portable Architecture
- **Pre-Bootstrap Cross-Platform Diagnostics:** Immediate line-by-line disk logging before importing heavy GUI or audio libraries, capturing CPU architecture (Apple Silicon ARM64, Rosetta 2, Intel x64), memory statistics, and OS build numbers.
- **Crash Trap Engine:** Native `faulthandler` trap writing stack traces to disk upon unhandled C/C++ exceptions or segmentation faults.
- **Zero-Install Portable Mode:** Auto-detects `portable.lock` to maintain settings, databases, and logs within the application folder on removable drives.
