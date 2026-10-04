# 📋 Registro Modifiche (Changelog)

Tutte le modifiche e le novità di **Musicat** sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto aderisce al [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)
[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)

---

## [1.3.0] - 2026-10-04

### 🚀 Workspace Incorporati (QStackedWidget), Explorer Cartelle a Sinistra, Fix Icona Taskbar & Sincronizzazione Selezione

#### 🖥️ Workspaces Incorporati nella Finestra Principale (Nessuna Finestra Popup Separata)
- **Architettura a 6 Viste Centrali (`QStackedWidget`):** I moduli primari non si aprono più come finestre di dialogo volanti o esterne, ma sono integrati direttamente nell'area centrale dell'applicazione:
  - **Indice 0:** Analisi / Home (`HomeTrendsView`)
  - **Indice 1:** Libreria DJ (`library_container` con tabella, filtri e albero cartelle)
  - **Indice 2:** Tag Editor (`Mp3tagWorkspaceWindow` incorporato in-app)
  - **Indice 3:** Smart Crates (`SmartCratesView`)
  - **Indice 4:** Trova Simili (`SimilarTracksView` con affinità armonica e web discovery integrati)
  - **Indice 5:** Organizza File (`OrganizerView` integrato in-app)
- **Fluidità di Navigazione:** Passaggio istantaneo tra le funzionalità tramite i macro-pulsanti della barra superiore senza interruzione del flusso di lavoro e senza finestre modali bloccanti.

#### 🔄 Sincronizzazione Intelligente dello Stato tra Workspace
- **Passaggio Tracce Selezionate:** Selezionando brani nella tabella della libreria e passando a *Tag Editor (Mp3tag)*, *Trova Simili* o *Organizza File*, le tracce selezionate vengono pre-caricate automaticamente.
- **Ritorno Guidato alla Libreria:** Tutti i workspace secondari incorporano pulsanti e segnali di chiusura/ritorno (`◀ Torna alla Libreria`) per ripristinare immediatamente la visualizzazione principale sincronizzando le modifiche al database.

#### 🗂️ Explorer Cartelle / Drive Spostato a Sinistra
- **Nuovo Layout Splitter:** L'albero di navigazione del filesystem e dei dischi è stato riposizionato sul **lato sinistro** della tabella musicale (layout a due pannelli standard DJ/DAW), con splitter ridimensionabile e pulsante di collasso `◀` / `▶`.

#### 🖼️ Risoluzione Definitiva Icona Barra delle Applicazioni Windows
- **AppUserModelID Esplicito:** Registrazione di un identificativo applicazione univoco di processo (`ilred89.musicat.djcataloger.app.1.0`) all'avvio in `main.py` prima dell'inizializzazione di `QApplication`.
- **Priorità Formati Icona Windows:** Corretta la risoluzione in `PathResolver.get_icon_path()`: su Windows viene data precedenza assoluta al formato nativo `assets/icon.ico` e `assets/icon.png`, impedendo che Windows tenti di caricare il file Apple `.icns` mostrando l'icona bianca generica.

#### 🎨 Navbar Pulita & Stato Pulsanti Uniforme
- **Evidenziazione Tab Attivo:** Tutti i 6 pulsanti dei moduli centrali utilizzano ora uno stile uniforme con evidenziazione chiara del workspace correntemente attivo (`btn_active` blu con testo bianco) rispetto a quelli inattivi (`btn_inactive`).
- **Scorciatoie Tastiera Dirette:** Aggiunte le scorciatoie `Alt+1` .. `Alt+6` per navigare direttamente da tastiera tra tutti i 6 workspace.

#### 🛠️ Risoluzione Deadlock SQLite & Chiusura Cursori nel File Manager
- **Fix Transazioni e Cursori:** Tutti i cursori e le transazioni SQLite in `MusicFileManager` sono ora protetti da blocchi `try...finally`, prevenendo blocchi su file temporanei o durante le operazioni di copia/incolla.

---

## [1.2.0] - 2026-10-04

### 🚀 Menu Colonne Tasto Destro, Barra Filtri 2-Righe, Trend Multi-Piattaforma, Discogs Priority & Allocazione RAM 80%

#### 🎛️ Gestione Colonne Contestuale & Persistenza Larghezze
- **Menu Contestuale Header Tabella:** Cliccando con il tasto destro su una qualsiasi intestazione della libreria viene visualizzato un menu a comparsa con l'elenco completo delle colonne e checkbox interattive per mostrare/nascondere le colonne in tempo reale.
- **Salvataggio Automatico Larghezze e Visibilità:** Il ridimensionamento manuale delle colonne e la loro visibilità vengono memorizzati all'istante in `config.json` (`ui.column_widths` e `ui.visible_columns`) e ripristinati a ogni avvio.
- **Rimozione Ridondanza nelle Impostazioni:** Rimossa la vecchia selezione manuale delle colonne dalla schermata Impostazioni, sostituita da un box guida chiaro ed esplicativo sull'uso del tasto destro.

#### ⚪ Bonifica Totale Tema Chiaro & Fix Visivo GPU
- **Pulizia Radicale Residui Scuri:** Bonificate tutte le sidebar laterali, schede interne e pannelli secondari nelle Impostazioni con sfondo uniforme chiaro (`#F8F9FA` / `#FFFFFF`), bordi leggeri (`#DEE2E6`) e testo scuro ad alto contrasto (`#212529`).
- **Card Informative in Analisi / Home:** Riquadri e card di generi e trend convertiti a sfondo bianco puro (`#FFFFFF`), con bordo discreto (`#D0D7DE`), angoli arrotondati (8px) ed effetto hover morbido (`#F8F9FA`, bordo `#0D6EFD`).
- **Riquadro Accelerazione Hardware GPU:** Eliminato qualsiasi sfondo scuro residuo; layout aggiornato con sfondo bianco, badge di stato verde chiaro e parametri ben leggibili.

#### 🧠 Allocazione Dinamica RAM Fino all'80% di Sistema
- **Rimozione Limite Fisso 2 GB:** Eliminato il tetto rigido dei 2 GB per la memoria cache.
- **Rilevamento RAM Reale di Sistema:** Utilizzo delle API native di sistema (`GlobalMemoryStatusEx` su Windows, `psutil`) per determinare la memoria fisica totale installata.
- **Slider Dinamico:** Corsa da un minimo di 512 MB fino all'**80% della RAM totale** installata (es. fino a 12.8 GB su 16 GB, oltre 25 GB su 32 GB), con etichetta interattiva in tempo reale: `Allocati: X.X GB / Y.Y GB totali`.

#### 🌐 Sezione Scrapers & API Credentials Espansa
- **Supporto Piattaforme Complete:** Inserimento e persistenza di chiavi API e credenziali per Spotify (Client ID & Secret), SoundCloud (Client ID & Auth Token), YouTube Data API v3 (API Key), Discogs (User-Agent + Personal Access Token) e Beatport.
- **Test Connessione Live con Feedback Visivo:** Ciascuna fonte dispone del proprio pulsante *"Verifica Connessione"* che testa le API in tempo reale e mostra un indicatore visivo immediato di successo (verde) o errore (rosso con messaggio dettagliato).

#### 💿 Discogs come Autorità Prioritaria nei Metadati
- **Client Discogs Avanzato:** Parsing approfondito di formato vinile/digitale, etichetta discografica primaria, numero di catalogo (`catno`) e crediti artisti.
- **Riconciliazione Gerarchica:** Aggiornato `MetadataReconciler` per accordare a Discogs la massima priorità autorevole per Anno, Etichetta, Numero di Catalogo, Formato e Artista, superando le fonti generiche.
- **Scraper Dialog Predefinito:** Selettore dello Scraper con Discogs preselezionato come provider prioritario.

#### 📈 Dashboard Trends Multi-Piattaforma & Classifiche
- **Suddivisione per Sorgente a Schede:** Introdotte le schede dedicate `Top Spotify`, `Top SoundCloud / Hype`, e `Top Beatport / Discogs`.
- **Categorie Specifiche:** Aggiornamento contestuale delle categorie musicali in base alla piattaforma selezionata (Dance, Tech House, Melodic Techno, Indie Dance, Drum & Bass, Nu-Disco, ecc.).
- **Dataset Offline Estesi & Cache Indipendente:** Fallback offline ricchi per ciascuna piattaforma e cache JSON isolata per sorgente per navigare velocemente senza latenza.
- **Cross-Check con Libreria Locale:** Riconoscimento istantaneo dei brani di tendenza già presenti nella collezione locale con badge visivo dedicato.

#### 🎚️ Barra Filtri Live a Due Righe (Risoluzione Troncatura Key & BPM)
- **Riga 1 (Ricerca e Organizzazione):** Barra di ricerca testuale con indicatore motore (Everything/Spotlight/FTS5), selettore cartella/drive di scansione, dropdown multi-genere (logica OR), filtro presenza copertina e pulsante Reset (ESC).
- **Riga 2 (Parametri Musicali DJ):**
  - Sezione BPM espansa: Box target con controlli passo, preset percentuali rapidi (`±2%`, `±4%`, `±6%`, `±8%`) e slider/box per range minimo e massimo.
  - Sezione Camelot Key: Dropdown allargato con piena leggibilità di codici Camelot e tonalità musicali aperte, checkbox "Solo Armonici" e pulsante Ruota Camelot interattiva.
  - Filtri per decennio/anno, qualità audio (Lossless/High/Standard), tag DJ ed esportazione Smart Crates.

#### ❓ Guida Integrata & Tooltip per Smart Crates
- **Finestra Guida Interattiva:** Aggiunto il pulsante `"❓ Guida all'uso"` nel workbench Smart Crates che apre la nuova finestra `SmartCratesHelpDialog`.
- **Esempi Pratici per DJ:** Spiegazione approfondita delle logiche AND/OR, tabelle con preset tipici da console (*Warm-up Set*, *Peak Time Banger*, *Classic House*, *Harmonic Mixes*) e istruzioni per l'esportazione M3U8 compatibile con Pioneer CDJ, Rekordbox, Traktor, Serato ed Engine DJ.
- **Tooltip Completi:** Aggiunti tooltip descrittivi su tutti i campi, selettori e pulsanti dell'editor delle regole.

#### 🧭 Icone Rappresentative sui Tasti Navbar
- **Identità Visiva Rinnovata:** Ciascun pulsante della barra superiore include un'icona tematica ed esplicativa:
  - `[🏠 Analisi / Home]`
  - `[📁 Libreria]`
  - `[🏷️ Tag Editor (Mp3tag)]`
  - `[📦 Smart Crates]`
  - `[🔍 Trova Simili]`
  - `[📂 Organizza File]`
  - `[⚙️ Impostazioni]`

#### 🛡️ Robustezza & Prevenzione Crash
- **Hook Globale Eccezioni:** Installazione in `main.py` di un intercettore globale `sys.excepthook` per registrare qualsiasi errore imprevisto nei file di log prima dell'eventuale chiusura.
- **Protezione Navigazione Generi:** Azzerato qualsiasi crash o blocco modale al click su card di generi o categorie quando la libreria è vuota o in fase di caricamento.
- **Suite di Test a 140 Test:** Copertura completa verificata al 100% (`140 passed in 8.9s`).

---

## [1.1.0] - 2026-10-02

### 🚀 Revisione UI/UX, Tema Chiaro Default, Suite di Logging Avanzato & Workbench Smart Crates

#### ⚪ Tema Chiaro Predefinito & Nuova Navbar Modulare
- **Tema Chiaro come Default:** Impostato il tema bianco / chiaro moderno ad alto contrasto (`#FFFFFF` / `#F8F9FA`, testi `#212529`, accenti `#0D6EFD`) come stile predefinito al primo avvio. Opzione Dark Mode sempre selezionabile a caldo dalle Impostazioni.
- **Navbar Minimale Pulita:** Rimozione completa di icone rapide isolate o pulsanti scorciatoia frammentari. La barra superiore contiene esclusivamente i 7 pulsanti di navigazione verso i macro-moduli completi:
  - `[Analisi / Home]`
  - `[Libreria]`
  - `[Tag Editor (Mp3tag)]`
  - `[Smart Crates]`
  - `[Trova Simili]`
  - `[Organizza File]`
  - `[Impostazioni]`
- **Schermata Iniziale Predefinita:** L'applicazione si avvia direttamente nella vista **Analisi / Home** (anziché nella libreria tabellare grezza).
- **Workbench Dedicato Smart Crates:** Rimozione del pannello compresso dalla vista principale in favore di una schermata/workbench indipendente a tutto schermo (`src/gui/views/crates_view.py`) per la creazione visuale di regole complesse ed esportazione in playlist `.m3u8` compatibili con Pioneer CDJ, Rekordbox, Traktor, Serato ed Engine DJ.

#### 📜 Suite di Logging Strutturato per Troubleshooting
- **Rotazione File con Compressione `.zip` (`ZipRotatingFileHandler`):**
  - Limite di dimensione file attivo a **20 MB** (`musicat.log`).
  - Rotazione automatica con compressione in archivio `.zip` (`musicat.log.1.zip`, ..., `musicat.log.10.zip`) con algoritmo `zipfile.ZIP_DEFLATED`.
  - Mantenimento degli ultimi **10 file compressi** con rimozione automatica delle copie storiche più vecchie.
- **Percorsi Adattivi:**
  - Modalità Portabile (`portable.lock`): salvataggio nella cartella locale `./logs/`.
  - Modalità Standard: salvataggio in `%APPDATA%\Musicat\logs` (Windows) o `~/Library/Application Support/Musicat/logs` (macOS).
- **Tracciamento Granulare di Ogni Evento:**
  - **`log_scan` (`[SCAN]`):** Directory scansionate, file trovati, inseriti, scartati ed errori di accesso filesystem.
  - **`log_audio_engine` (`[PLAYER:VLC]`):** Inizializzazione `libvlc`, caricamento stream, play/pause/seek, pitch bending ed errori di decodifica.
  - **`log_tag_edit` (`[TAG]` & `[TAG:DIFF]`):** Dump metadati pre/post modifica in JSON, diff dei campi modificati e rilevamento header ID3 corrotti.
  - **`log_http` (`[HTTP:<Fonte>]`):** Misurazione latenza in millisecondi, logging di URL, parametri, codici di risposta (200, 403, 404) e gestione eccezioni per Beatport, Spotify, Chosic/Cosine, Discogs e MusicBrainz.
  - **`log_file_op` (`[DISPATCH:<OP>]`):** Percorsi fisici sorgente/destinazione (`SRC -> DEST`), strategie di collisione (`RENAME`, `OVERWRITE`, `SKIP`).
- **Live Log Console & Bundle Diagnostico:**
  - Dock live dei log (`Ctrl + L`) con filtro di livello (`DEBUG`, `INFO`, `WARNING`, `ERROR`), toggle di auto-scroll e pulizia istantanea.
  - Pulsante **"Esporta Log per Assistenza (.zip)"** sia nella Live Console che nelle Impostazioni, per generare un pacchetto diagnostico con log, statistiche hardware anonime, stato database e configurazione sanificata.

#### 🧠 Commenti Algoritmici & Documentazione Tecnica (Sphinx/Google Style)
- **Acoustic Analyzer (`src/audio/analyzer.py`):** Spiegazione dell'algoritmo STFT, filtraggio banda musicale C2-C7, mappatura continua semitoni MIDI, accumulo vettore cromatico a 12 bin, correlazione di Pearson circolare con i profili Krumhansl-Schmuckler e stima BPM tramite autocorrelazione del flusso spettrale.
- **Audio Quality Analyzer (`src/plugins/quality_analyzer/analyzer.py`):** Documentazione ITU-R BS.1770-4 Annex 2 con sovracampionamento polifase sinc/FIR 4x per intercettare i picchi inter-sample (True Peak in dBTP), rilevamento flat-top clipping e filtri K-weighting EBU R128 con doppio gating.
- **Metadata Reconciler (`src/scrapers/reconciler.py`):** Dettagli sulla gerarchia di autorevolezza delle fonti musicali, voto di maggioranza e tie-breaker.
- **Everything MFT Search (`src/core/everything_search.py`):** Documentazione del meccanismo IPC Windows di Voidtools Everything, messaggi `WM_COPYDATA` e binding `ctypes`.

#### 🎛️ Gestione Colonne Tabella Libreria & Monitoraggio Hardware Reale
- **Selezione Colonne con Tasto Destro:** Aggiunto menu contestuale sull'intestazione della tabella libreria (`horizontalHeader`) con elenco spuntabile delle 19 colonne (`#`, `Cover`, `Titolo`, `Artista`, `Remixer`, `BPM`, `Camelot`, `Key`, `Genere`, `Anno`, `Album`, `Etichetta`, `Durata`, `Bitrate`, `Energia`, `LUFS`, `True Peak`, `Qualità Audio`, `Percorso`).
- **Persistenza Configurazione Colonne:** Le colonne selezionate vengono memorizzate in `config.json` (`ui.visible_columns` e `ui.custom_columns_active`), preservando la scelta dell'utente a ogni riavvio con pulsanti rapidi "Mostra Tutte" e "Ripristina Predefinite".
- **Monitoraggio RAM Hardware di Sistema:** Eliminato il divisore fittizio di 2 GB (relativo alla sola cache SQLite); implementata la lettura nativa della RAM complessiva del computer (`GlobalMemoryStatusEx` su Windows, `sysctl` su macOS) che mostra la memoria reale (es. `RAM: 283 MB / 24 GB`) e tooltip esplicativo sull'assenza di limiti nel processo 64-bit.
- **Fix Tema Chiaro BreadcrumbBar & MiniPlayer:** Risolta l'anomalia della striscia scura sotto al player: la barra del percorso file si adatta istantaneamente al tema attivo (`#f8f9fa` in Light Theme).
- **Icona Nativa macOS & Taskbar Windows:** Generato `assets/icon.icns` a 10 livelli di risoluzione per PyInstaller su macOS e configurato `AppUserModelID` (`ilred89.musicat.djcataloger.1.0`) per la corretta visualizzazione nella barra delle applicazioni di Windows.

#### 🧪 Suite di Test
- Suite di test espansa e consolidata a **132 test unitari** eseguiti con successo al 100% (`Ran 132 tests in 9.5s OK`).

---

## [1.0.0] - 2026-10-01

### 🚀 Primo Rilascio Ufficiale

Benvenuti al primo rilascio ufficiale di **Musicat**, il catalogatore musicale per DJ, editor di metadati in stile Mp3tag e smart organizer acustico progettato per librerie di grandi dimensioni (oltre 50.000 tracce).

### ✨ Caratteristiche Principali

#### 🎛️ Installer Dual-Mode & Portabilità Senza Installazione
- **Script Inno Setup (`installer/setup.iss`):** Installer unico `Musicat-Setup-Windows-x64.exe` con selezione guidata della modalità:
  - **Modalità Standard:** Installazione in `Program Files`, collegamenti Desktop/Start Menu e isolamento dati in `%APPDATA%\Musicat`.
  - **Modalità Portabile:** Estrazione pulita su qualsiasi pendrive o SSD esterno con creazione automatica del file `portable.lock` e salvataggio di impostazioni, database e log esclusivamente nella cartella locale `./musicat_data/`.
- **Risolutore Volume Serial Number (VSN):** Mappatura dei percorsi indipendente dalle lettere di unità Windows (`[VOL:XXXXXXXX]`) che impedisce la rottura dei collegamenti del database quando si cambia porta USB o computer.

#### ⚡ Ricerca Ultra-Rapida Voidtools Everything SDK & Fallback SQLite FTS5
- Query IPC dirette tramite `Everything64.dll` sulla Master File Table (MFT) di volumi NTFS per ricerche in meno di 1 millisecondo su collezioni da oltre 100.000 brani.
- Fallback automatico trasparente su tabella virtuale **SQLite FTS5** (Full-Text Search) con trigger sincronizzati su inserimento, modifica ed eliminazione.

#### 🎵 Player Audio Universale libVLC & Pitch Control per DJ
- Motore audio nativo basato su `libvlc` con supporto di riproduzione per tutti i formati senza codec esterni: **MP3, WAV (fino a 32-bit float), FLAC, AIFF, M4A, OGG, ALAC, OPUS**.
- **Cursore Pitch / Tempo DJ:** Variazione del tempo e pitch in tempo reale ($\pm 8.0\%$) con detent di ripristino istantaneo a zero.
- Forma d'onda interattiva con scrubbing dei picchi, seek con click diretto e looping continuo.

#### 🏷️ Editor Metadati Professionale in Stile Mp3tag & Conversione Pattern
- Tagging unificato su ID3v2.3/2.4, Vorbis Comments e atomi MP4 con campi dedicati ai DJ (`BPM`, `INITIALKEY`/Camelot, `GENRE`, `LABEL`, `REMIXER`, `ENERGYLEVEL`, `COMMENT`).
- Editing batch simultaneo su selezioni multiple con protezione `<mantieni esistente>`.
- Convertitore bidirezionale di pattern:
  - *Nome file ➔ Tag:* `%artist% - %title% (%bpm% BPM)`
  - *Tag ➔ Nome file:* Ridenominazione fisica di massa basata sui metadati.
  - *Tag ➔ Tag:* Copia, inversione o fusione tra campi.

#### 🌐 Scraping Multi-Fonte & Riconciliazione Conflitti
- Scraper dedicati per la musica elettronica e da club: **Beatport**, **Traxsource**, **Discogs**, **MusicBrainz**.
- Discovery su piattaforme social e remix: **SoundCloud**, **YouTube Music**, **Hypeddit**, **Remix.audio**.
- **Motore di Riconciliazione:** Matrice visiva "Prima / Dopo" per confrontare i risultati da tutte le fonti, individuare i campi discordanti e selezionare con precisione chirurgica quali metadati applicare al file.

#### 🖼️ Download Copertine Studio HD (Fino a 3000x3000px)
- Estrazione di copertine lossless ad altissima risoluzione tramite Apple Music / iTunes CDN (con upscaling da `1400x1400` a `3000x3000px`), Beatport GeoMedia e Traxsource.
- Iniezione diretta nei metadati del file (`APIC` per ID3, blocco Picture per FLAC, atomo `covr` per MP4/M4A) e salvataggio opzionale di `cover.jpg` nella cartella.

#### 📊 Motore Acustico Parallelo Multiprocesso & Cache L1 in RAM
- **Pool di Processi Saturante la CPU (`src/audio/parallel_analyzer.py`):** Assegnazione dinamica dei processi worker su tutti i core logici disponibili (`os.cpu_count() - 1`) con elaborazione a batch per ridurre l'overhead IPC.
- **Streaming Audio Worker ad Alta Efficienza (`src/audio/worker.py`):**
  - Lettura rapida solo della finestra centrale a 22.050 Hz mono (drop di 60 secondi), riducendo l'uso della CPU dell'80%.
  - Estrazione dei segmenti ad alta energia per il rilevamento di BPM e Camelot Key.
  - Generazione di forme d'onda con picchi sottocampionati per visualizzazione istantanea.
- **Cache L1 in RAM (`src/core/memory_cache.py`):**
  - **`AnalysisMemoryCache`:** Buffer SQLite in memoria RAM (`:memory:`) per evitare scritture premature su disco e preservare la vita utile degli SSD.
  - **`WaveformMemoryCache`:** Cache LRU thread-safe in memoria con dimensione configurabile (es. 512MB / 1GB / 2GB) per il caricamento istantaneo (<0.1ms) delle forme d'onda.

#### 📁 Smart Organizer & Smistamento Fisico su Disco
- Generazione dinamica della struttura di cartelle in base a maschere personalizzabili: `{Genre}/BPM {bpm_range}/{Camelot} - {Artist} - {Title}.ext`.
- Modalità obbligatoria **Dry Run (Simulazione)** con anteprima dei percorsi, collision detection (`Auto-Rinomina (1)`, `Sovrascrivi`, `Salta`) e verifica integrità prima di qualsiasi spostamento fisico.

#### 🎛️ Live DJ Crates & Barra Filtri Rapidi (<15ms di Latenza)
- Barra filtri reattiva con autocomplete multi-genere (OR), selezione Target BPM con preset percentuali (`±2%`, `±4%`, `±6%`, `±8%`), filtro per decennio e livello di energia.
- Assistente Armonico Ruota Camelot (`1A`–`12B`) con evidenziazione dei percorsi di mixaggio compatibili (`±1`, scala relativa, boost `+2`, salto `+7`).
- Esportazione istantanea in playlist estese `.m3u8` compatibili con Rekordbox, Traktor, Serato ed Engine DJ.

#### 🍏 Supporto Cross-Platform macOS & Pipeline Multi-OS
- Ricerca nativa su macOS tramite Spotlight Metadata (`mdfind`) e volumi APFS.
- Scoperta dinamica di `libvlc.dylib` tra Homebrew, `/Applications/VLC.app` e bundle di sistema sia su Apple Silicon (M1/M2/M3/M4) che Intel x64.
- Risolutore cross-platform per i punti di montaggio macOS (`/Volumes/...`).
- Pipeline GitHub Actions con compilazione automatica di `Musicat-Setup-Windows-x64.exe`, `Musicat-Windows-Portable.zip`, `Musicat-macOS.dmg` e `Musicat-macOS-Portable.zip`.

#### 🌐 Localizzazione Bilingue (Italiano Lingua Predefinita)
- Motore di traduzione nativo (`src/core/i18n.py`) con dizionari JSON in `locales/it.json` e `locales/en.json`.
- **Italiano come lingua primaria predefinita** all'avvio.
- Cambio lingua istantaneo "a caldo" dalle Impostazioni senza necessità di riavviare l'applicazione.
- Documentazione completa bilingue.
