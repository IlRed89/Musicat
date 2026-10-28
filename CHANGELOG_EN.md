# 📋 Changelog

All notable changes and official releases for **Musicat** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Language: Italian](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)
[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)

---

## [1.3.0] - 2026-10-28 — Official Consolidated Release

Official consolidated release of **Musicat** introducing accelerated multi-thread audio analysis, an adaptive responsive layout for compact displays, direct Drag & Drop import, Quick Access shortcuts in the file navigation sidebar, complete decoupling of the Mp3tag Tag Editor, and streamlined online service authentication.

### 🌟 What's New in v1.3.0

#### 1. ⚡ Accelerated Acoustic Analysis & Multi-Thread Parallelization
- **Dynamic Thread Pool Worker:** `AsyncAnalysisWorker` processes audio analysis via a `ThreadPoolExecutor` sized to the available physical CPU cores (`os.cpu_count()`), handling multiple tracks concurrently without freezing the user interface.
- **Fast-Pass Acoustic Analysis:** Implemented rapid sampling on an optimized central window (60–90 seconds starting at 25% track duration) for BPM and Camelot Key estimation, drastically reducing I/O and CPU decoding time.
- **Strict Scraping Network Timeouts:** Aggressive 2.5s – 3.0s timeouts on all external metadata lookups (Discogs, MusicBrainz, Wikipedia, YouTube), preventing analysis queues from stalling on unresponsive connections.

#### 2. 📱 Adaptive Responsive Layout & Overflow Elimination
- **Fluid Horizontal Filter Bar:** Live filter and control bar wrapped in an invisible horizontal `QScrollArea`, preventing button clipping and text cutoffs on small monitors or narrow window sizes.
- **Calibrated Spacing & Min-Widths:** Standardized minimum widget dimensions across all toolbars for consistent scaling at any window resolution.

#### 3. 🧹 "Clear View" Button in Library
- **1-Click Visual Reset:** Added the `[🧹 Clear View]` button in the Library toolbar (`table_model.clear_view()`), allowing users to immediately empty the visible table without deleting physical files from disk or touching database records.

#### 4. 📂 Direct Drag & Drop onto Library Table
- **Rapid File and Folder Import:** Native `dragEnterEvent` and `dropEvent` support on the main library table, automatically detecting audio files (`.mp3`, `.flac`, `.wav`, `.aiff`, `.m4a`, `.ogg`), indexing them into SQLite, and populating the table.

#### 5. 🖥️ Quick Access Section in File Explorer
- **System Folder Shortcuts:** Redesigned the left sidebar to feature a pinned Quick Access group with native icons for Desktop, Documents, Downloads, and Music, followed by the "This PC / Drives" volume explorer.

#### 6. ⚡ Context Menu with Dedicated "Analyze" Action
- **Targeted Selection Analysis:** First right-click context menu item in bold: **`[⚡ Analyze Selected Tracks]`**, initiating DSP and metadata analysis strictly on highlighted items.
- **Tag Editor Routing:** Direct routing action **`[🏷️ Send to Tag Editor (Mp3tag)...]`** to immediately load selected tracks into the Mp3tag workspace.

#### 7. 🏷️ Complete Decoupling of Mp3tag Workspace
- **Isolated View State:** Removed automatic view synchronization or wiping when switching between Library and Mp3tag.
- **Autonomous Load Actions:**
  - Added dedicated toolbar and menu buttons: `[➕ Add Files...]` (`Ctrl+O`), `[📁 Add Folder...]` (`Ctrl+D`), `[🧹 Clear List]`.
  - Independent Drag & Drop support directly on the Mp3tag table (`Mp3tagTableWidget`).

#### 8. 🔑 Modernized OAuth2 & Online Services
- **Standard-Compliant Spotify OAuth2:** Authorization URL generation with explicit `response_type=code`, `client_id`, `redirect_uri=http://localhost:8888/callback`, and playlist read/write scopes.
- **SoundCloud Token Fallback:** Direct session token entry to bypass closed public developer app registrations.
- **YouTube Data API v3:** Direct Google Cloud API Key authentication with real-time validation test, avoiding `401: invalid_client` errors.

#### 9. 🎨 Seamless Hot Theme Switching & Bundled FFmpeg
- **Instant Hot-Swappable Themes:** Dynamic light/dark theme switching applied at runtime via `QApplication` stylesheet without closing or reloading Settings.
- **Pre-Bundled FFmpeg:** Automatic detection and usage of the bundled binary at `bin/ffmpeg.exe`, with status indicator and optional "Browse..." button.

---

## [1.2.0] - 2026-10-19 — Official Consolidated Release

- Studio-grade DSP engine powered by Spotify Pedalboard, FFmpeg libavfilter, and JUCE VST3.
- Dynamic column width autofit with +16px anti-ellipsis safety margin.
- Maximized fullscreen boot by default.
- Top navigation bar reorganization with Smart Crates docked on the right.
- Restored "Similar" button in the player deck and isolated Top Charts context.
