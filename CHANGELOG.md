# 📋 Registro Modifiche (Changelog)

Tutte le modifiche e le novità di **Musicat** sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto aderisce al [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)
[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)

---

## [1.8.0] - 2026-10-05

### 🎛️ Scraping Multi-Source (Genere & Anno), Riordino Colonne Drag & Drop, Fix Freccia ComboBox & Restyle Loudnorm

#### 🌐 Motore di Arricchimento Metadati Cascata Multi-Source (Genere & Anno)
- **Cascata Multi-Provider Intelligente:** Integrazione Discogs (priorità a `styles` e Master Release per identificare sottogeneri DJ precisi quali Tech House, Melodic Techno, Afro House al posto del generico "Electronic") $\rightarrow$ MusicBrainz / AcousticBrainz (community tags e data di prima uscita) $\rightarrow$ Beatport / Traxsource $\rightarrow$ `WebEnricher` (fallback web scraping su Wikipedia Knowledge Graph e YouTube con query mirata `"[Artista] - [Titolo] genre year"`).
- **Normalizzazione Rigorosa dei Generi:** Rifiuto preventivo di etichette vaghe o inutili ("Other", "Unknown", "Soundtrack", "Music", "Various", "General"), preferenza per i sottogeneri musicali e assegnazione di `"Vario"` rigorosamente come ultima risorsa se nessun provider restituisce dati.

#### 🔀 Riordino Interattivo Colonne Drag & Drop & Persistenza Layout
- **Trascinamento Intestazioni Tabella:** Abilitato `setSectionsMovable(True)` e `setDragEnabled(True)` sull'header della tabella libreria per consentire la riorganizzazione libera delle colonne.
- **Persistenza Stato Header:** Salvataggio serializzato dello stato dell'header (`saveState()` in formato esadecimale) in `config.json` (`ui.header_state`) e ripristino istantaneo all'avvio con `restoreState()`.

#### 🔽 Fix ComboBox Generi: Freccia Visibile & Popolamento Esclusivamente Dinamico
- **Rimozione Generi Hardcoded:** Eliminato il dizionario statico `COMMON_DJ_GENRES`. Il selettore viene ora popolato esclusivamente dai generi effettivamente presenti nel database SQLite (`SELECT DISTINCT genre FROM tracks`).
- **Ordinamento Intuitivo:** Voce iniziale `"🏷️ Tutti i Generi"` in testa, generi del database in ordine alfabetico e voce `"Vario"` posizionata in fondo.
- **Sottocontrolli CSS per la Freccia Dropdown:** Aggiunti stili espliciti `QComboBox::drop-down` e `QComboBox::down-arrow` con freccia vettoriale pura CSS sia nel tema scuro che nel tema chiaro, eliminando il bug visivo della scomparsa della freccia su PySide6/Windows.

#### 🧹 Sfoltimento Colonne Predefinite della Tabella Principale
- **Rimozione Colonne Superflue dalla Vista Standard:** Nascoste di default le colonne `energy_level`, `lufs`, `true_peak` e `audio_status` per evitare affollamento orizzontale.
- **Proporzioni Ottimizzate per DJ:** Spazio redistribuito uniformemente tra le colonne cardine: `#`, `Cover`, `Titolo`, `Artista`, `Remixer`, `BPM`, `Camelot`, `Key`, `Genere`, `Anno`, `Durata`, `Bitrate`.

#### 🔊 Loudness Meter Pulito & Restyle Nativo Light del Dialog "Correggi Audio"
- **Disattivazione Meter per Brani Non Analizzati:** Eliminata l'indicazione fittizia `-70 LUFS / -100 dBTP`. I brani privi di scansione mostrano ora il placeholder neutro disattivato `"— LUFS | TP: — dBTP (Non analizzato)"`.
- **Restyle Completo Light Theme:** Riprogettata l'interfaccia di `QualityDiagnosisDialog` con sfondo nativo `#ffffff`, testi a contrasto elevato `#212529` e groupbox puliti.
- **Box "Tips & Spiegazioni Operative":** Scheda didattica dettagliata sulle differenze tra normalizzazione non distruttiva dei metadati (ReplayGain) e normalizzazione fisica con ricodifica audio FFmpeg (-1.0 dBTP headroom).
- **Cursori Target Interattivi:** Slider per Loudness Target (-9/-10 LUFS club/DJ, -14 LUFS streaming) e True Peak Target (-1.0 dBTP) con tooltip operativi contestuali.

---

## [1.7.0] - 2026-10-05

### ⚡ Pulsante Esplicito di Analisi Toolbar, Worker Asincrono Non Bloccante, Revisione Metadati & Scrittura Fisica con Mutagen

#### ⚡ Tasto Dedicato "Analizza Tracce" nella Toolbar
- **Pulsante Principale `[⚡ Analizza Selezionate]`:** Aggiunto direttamente nella riga comandi superiore della Libreria DJ con styling accent visibile.
- **Logica di Analisi Flessibile:** Se l'utente seleziona una o più tracce nella tabella, analizza solo quelle; se nessuna traccia è selezionata ma è aperta una cartella nell'esplora risorse, analizza tutte le tracce caricate; se non c'è nulla, mostra notifica discreta nella barra di stato (`⚠️ Seleziona almeno una traccia o una cartella da analizzare.`).
- **Eliminazione Obbligo Menu Contestuale:** L'analisi e la riconciliazione non richiedono più l'accesso al tasto destro del mouse.

#### 🔄 Elaborazione Asincrona in Background (`AsyncAnalysisWorker`)
- **Zero Freeze dell'Interfaccia Grafica:** L'intero processo di calcolo acustico (BPM, Chiave Camelot/Musicale), separazione dei metadati e scrittura dei tag è delegato a un worker `QThread` dedicato. La finestra principale rimane reattiva durante l'elaborazione (riproduzione VLC, scorrimento tabella, navigazione viste).
- **Feedback Discreto con Annullamento Immediato:** Barra di avanzamento discreta e messaggio traccia per traccia nella barra di stato in basso con pulsante rosso `[✕ Annulla]` per interrompere l'elaborazione in qualsiasi momento.
- **Aggiornamento Fluido della Tabella:** Emette segnali Qt per aggiornare istantaneamente la riga senza ricaricamenti a scatti o riavvii del modello.

#### 📐 Fix Layout & Responsive del Dialog Metadati (`ReconcilerDialog` & `ScraperDialog`)
- **Quattro Colonne Chiare ed Elastiche:** `Campo`, `Valore Attuale`, `Valore Rilevato (Online)`, `Valore da Applicare`. Le colonne informative usano `ResizeToContents` mentre il valore da applicare e il riepilogo fonti usano `Stretch`.
- **Altezza Righe & Padding Generoso:** Aumentata l'altezza riga predefinita a 36px con padding per evitare testi tagliati, etichette sovrapposte o menu a tendina compressi.
- **Finestra Ridimensionabile con Size Grip:** Dimensione minima impostata a 920x620 px con grip di ridimensionamento libero attivo.
- **Ricerca Online Asincrona (`ReconcilerSearchWorker`):** Lo scraping simultaneo su Beatport, Discogs, Traxsource, MusicBrainz e Apple Music HD viene eseguito in background, aprendo istantaneamente il dialog senza bloccare il thread principale.

#### 🇮🇹 Localizzazione Completa in Italiano del Dialog Metadati
- Tutte le etichette, intestazioni e pulsanti sono tradotti in lingua italiana: *"Revisione e Conferma Metadati"*, *"Campo"*, *"Valore Attuale"*, *"Valore Rilevato (Online)"*, *"Valore da Applicare"*, *"Salva Modifiche nei File"*, *"Annulla"*, *"Query di Ricerca"*, *"Avvia Ricerca Online"*.

#### 💾 Persistenza Fisica dei Tag con Mutagen & SQLite
- **Separazione Netta Artista / Titolo:** Se il titolo o il nome file contiene il pattern `"Artista - Titolo"` e l'artista è vuoto, separa automaticamente i valori assegnando `artist = clean_artist` e `title = clean_title`.
- **Prevenzione Conflitti File Lock su Windows:** Scrittura dei tag gestita con rilasci espliciti degli handle Mutagen (`del tags/audio`, `gc.collect()`) e gestione automatica con retry su `PermissionError`.
- **Sincronizzazione Istantanea SQLite:** Scrittura atomica sia nei tag fisici del file che nel database SQLite con aggiornamento immediato della vista.

---

## [1.6.0] - 2026-10-05

### 🚀 Riproduzione Streaming Top Charts, Login OAuth nel Browser, Avvio su Libreria & Sincronizzazione Cartelle Filesystem

#### 🎧 Riproduzione Audio su Top Charts (Streaming Preview & Prompt di Accesso)
- **Ascolto Immediato su Click:** Cliccando sulle card dei brani o sul pulsante play nella schermata Top Charts, viene avviata la riproduzione dell'anteprima audio HD (stream a 30s) direttamente nel mini-player interno libVLC (`media_new_location` via rete).
- **Gestione Tracce Protette & Redirect Login:** Se la traccia richiede un account connesso o il catalogo non fornisce un'anteprima pubblica, viene mostrato un dialog intuitivo che invita ad accedere e reindirizza direttamente su **Impostazioni > Account & Servizi**.
- **Visualizzazione Mini-Player Dedicata:** Breadcrumb e indicatore di stato mostrano chiaramente l'etichetta `🌐 Streaming Online (Anteprima 30s)` senza tentare calcoli locali del waveform non necessari.

#### 📁 Schermata Predefinita all'Avvio: Libreria DJ (No Top Charts)
- **Apertura Istantanea su Libreria (Index 0):** All'avvio dell'applicazione la vista principale attiva è la Libreria DJ con tabella virtuale e albero delle cartelle.
- **Riorganizzazione Macro-Navigazione:** La barra superiore posiziona `📁 Libreria` come primo pulsante a sinistra e `🔥 Top Charts` (precedentemente Analisi) come seconda tab secondaria.
- **Scorciatoie Tastiera DJ Riorganizzate:** `Alt+1` attiva la Libreria, `Alt+2` attiva Top Charts, mantenendo continuità operativa.

#### 🌐 Gestione Account OAuth con Login Diretto nel Browser
- **Autenticazione Rapida a Singolo Click:** Ridisegnata la sezione **Impostazioni > Account & Servizi** con schede per Spotify, SoundCloud, YouTube e Discogs dotate di pulsante `[Connetti Account]`.
- **Server Loopback Locale per Intercettazione Token:** Implementato `OAuthManager` con server HTTP effimero locale (`http://localhost:8888/callback`) che gestisce in background l'autorizzazione nel browser predefinito di sistema.
- **Stato Account in Tempo Reale & Disconnessione:** Le schede mostrano lo stato `✓ Connesso come: [Nome Utente]` con pulsante `[Disconnetti]`.
- **Sezione Sviluppatore Comprimibile:** Posizionata in calce alla pagina una sezione richiudibile per l'inserimento facoltativo di credenziali manuali o token API custom.

#### 📂 Navigazione Filesystem & Auto-Scansione Cartelle dall'Albero
- **Normalizzazione Percorsi Multi-Piattaforma:** Corretto il disallineamento tra barre Windows (`\`) e Unix (`/`) sia nelle query SQL SQLite che nella cache in memoria a 64-bit di `LiveFilterEngine`, eliminando le tabelle vuote su clic di cartelle già indicizzate.
- **Scansione Automatica Cartelle Non Indicizzate:** Selezionando una cartella fisica non ancora presente nel database (es. `E:\Nuova cartella\Commerciale`), l'albero avvia istantaneamente una scansione asincrona in background dei soli file audio presenti con barra di avanzamento discreta nella status bar, popolando la tabella in tempo reale.
- **Snellimento Header Libreria:** Rimosso definitivamente dall'header il badge `"Live RAM Index (<15ms)"` (ora monitorato esclusivamente nella barra di stato con barre graduate dinamiche) e rimosso il campo ridondante *"Cartella"*, demandando l'esplorazione gerarchica all'albero laterale dedicato.

---

## [1.5.1] - 2026-10-05

### 🛡️ Risoluzione Completa Crash Thread-Safety Home Trends & Nuova Build Eseguibile

#### ⚡ Thread-Safety Totale & Eliminazione Crash Nativi in Home Trends
- **Eliminazione Chiamate Distruttive a `QThread.terminate()`:** Sostituito l'uso di thread Qt forzati con `TrendsLoader` basato su `concurrent.futures.ThreadPoolExecutor`. Zero rischio di terminazione anomala nativa C++ (`0xC0000005`) durante i click veloci tra generi e piattaforme.
- **Isolamento Thread Grafico per le Miniature (`TrendingCoverLoader`):** Decodifica in background delle immagini condotta rigorosamente tramite la classe thread-safe `QImage`. Conversione finale a `QPixmap` circoscritta al solo GUI Thread al segnale `cover_ready`, con cache in memoria scalata.
- **Annullamento Richieste Obsolete via Request ID (`req_id`):** Introdotto contatore progressivo di richieste che scarta istantaneamente risposte lente o asincrone di categorie precedentemente selezionate.
- **Ottimizzazione Query Incrociata Libreria Locale (`cross_check_library`):** Controllo fulmineo della presenza di tracce (`COUNT(*)`) in 0.1ms prima di interrogare il database, eliminando decine di connessioni concorrenti ridondanti a SQLite.

---

## [1.5.0] - 2026-10-05

### 🚀 Home Trends Estesi a Scorrimento Fluido, Pulizia Header Libreria, Esplora Risorse Drive Pulito & Tagging Massivo da Pattern (Mp3tag)

#### 📈 Home Trends: Elenco Completo a Scorrimento Illimitato (Nessun Blocco a 4/5 Tracce)
- **Rimozione Vincoli e Troncamenti Hardcoded:** Eliminati i limiti `[:5]` e parametri restrittivi `limit=5` in tutto il motore trends (`spotify_trends.py` e `home_view.py`).
- **Espansione Catalogo Curato su Tutte le 18 Categorie:** Arricchite tutte le categorie di Spotify, SoundCloud e Beatport con feed da 20+ tracce autentiche complete di metadati, BPM, chiavi Camelot e link alle copertine ad alta risoluzione.
- **Caricamento Copertine Asincrono con Concorrenza Controllata (`QSemaphore`):** Implementata gestione concorrenza a 6 worker contemporanei in `AsyncThumbnailLoader` con cache in memoria `_cache`, garantendo scorrimento a 60 FPS fluido e zero micro-scatti durante lo scroll prolungato della griglia.

#### 🎛️ Pulizia Header Libreria & Allargamento Elastico dei Controlli
- **Rimozione Controlli Smart Crates dalla Barra Filtri:** Rimossa la combobox dei crates e i pulsanti *"Salva Crate"* / *"Esporta M3U8"* dall'angolo in alto a destra della Libreria (`live_filters.py`). La consultazione e gestione dei crates è centralizzata esclusivamente nel workspace dedicato incorporato.
- **Riorganizzazione Elastica dello Spazio Orizzontale:** Allargati i controlli di ricerca, BPM target (`85px`), tolleranza (`72px`), BPM Min/Max (`75px`), chiave Camelot (`140px`), pulsante ruota armonica (`70px`), decadi/anni (`160px`), filtri audio (`170px`) e pill tag DJ (`55-95px`), eliminando qualsiasi compressione visiva delle etichette.
- **Routing Diretto dei Crate dalla Sidebar:** Il clic su un elemento crate nell'albero della barra laterale reindirizza istantaneamente al workspace Smart Crates (`select_crate_by_name`).

#### 🗂️ Esplora Risorse Filesystem (Radice Unità Fisiche Pulita)
- **Radice Logica di Sistema:** Impostata la radice di `QFileSystemModel` sulla radice logica di sistema (`""` su Windows, `/Volumes` su macOS) con tutte le unità compresse all'avvio (`collapseAll()`).
- **Visualizzazione Chiara delle Unità:** All'apertura della barra laterale compaiono esclusivamente le lettere delle unità fisiche (`Disco locale (C:)`, `D:`, `E:`) non espanse, senza auto-espansione caotica dei contenuti di `C:\`.

#### 🏷️ Workspace Mp3tag: Tagging Massivo da Pattern (`BulkPatternTagDialog`) & Scorciatoia Rapida
- **Dialog Tagging da Pattern Avanzato:** Implementato `BulkPatternTagDialog` accessibile tramite scorciatoia rapida (`Ctrl + Shift + P` e `Alt + F`) e da pulsante dedicato nel pannello sinistro.
- **Supporto Maschere e Segnaposto Flessibili:** Supporto completo per maschere personalizzabili (es. `[%title%] - [%artist%]`, `[%artist%] - [%title%]`, `[%track%]. [%title%]`) con pulsanti rapidi per l'inserimento dei segnaposto `[%title%]`, `[%artist%]`, `[%album%]`, `[%year%]`, `[%genre%]`, `[%track%]`.
- **Tabella Anteprima Live Prima ➔ Dopo (Preview):** Visualizzazione in tempo reale con evidenziazione colorata delle differenze (valore attuale ➔ nuovo valore in ciano/verde) e conteggio delle modifiche prima dell'applicazione.
- **Scrittura Diretta su Disco via Mutagen & Sincronizzazione DB:** Salvataggio effettivo immediato nei file fisici con Mutagen (`AudioTagEditor.write_metadata`) e sincronizzazione con il database SQLite e la griglia dell'editor.
- **Pulizia Toolbar e Azioni Rapide:** Rimossi i pulsanti ridondanti per conversione maiuscole/minuscole dalla toolbar e dal pannello laterale, snellendo l'area di lavoro.

#### 🍏 Diagnostica di Avvio Precoce & Tracciamento macOS (Pre-Bootstrap Logging Suite)
- **Logging Pre-Bootstrap a Dipendenza Zero:** Riorganizzato `main.py` per inizializzare il logging su file come primissima istruzione assoluta prima di importare PySide6, libVLC o Mutagen, con flush immediato riga per riga (`flush()` e `fsync()`).
- **Scrittura Multipla su macOS:** Salvataggio simultaneo in `~/Library/Application Support/Musicat/logs/musicat_boot.log` e su `~/Desktop/musicat_debug.log` (o nella cartella locale se in modalità portabile).
- **Rilevamento Hardware, OS & Rosetta 2:** Tracciamento dettagliato di versione macOS (`mac_ver()`), architettura CPU e stato di emulazione Rosetta 2 (`sysctl.proc_translated`), eseguibile, PID, argv e variabili d'ambiente critiche (`DYLD_*`, `PATH`, `QT_*`, `VLC_*`).
- **Probe Dinamico libVLC & Intercettazione Errori dlopen:** Test diagnostico automatico di tutti i percorsi candidati (`/Applications/VLC.app`, Homebrew, bundle Frameworks) con cattura esatta di `OSError` e architetture incompatibili senza crash silenziosi.
- **Trap Crash Nativi C/C++ (Segfault):** Integrazione del modulo standard `faulthandler` su tutti i thread (`faulthandler.enable()`) e hook globale `sys.excepthook` per intercettare qualsiasi segmentation fault a livello C++ o eccezione non gestita.
- **Script di Lancio per Debug Rapido (`run_mac_debug.sh`):** Creato script bash eseguibile nella root del repository per lanciare Musicat con cattura live di stdout/stderr su `~/Desktop/musicat_terminal.log` e supporto al flag `--qt-debug`.

---

## [1.4.0] - 2026-10-04

### 🚀 Monitor Hardware Visivo (Progress Bar Dinamiche), Mp3tag Avanzato (Autonumerazione & Pattern Live), ComboBox Generi Unificata & Fallback "Vario"

#### 📊 Monitor Hardware Visivo nella Status Bar
- **Barre di Avanzamento Grafiche Integrate (`HardwareProgressBar`):** Sostituito il semplice testo nella barra di stato inferiore con due barre orizzontali compatte per CPU e RAM.
- **Gradiente Dinamico a 3 Soglie di Carico:**
  - **Verde (`#28A745`):** Carico normale (0% - 60%);
  - **Giallo / Arancione (`#FD7E14`):** Carico medio-alto (61% - 84%);
  - **Rosso (`#DC3545`):** Stress elevato / saturazione (85% - 100%).
- **Formattazione Centrata & Telemetria Asincrona:** Testo centrato e leggibile (`CPU XX%`, `RAM X.X/YY GB`) con aggiornamento asincrono a intervallo di 1.5 secondi (1500 ms) e pieno adattamento al tema chiaro/scuro.

#### 🏷️ Workspace Mp3tag: Strumenti Avanzati di Tagging
- **Procedura Guidata Numerazione Tracce (`TrackNumberingWizardDialog`):**
  - Pulsante dedicato *"🔢 Rinumera Tracce..."*;
  - Numerazione sequenziale configurabile con zero iniziale opzionale (`01, 02...`);
  - Opzione per salvare il denominatore totale tracce (`01/12`);
  - Azzeramento automatico del contatore per cartella o per album;
  - Tabella di anteprima in tempo reale prima dell'applicazione effettiva.
- **Convertitori Pattern con Anteprima Live Tabellare:**
  - **Nome File ➔ Tag (`FilenameToTagDialog`):** Dialog interattivo con selezione preset, pulsanti per inserimento rapido dei token (`%artist%`, `%title%`, `%album%`, `%track%`, `%year%`, `%bpm%`, `%genre%`) e anteprima tabellare dei tag estratti.
  - **Tag ➔ Nome File (`TagToFilenameDialog`):** Ridenominazione fisica dei file audio su disco in base ai metadati ID3 con anteprima in tempo reale dello stato dei file prima dell'operazione.
  - **Supporto Token `$num(%track%,2)`:** Implementato il parsing e la generazione avanzata di padding a cifre personalizzate sia nell'estrazione che nella formattazione in `PatternEngine`.
- **Azioni Rapide per Modifica Case/Maiuscole/Minuscole:**
  - Pulsanti diretti a 1-click nella toolbar e nel pannello sinistro per *Title Case* (Maiuscole Iniziali), *TUTTO MAIUSCOLO* e *tutto minuscolo*.

#### 🎛️ ComboBox Generi Dinamica Unificata & Fallback "Vario"
- **Controllo Unificato Editabile:** Fusione del campo di ricerca testuale e del menu a discesa in una singola `QComboBox` editabile con autocompletamento istantaneo (`setEditable(True)`, `setInsertPolicy(NoInsert)`).
- **Elenco Dinamico Ordinato Alfabeticamente:** Inizializzazione con voce predefinita `🏷️ Tutti i Generi`, seguita dall'elenco completo dei generi presenti nel database SQLite ordinati da A a Z, con aggiornamento automatico al termine di ogni scansione o aggiornamento libreria.
- **Raggruppamento Fallback "Vario":** Le tracce senza metadati di genere (ID3 vuoto o nullo) vengono automaticamente visualizzate come `"Vario"` nella tabella della libreria e filtrate coerentemente dal motore in-memory e SQL.

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
