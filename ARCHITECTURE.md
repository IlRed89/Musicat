# 🏛️ Musicat Architecture & Technical Specification

> **Technical Architecture, Data Models, Multiprocessing Pipeline, Logging Subsystem & Cross-Platform Engine Documentation**  
> *Documentazione Tecnica dell'Architettura, Modelli Dati, Pipeline Concorrente, Sottosistema di Logging e Motore Multipiattaforma.*

---

## 1. High-Level Architecture Diagram / Diagramma Architetturale

```mermaid
graph TD
    UI[PySide6 High-Contrast Interface<br/>Light Theme Default / Hot Dark Theme Toggle / Maximized Boot] --> Navbar[Clean Top Navbar<br/>Library / Top Charts / Tag Editor / Similar / Organize / Smart Crates / Settings]
    
    Navbar --> Stack[QStackedWidget 6 Embedded Workspaces]
    Stack --> DJLibrary[Position 1: DJ Library View<br/>Responsive Scroll Overflow, Drag & Drop Table, Quick Access & Clear View]
    Stack --> AnalysisHome[Position 2: Top Charts View<br/>Full-Scroll Trends, Stream Preview 30s & Similar Context]
    Stack --> Mp3tag[Position 3: Independent Tag Editor Mp3tag Workspace<br/>Isolated State, Internal File/Folder Import, Wizard & Bulk Pattern]
    Stack --> Similars[Position 4: Similar Tracks Workspace<br/>Cosine Similarity Engine & Web Vectors Discovery]
    Stack --> Organize[Position 5: Embedded File Organizer<br/>Physical File Dispatcher & Collision Safety]
    Stack --> CratesBench[Position 6: Dedicated Smart Crates Workbench (Docked Right)<br/>Interactive Rule Guide & Extended M3U8 Export]
    Navbar --> Settings[Position 7: Modular Settings Dialog<br/>Hot-Swap Stylesheet, Bundled FFmpeg & Online Accounts]

    DJLibrary --> QuickAccess[Quick Access Sidebar Shortcuts<br/>Desktop / Documents / Downloads / Music & Physical Drives]
    DJLibrary --> FilterBar[Responsive Live Filter Bar in QScrollArea <15ms]
    FilterBar --> FilterEngine[LiveFilterEngine + In-Memory RAM Index]
    FilterEngine --> SearchFactory[Unified Search Engine Factory]

    SearchFactory --> Everything[Windows: Everything64.dll IPC]
    SearchFactory --> Spotlight[macOS: Spotlight mdfind]
    SearchFactory --> SQLiteFTS[Fallback: SQLite FTS5]

    DJLibrary --> Player[libVLC Mini-Player Deck with +/-8% Pitch & Waveform Scrubbing]

    Mp3tag --> PatternEngine[PatternEngine with $num token support]
    Mp3tag --> NumberWizard[Track Numbering Wizard Dialog]
    Mp3tag --> TagEditor[AudioTagEditor Mutagen]
    TagEditor --> Reconciler[Metadata Reconciler]
    Reconciler --> Scrapers[Beatport / Discogs / MusicBrainz / WebEnricher]

    DJLibrary --> ParallelDSP[AsyncAnalysisWorker Dynamic ThreadPoolExecutor]
    ParallelDSP --> FastPassDSP[Fast-Pass Acoustic DSP: Central Window 60-90s at 25%]
    FastPassDSP --> AudioDSP[BPM Autocorrelation & Camelot Chromagram]
    AudioDSP --> RAMCache[L1 AnalysisMemoryCache :memory:]
    RAMCache --> DiskDB[(SQLite WAL Database: Thread-Safe Coordinator Commits)]

    UI --> DspEngine[Advanced Audio DSP Engine src/audio/dsp_engine.py]
    DspEngine --> Pedalboard[Spotify Pedalboard JUCE C++ DSP]
    DspEngine --> Libavfilter[FFmpeg libavfilter adeclip/alimiter/loudnorm]
    DspEngine --> JuceBridge[JUCE External VST3 Plugin Bridge]
    DspEngine --> DspPresets[5 Studio Presets: Club Master, Vocal Clarity, Warm Analog, DJ Punch, De-Clip]

    Settings --> OAuthManager[OAuth & Account Security Manager]
    OAuthManager --> SpotifyOAuth[Spotify OAuth2: response_type=code & Loopback]
    OAuthManager --> SoundCloudAuth[SoundCloud: Session Token Direct Fallback]
    OAuthManager --> YouTubeAPI[YouTube Data API v3: Google Cloud API Key with Live Validation]

    AnalysisHome --> QualityPlugin[Audio Quality & Loudnorm Plugin]
    QualityPlugin --> EBUR128[EBU R128 / True Peak 4x Sinc / FFmpeg loudnorm]

    UI --> StatusBar[Status Bar Telemetry<br/>HardwareProgressBar CPU & RAM with Dynamic Color Thresholds]
    StatusBar --> HwMonitor[HardwareMonitor Asynchronous Poller 1.5s]

    UI --> LoggerSubsys[Structured Logging Subsystem<br/>ZipRotatingFileHandler 20MB & Support Bundle]
    LoggerSubsys --> GuiLog[Thread-Safe GuiLogHandler & Live Dock]
    LoggerSubsys --> LogZipArchive[(Compressed .zip Logs 1..10)]

    UI --> I18nBus[I18n Localization Bus IT/EN]
    I18nBus --> Locales[locales/*.json]
```

---

## 2. Subsystem Breakdown / Componenti del Sistema

### A. User Interface & Responsive Architecture (`src/gui/`)
- **Responsive Layout & Overflow Protection (`src/gui/live_filters.py`):**
  - La barra comandi e filtri della libreria è incapsulata in una `QScrollArea` orizzontale fluida con rimozione di larghezze minime vincolanti, eliminando qualsiasi sovrapposizione di widget o taglio di etichette su display a bassa risoluzione o finestre ridotte.
- **Drag & Drop Diretto sulla Tabella (`LibraryTableView` in `src/gui/main_view.py`):**
  - Supporto nativo agli eventi `dragEnterEvent`, `dragMoveEvent` e `dropEvent`. Il rilascio di file o cartelle esegue la scansione asincrona dei formati audio supportati, l'inserimento nel database SQLite e l'aggiornamento immediato del modello della tabella.
- **Pulsante "Svuota Vista" (`btn_clear_view`):**
  - Consente di azzerare la vista tabellare (`table_model.clear_view()`) senza cancellare fisicamente i file dal disco rigido né rimuovere le voci dal database, offrendo un piano di lavoro pulito all'utente.
- **Barra Laterale ad Accesso Rapido (`sidebar_widget` in `src/gui/main_view.py`):**
  - Riorganizzata con cartelle di sistema in cima (Desktop, Documenti, Download, Musica) risolte dinamicamente tramite `Path.home()`, seguite dalla sezione "Questo PC / Dischi" con l'albero delle sole unità di memorizzazione.
- **Menu Contestuale Avanzato:**
  - Primo elemento in grassetto **`[⚡ Analizza Tracce Selezionate]`** per elaborazione mirata delle sole righe selezionate.
  - Voce **`[🏷️ Invia a Tag Editor (Mp3tag)...]`** per instradare le tracce scelte al modulo di tagging senza azzerare la libreria.
- **Cambio Tema a Caldo (Hot-Swapping):**
  - Commutazione istantanea tra tema chiaro e tema scuro applicata a livello di `QApplication.setStyleSheet()` e `style().polish()` senza distruggere i widget né chiudere la finestra delle Impostazioni.

---

### B. Parallel Acoustic DSP & Fast-Pass Analysis Pipeline (`src/audio/`)
L'estrazione delle caratteristiche acustiche dei brani (BPM, tonalità Camelot, True Peak, LUFS) sfrutta una pipeline multi-core altamente ottimizzata:

```mermaid
flowchart TD
    Select[User Selection / Drag & Drop Tracks] --> Coordinator[AsyncAnalysisWorker on Qt Coordinator Thread]
    Coordinator --> Pool[concurrent.futures.ThreadPoolExecutor max_workers=os.cpu_count]
    
    subgraph Parallel Worker Tasks
        Pool --> Task1[Track 1: Fast-Pass Audio Slice]
        Pool --> Task2[Track 2: Fast-Pass Audio Slice]
        Pool --> TaskN[Track N: Fast-Pass Audio Slice]
        
        Task1 --> DSP1[FFT Autocorrelation BPM + Chromagram Key]
        Task2 --> DSP2[FFT Autocorrelation BPM + Chromagram Key]
        TaskN --> DSPN[FFT Autocorrelation BPM + Chromagram Key]
    end
    
    DSP1 --> Queue[Safe Inter-Thread Result Queue]
    DSP2 --> Queue
    DSPN --> Queue
    
    Queue --> SerialCommit[Serialized SQLite Database Commit on Main Worker Thread]
    SerialCommit --> ModelNotify[TrackTableModel rowChanged & UI Progress Update]
```

1. **Parallelizzazione Multi-Core:**
   - La classe `AsyncAnalysisWorker` alloca un `ThreadPoolExecutor` dimensionato dinamicamente (`max(2, min(os.cpu_count(), 8))`). L'elaborazione DSP intensiva avviene simultaneamente su più core logici.
2. **Fast-Pass Acoustic Analysis (`load_audio_sample` in `src/audio/analyzer.py`):**
   - Non effettua la decodifica dell'intero file audio; cerca (*seek*) il punto corrispondente al 25% della durata complessiva e carica un campione centrale rappresentativo di 60–90 secondi, riducendo l'overhead di I/O su dischi USB e l'uso di memoria RAM di oltre l'80%.
3. **Scraping Asincrono con Timeout Rigidi:**
   - Le interrogazioni di arricchimento verso Discogs, MusicBrainz e WebEnricher impiegano timeout stringenti (2.5 – 3.0 secondi), garantendo che eventuali colli di bottiglia di rete non rallentino la coda di elaborazione dei brani.

---

### C. State Isolation & Decoupling tra Libreria e Mp3tag Workspace (`src/gui/mp3tag_workspace.py`)
Musicat garantisce la totale indipendenza dello stato del Tag Editor:

1. **Disaccoppiamento della Vista:**
   - Il passaggio alla schermata Mp3tag (`_switch_view`) non esegue più alcun caricamento o azzeramento automatico della griglia dati. Lo spazio di lavoro conserva esattamente i file aperti dall'utente fino a esplicito salvataggio o svuotamento.
2. **Canali di Input Espliciti:**
   - Tracce inviate tramite click destro dalla Libreria (`[🏷️ Invia a Tag Editor (Mp3tag)...]`).
   - Pulsanti toolbar/menu dedicati: `[➕ Aggiungi File...]` (`Ctrl+O`), `[📁 Aggiungi Cartella...]` (`Ctrl+D`), `[🧹 Svuota Elenco]`.
   - Drag & Drop diretto di file e directory sulla finestra del workbench (`Mp3tagTableWidget`).
3. **Editor Massivo Pattern e Rinumerazione:**
   - `FilenameToTagDialog` e `TagToFilenameDialog` consentono l'estrazione e la scrittura fisica di token avanzati (`%artist%`, `%title%`, `%album%`, `$num(%track%,2)`).
   - `TrackNumberingWizardDialog` gestisce la numerazione sequenziale con azzeramento al cambio di cartella/album e padding personalizzato.

---

### D. Audio DSP Engine & Mastering Pipeline (`src/audio/dsp_engine.py`)
1. **Spotify Pedalboard & Vectorized Fallback:**
   - C++ DSP engine basato su JUCE (`HighpassFilter`, `LowpassFilter`, `PeakFilter`, `Compressor`, `Limiter`).
   - In caso di assenza dei binari compilati, interviene il processore vettoriale NumPy/SciPy con filtri Butterworth e limiter soft-saturation (`tanh`).
2. **FFmpeg libavfilter Pipeline Broadcast:**
   - De-clipping digitale (`adeclip`), noise reduction (`afftdn`), equalizzazione e limiting con lookahead (`alimiter`).
   - Risoluzione automatica di `ffmpeg.exe` e `ffprobe.exe` integrati nella cartella `bin/` portatile, con supporto a binari personalizzati configurabili in Impostazioni.
3. **5 Preset Mastering per DJ:**
   - *Club Master* (-0.5 dBTP), *Vocal Clarity*, *Warm Analog*, *DJ Punch*, *De-Clip & Clean*.

---

### E. OAuth & Online Accounts Authentication Engine (`src/core/oauth_manager.py`, `src/services/spotify_auth.py`)
1. **Spotify Authorization Code Flow (`SpotifyAuth`):**
   - Costruzione standard conforme dell'URL: `https://accounts.spotify.com/authorize` con `response_type=code`, `client_id`, `redirect_uri=http://localhost:8888/callback` e scope per la lettura e manipolazione delle playlist.
   - Gestione server di loopback locale per la ricezione sicura del codice di autorizzazione e lo scambio con token Bearer.
2. **SoundCloud Session Token Fallback:**
   - Supporto all'immissione manuale sicura del token di sessione per aggirare la chiusura delle registrazioni di nuove app per sviluppatori su SoundCloud.
3. **YouTube Data API v3:**
   - Supporto Google Cloud API Key con test asincrono di validazione immediata, eliminando gli errori `401: invalid_client` per le ricerche pubbliche.

---

### F. Multi-OS Packaging & Release Pipeline
1. **PyInstaller Spec (`build_windows.spec`):**
   - Riconoscimento automatico delle dipendenze C++ native (PySide6, soundfile, scipy, pedalboard, vlc, onnxruntime).
   - Inclusione degli asset, delle cartelle `locales/` e dei binari predefiniti `bin/ffmpeg.exe`.
2. **Portabilità Totale (`portable.lock`):**
   - Il rilevamento del file `portable.lock` dirotta tutte le scritture di database, configurazione e log nella directory locale dell'applicazione, consentendo l'uso immediato da chiavette USB su qualsiasi workstation.

---

## 3. Database Schema / Schema SQLite (`src/core/db.py`)

```sql
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory TEXT NOT NULL,
    filesize INTEGER,
    file_mtime REAL,
    duration REAL,
    bitrate INTEGER,
    sample_rate INTEGER,
    format TEXT,
    title TEXT,
    artist TEXT,
    album TEXT,
    album_artist TEXT,
    year INTEGER,
    genre TEXT,
    track_num INTEGER,
    total_tracks INTEGER,
    disc_num INTEGER,
    bpm REAL,
    musical_key TEXT,
    camelot_key TEXT,
    initial_key TEXT,
    energy_level INTEGER,
    rating INTEGER,
    label TEXT,
    remixer TEXT,
    comment TEXT,
    has_cover INTEGER DEFAULT 0,
    lufs REAL,
    true_peak REAL,
    audio_status TEXT,
    waveform_peaks BLOB,
    analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    title, artist, album, genre, label, remixer, comment, filename,
    content='tracks', content_rowid='id'
);
```
