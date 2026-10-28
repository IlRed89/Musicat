<div align="center">
  <img src="assets/icon.png" width="128" height="128" alt="Musicat Icon" />
  <h1>Musicat</h1>
  <p>
    <strong>The Universal DJ Cataloger, Mp3tag-Grade Metadata Engine &amp; Acoustic Smart Organizer.</strong><br>
    <em>Engineered specifically for touring DJs, music collectors, and audio archivists managing massive libraries (50,000+ tracks on external SSDs).</em>
  </p>
</div>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/Lingua-Italiano-green.svg" alt="Language: Italian"></a>
  <a href="README_EN.md"><img src="https://img.shields.io/badge/Language-English-blue.svg" alt="Language: English"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python Version"></a>
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11%20x64%20%7C%20macOS%20Universal-brightgreen.svg" alt="Platform">
  <img src="https://img.shields.io/badge/version-v1.3.0%20(Latest)-blue.svg" alt="Official Version">
  <a href="https://github.com/IlRed89/Musicat"><img src="https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg" alt="Official Repository"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-purple.svg" alt="License"></a>
</p>

---

## 🌟 Overview & Vision

Managing extensive music archives (over **50,000 tracks**) on external SSDs poses critical challenges for DJs and archivists:
- Operating system drive letters on Windows (`D:`, `E:`, `F:`) or mount points on macOS change frequently across USB hubs or computers, breaking traditional media player database paths.
- Console DJ software (Rekordbox, Traktor, Serato, Engine DJ) lacks batch mask tagging tools, automated multi-source metadata reconciliation, and deep acoustic diagnostics.
- Generic tag editors (like Mp3tag) do not provide an integrated audio deck with pitch bending, real-time DSP analysis (BPM, Camelot Key, EBU R128 Loudness), responsive live filtering, or streaming chart integration.

**Musicat** bridges this gap by uniting 10 advanced macro-modules into a modern, responsive, high-contrast desktop application (clean light theme by default, seamless hot-swappable Dark Mode), natively supporting **Windows (10/11 x64)** and **macOS (Apple Silicon M-Series + Intel x64)**.

---

## 🚀 Key Modules Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                              MUSICAT v1.3.0                                        |
+----------------------------------------------------------------------------------------------------+
| [📁 Library]  | [🔥 Charts]   | [🏷️ Mp3tag]   | [🔍 Similar]  | [📂 Organize]  | [📦 Crates]  [⚙️] |
| - Drag & Drop | - Streaming   | - Decoupled   | - Cosine.club | - In-App Stack | - M3U8 Rules |      |
| - Clear View  | - 3-Platforms | - $num() Live | - Web Vectors | - Collision    | - Right Dock |      |
| - Quick Access| - Reconcile   | - Track Wizard| - Key & BPM   | - Dry Run      | - Drag/Drop  |      |
+----------------------------------------------------------------------------------------------------+
|         Ultra-Fast Search Engine (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)        |
+----------------------------------------------------------------------------------------------------+
|       Fast-Pass Acoustic DSP Multi-Core (ThreadPoolExecutor, BPM & Camelot Key Sub-Sample)         |
+----------------------------------------------------------------------------------------------------+
|                 libVLC Audio Engine with +/-8% Pitch Bend & Interactive Waveform Scrubbing         |
+----------------------------------------------------------------------------------------------------+
|     DSP Audio Engine (Spotify Pedalboard, FFmpeg libavfilter & JUCE VST3 Plugin Bridge)           |
+----------------------------------------------------------------------------------------------------+
|          Cross-Platform Path Resolver ([VOL:XXXXXXXX] & portable.lock Drive Migration)             |
+----------------------------------------------------------------------------------------------------+
```

### 1. 📁 High-Performance DJ Library, Drag & Drop and Quick Access
- **Direct Table Drag & Drop:** Drag audio files or whole folders directly onto the Library table: Musicat recursively detects audio files (`.mp3`, `.flac`, `.wav`, `.aiff`, `.m4a`, `.ogg`), indexes them into SQLite, and immediately populates the view.
- **`[🧹 Clear View]` Button:** Instantly clears the visible table without deleting physical files from disk or clearing SQLite database records, providing a fresh workspace on demand.
- **Quick Access Sidebar:** Top left navigation pane featuring 1-click system folder shortcuts:
  - 🖥️ **Desktop**
  - 📁 **Documents**
  - 📥 **Downloads**
  - 🎵 **Music**
  - Followed by **"This PC / Drives"** displaying connected logical disk drives.
- **Responsive Layout & Fluid Overflow:** Filter bar wrapped inside a smooth horizontal `QScrollArea`, completely preventing text clipping or button overlapping on compact resolutions or resized windows.
- **Enriched Context Menu:** Right-clicking on selected tracks presents:
  - **`[⚡ Analyze Selected Tracks]`** (bold, first entry): launches acoustic DSP and metadata analysis solely on chosen files.
  - **`[🏷️ Send to Tag Editor (Mp3tag)...]`**: routes selected tracks into the tagger workspace without resetting or affecting the library table.

### 2. ⚡ Fast-Pass Multi-Core Acoustic Analysis
- **Dynamic Multi-Thread Pool (`ThreadPoolExecutor`):** Multi-track concurrent processing scaled to physical CPU cores (`os.cpu_count()`), ensuring a non-blocking GUI with synchronized, thread-safe SQLite commits.
- **Fast-Pass Acoustic Analysis:** Instant BPM and Camelot Key estimation analyzing an optimized central window (60–90 seconds starting from 25% track duration), slashing I/O and decoding overhead by 80%.
- **Aggressive Scraping Timeouts:** Strict 2.5s – 3.0s timeouts on network scrapers (Discogs, MusicBrainz, WebEnricher/Wikipedia/YouTube), preventing queue stalls on slow external providers.

### 3. 🏷️ Dedicated Mp3tag Workspace & Bulk Pattern Tagging
- **Complete Decoupling from Library:** Zero automatic view synchronization or wiping when switching tabs. Mp3tag loads tracks only when explicitly asked.
- **Dedicated Internal Commands:**
  - Toolbar & menu actions: **`[➕ Add Files...]`**, **`[📁 Add Folder...]`**, **`[🧹 Clear List]`**, **`[💾 Save Changes]`**.
  - **Autonomous Drag & Drop:** Drop files directly onto the Mp3tag table to edit isolated batches.
- **Track Numbering Wizard (`TrackNumberingWizardDialog`):** Automatic sequential numbering with 2-digit zero padding (`01, 02...`), fractional format (`01/12`), initial offset, and auto-reset on folder/album changes.
- **Bidirectional Live Pattern Converters:**
  - *Filename ➔ Tag (`FilenameToTagDialog`):* Smart metadata extraction with tokens (`%artist%`, `%title%`, `%album%`, `%bpm%`, `%key%`, `%year%`, `%genre%`) and `$num(%track%,2)` support.
  - *Tag ➔ Filename (`TagToFilenameDialog`):* Batch disk renaming with live colored preview.
- **Quick Macros:** Case normalization (*Title Case*, *UPPERCASE*, *lowercase*), promo tag stripping (`[FREE DOWNLOAD]`, `[Extended Mix]`), and 2-digit track padding.

### 4. 🔊 DSP Audio Engine, Loudness Metering & Mastering
- **1-Click Profiles & Transparent Modes:**
  - *ReplayGain (metadata only)*, *Physical normalization (new MP3 _normalized.mp3)*, and *Safe overwrite (with backup in _original/)*.
  - Studio presets: *DJ Club (-10 LUFS)*, *Streaming (-14 LUFS)*, *Anti-Clipping & Clean*, *Warm Analog*, *DJ Punch*, *Vocal Clarity*.
- **EBU R128 & ITU-R BS.1770-4 Compliance:** Integrated Loudness (LUFS), True Peak with 4x sinc oversampling (dBTP), and Loudness Range (LRA).
- **Interactive Glossary `[ℹ️ Explanation of Terms]`:** Plain explanations of LUFS, True Peak dBTP, and dynamics for DJs and producers.
- **Default Bundled FFmpeg:** Automatic resolution of the pre-bundled `bin/ffmpeg.exe` binary within the app folder, with optional "Browse..." dialog for custom system installations.

### 5. 🔑 Streamlined Online Account Authentication (OAuth2 & API Key)
- **Spotify:** Modern OAuth2 Authorization Code flow with `response_type=code`, loopback listener `http://localhost:8888/callback`, and library read/write scopes.
- **SoundCloud:** Direct session token fallback to bypass closed public OAuth app registration.
- **YouTube Data API v3:** Google Cloud API Key authentication with real-time live key validation test, preventing `401: invalid_client` errors.

### 6. 🎨 Hot-Swappable Theme Engine & Clean UI
- **Instant Hot Theme Switching:** Seamless light/dark mode transitions via `QApplication` stylesheet injection and widget re-polishing without closing or reloading the Settings dialog.
- **Standardized Form Controls:** Uniform checkbox styles and spacing across all tabs, including the Accounts and Services panel.

---

## ⌨️ DJ Console Keyboard Shortcuts

| Shortcut | Action | Description |
|---|---|---|
| `Ctrl + F` | Quick Search | Focus unified search bar (Everything MFT / Spotlight / FTS) |
| `Ctrl + G` | Genre Filter | Focus genre dropdown with autocomplete |
| `Ctrl + B` | BPM Filter | Focus Target BPM filter |
| `Ctrl + K` | Camelot Wheel | Open visual Camelot wheel assistant for harmonic mixing |
| `Esc` | Reset Filters | Instantly clear all active filters and show entire library |
| `Space` | Play / Pause | Start or pause playback in audio deck |
| `Enter` | Load to Deck | Load highlighted track into player |
| `Ctrl + O` | Add Files (Mp3tag) | Select and import audio files into Tag Editor |
| `Ctrl + D` | Add Folder (Mp3tag) | Recursively import a folder into Tag Editor |
| `Ctrl + S` | Save Changes | Save tags and update SQLite database in Mp3tag |
| `Ctrl + Shift + P` / `Alt + F` | Tag from Pattern | Open advanced pattern mask extraction dialog with live preview |
| `Ctrl + Q` | Quality & Volume | Open EBU R128 loudness and clipping diagnosis |
| `Ctrl + Shift + S` | Find Similar | Discover harmonic and acoustic matches locally and online |
| `Ctrl + L` | Live Log Console | Toggle system logging console dock |
| `Ctrl + ,` | Settings | Open application preferences and service configuration |

---

## 📦 Download & Official Releases

| Platform | File | Description |
|---|---|---|
| **Windows 10/11 x64** | `Musicat-Windows-Portable.zip` | Complete portable bundle (FFmpeg, Qt6, libVLC, zero installation) |
| **Windows 10/11 x64** | `Musicat.exe` | Compiled 64-bit standalone executable for Windows |
| **macOS Universal** | `Musicat-macOS.dmg` | Native DMG disk image with drag & drop installer |
| **macOS Universal** | `Musicat-macOS-Portable.zip` | Portable bundle for external APFS/HFS+ drives |
| **All Platforms** | `SHA256SUMS.txt` | Cryptographic SHA-256 integrity checksums |

👉 **[Download Official Latest Release (v1.3.0)](https://github.com/IlRed89/Musicat/releases/latest)**

---

## 🛠️ Installation & Building from Source

### Prerequisites
- Python 3.11, 3.12, or 3.13 (64-bit)
- `git`
- libVLC (or 64-bit VLC Media Player installed)

### Setup

```bash
# 1. Clone repository
git clone https://github.com/IlRed89/Musicat.git
cd Musicat

# 2. Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS:
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Run targeted test suite
python -m unittest tests/test_performance_and_features.py tests/test_updater.py

# 5. Launch Musicat
python main.py
```

### Standalone Compilation

```bash
# Standalone Windows executable (PyInstaller)
pyinstaller build_windows.spec --clean -y
```

---

## 📄 License

Musicat is open-source software licensed under the **MIT License**.  
See the [LICENSE](LICENSE) file for full legal terms.
