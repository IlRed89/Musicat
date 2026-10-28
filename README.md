<div align="center">
  <img src="assets/icon.png" width="128" height="128" alt="Musicat Icon" />
  <h1>Musicat</h1>
  <p>
    <strong>Il Catalogatore Universale per DJ, Metadata Engine Stile Mp3tag &amp; Smart Organizer Acustico.</strong><br>
    <em>Sviluppato specificamente per DJ professionisti, collezionisti musicali e archivisti con librerie di grandi dimensioni (50.000+ tracce su dischi esterni).</em>
  </p>
</div>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/Lingua-Italiano-green.svg" alt="Lingua: Italiano"></a>
  <a href="README_EN.md"><img src="https://img.shields.io/badge/Language-English-blue.svg" alt="Language: English"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python Version"></a>
  <img src="https://img.shields.io/badge/piattaforma-Windows%2010%2F11%20x64%20%7C%20macOS%20Universal-brightgreen.svg" alt="Piattaforma">
  <img src="https://img.shields.io/badge/versione-v1.3.0%20(Latest)-blue.svg" alt="Versione Ufficiale">
  <a href="https://github.com/IlRed89/Musicat"><img src="https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg" alt="Repository Ufficiale"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licenza-MIT-purple.svg" alt="Licenza"></a>
</p>

---

## 🌟 Panoramica & Visione

La gestione di archivi musicali estesi (oltre **50.000 brani**) su SSD o dischi esterni comporta sfide operative critiche per qualsiasi DJ o archivista:
- Le lettere di unità di Windows (`D:`, `E:`, `F:`) o i punti di mount APFS/HFS+ di macOS mutano continuamente al cambio di porta USB o tra computer diversi, corrompendo i riferimenti dei database musicali ordinari.
- I software per console (Rekordbox, Traktor, Serato, Engine DJ) mancano di strumenti integrati per l'editing massivo dei tag a maschera, il recupero automatico di metadati da fonti esterne e la diagnostica acustica avanzata.
- I comuni editor di tag (come Mp3tag) non integrano player con pitch bending, analisi DSP in tempo reale (BPM, Camelot Key, Loudness EBU R128), filtri live reattivi né connessione alle classifiche musicali.

**Musicat** colma questo divario unendo in un'interfaccia desktop reattiva, moderna e ad alto contrasto (tema chiaro predefinito, Dark Mode commutabile a caldo senza riavvio) 10 macro-moduli avanzati, compatibili nativamente con **Windows (10/11 x64)** e **macOS (Apple Silicon M-Series + Intel x64)**.

---

## 🚀 Architettura dei Moduli Chiave

```
+----------------------------------------------------------------------------------------------------+
|                                              MUSICAT v1.3.0                                        |
+----------------------------------------------------------------------------------------------------+
| [📁 Libreria] | [🔥 Charts]   | [🏷️ Mp3tag]   | [🔍 Simili]   | [📂 Organizza] | [📦 Crates]  [⚙️] |
| - Drag & Drop | - Streaming   | - Disaccoppiato| - Cosine.club | - In-App Stack | - Regole M3U8|      |
| - Svuota Vista| - 3 Piattaform| - $num() Live | - Web Vectors | - Collision    | - Dock Destra|      |
| - Accesso Rap.| - Riconcilia  | - Wizard Track| - Key & BPM   | - Dry Run      | - Drag/Drop  |      |
+----------------------------------------------------------------------------------------------------+
|         Motore Ricerca Rapida (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)           |
+----------------------------------------------------------------------------------------------------+
|       Fast-Pass Acoustic DSP Multi-Core (ThreadPoolExecutor, BPM & Camelot Key Sub-Sample)         |
+----------------------------------------------------------------------------------------------------+
|                 Engine libVLC con Pitch Bend +/-8% e Waveform Scrubbing Interattivo                |
+----------------------------------------------------------------------------------------------------+
|     DSP Audio Engine (Spotify Pedalboard, FFmpeg libavfilter & JUCE VST3 Plugin Bridge)           |
+----------------------------------------------------------------------------------------------------+
|          Risolutore Path Multi-Piattaforma ([VOL:XXXXXXXX] & portable.lock Drive Migration)        |
+----------------------------------------------------------------------------------------------------+
```

### 1. 📁 Libreria DJ ad Alte Prestazioni, Drag & Drop e Accesso Rapido
- **Drag & Drop Diretto sulla Tabella:** Trascina file o intere cartelle audio da Esplora File/Finder direttamente sulla tabella della Libreria: Musicat rileva i brani ricorsivamente (`.mp3`, `.flac`, `.wav`, `.aiff`, `.m4a`, `.ogg`), li indicizza in SQLite e li visualizza all'istante.
- **Pulsante `[🧹 Svuota Vista]`:** Azzera all'istante la schermata della tabella attiva senza toccare i file fisici su disco né cancellare il database, permettendo di ripartire con una vista pulita.
- **Sezione Accesso Rapido nell'Esplora File:** Barra laterale sinistra rinnovata con scorciatoie immediate alle cartelle di sistema:
  - 🖥️ **Desktop**
  - 📁 **Documenti**
  - 📥 **Download**
  - 🎵 **Musica**
  - Subito sotto, la sezione **"Questo PC / Dischi"** elenca le sole unità disco logiche collegate.
- **Layout Flessibile & Responsive Overflow:** Barra dei filtri racchiusa in un contenitore a scorrimento fluido (`QScrollArea`), evitando sovrapposizioni o tagli di testo su schermi a risoluzione ridotta o finestre ridimensionate.
- **Menu Contestuale Arricchito:** Cliccando con il tasto destro su una o più tracce selezionate:
  - **`[⚡ Analizza Tracce Selezionate]`** (in grassetto, primo elemento): avvia l'analisi acustica e metadati mirata esclusivamente sui brani evidenziati.
  - **`[🏷️ Invia a Tag Editor (Mp3tag)...]`**: trasferisce le tracce selezionate nel workbench di tagging senza interferire con la libreria.

### 2. ⚡ Analisi Acustica Accelerata (Fast-Pass & Multi-Core)
- **Parallelizzazione Dinamica Multi-Thread (`ThreadPoolExecutor`):** Analisi audio multi-traccia concorrente dimensionata sul numero effettivo di core CPU fisici (`os.cpu_count()`), preservando la totale reattività della UI con salvataggi serializzati e thread-safe su SQLite.
- **Fast-Pass Acoustic Sampling:** Calcolo istantaneo di BPM e Camelot Key analizzando una finestra centrale rappresentativa (60–90 secondi a partire dal 25% della durata della traccia), abbattendo dell'80% i tempi di I/O e decodifica.
- **Scraping Asincrono con Timeout Rigidi:** Timeout massimi a 2.5 – 3.0 secondi per provider (Discogs, MusicBrainz, WebEnricher/Wikipedia/YouTube), evitando blocchi o code pendenti in caso di rete lenta.

### 3. 🏷️ Workspace Mp3tag Indipendente & Bulk Pattern Tagging
- **Disaccoppiamento Completo dalla Libreria:** Nessuna sincronizzazione o azzeramento automatico della vista navigando tra i tab. Mp3tag riceve tracce solo su esplicita richiesta.
- **Comandi Interni Dedicati:**
  - Pulsanti in toolbar e menu: **`[➕ Aggiungi File...]`**, **`[📁 Aggiungi Cartella...]`**, **`[🧹 Svuota Elenco]`**, **`[💾 Salva Modifiche]`**.
  - **Drag & Drop autonomo:** Rilascia file e cartelle direttamente sulla griglia di Mp3tag per lavorare su una selezione isolata.
- **Procedura Guidata Numerazione Tracce (`TrackNumberingWizardDialog`):** Numerazione sequenziale automatica con padding a 2 cifre (`01, 02...`), formato frazionario (`01/12`), offset iniziale e azzeramento contatore a ogni cambio cartella/album.
- **Convertitori Pattern Bidirezionali Live:**
  - *Nome File ➔ Tag (`FilenameToTagDialog`):* Estrazione automatica dei metadati con token flessibili (`%artist%`, `%title%`, `%album%`, `%bpm%`, `%key%`, `%year%`, `%genre%`) e supporto al token `$num(%track%,2)`.
  - *Tag ➔ Nome File (`TagToFilenameDialog`):* Ridenominazione fisica su disco con anteprima a colori in tempo reale.
- **Macro Veloci:** Normalizzazione maiuscole/minuscole (*Title Case*, *MAIUSCOLO*, *minuscolo*), rimozione suffissi promozionali (`[FREE DOWNLOAD]`, `[Extended Mix]`) e padding numeri traccia.

### 4. 🔊 Motore Audio DSP, Diagnostica Volume & Mastering
- **Profili 1-Click & Modalità Chiare:**
  - *ReplayGain (solo metadati)*, *Normalizzazione fisica (nuovo file MP3 _normalized.mp3)* e *Sovrascrittura sicura (con backup in _original/)*.
  - Preset pronti all'uso: *DJ Club (-10 LUFS)*, *Streaming (-14 LUFS)*, *Anti-Clipping & Clean*, *Warm Analog*, *DJ Punch*, *Vocal Clarity*.
- **Standard EBU R128 & ITU-R BS.1770-4:** Misurazione Integrated Loudness (LUFS), True Peak con oversampling 4x sinc e Loudness Range (LRA).
- **Glossario Interattivo `[ℹ️ Spiegazione Termini]`:** Spiegazioni chiare e contestuali su LUFS, True Peak dBTP e dinamica per DJ e producer.
- **FFmpeg Integrato (Bundled di Default):** Ricerca automatica dell'eseguibile `bin/ffmpeg.exe` pre-incluso nella cartella dell'applicazione, con pulsante "Sfoglia..." opzionale per puntare a binari di sistema.

### 5. 🔑 Autenticazione Semplificata Servizi Online (OAuth2 & API Key)
- **Spotify:** Flusso OAuth2 conforme alle policy più recenti con `response_type=code`, gestione loopback `http://localhost:8888/callback` e scope per la lettura e sincronizzazione delle playlist.
- **SoundCloud:** Supporto diretto con token di sessione per aggirare le restrizioni sulle registrazioni di nuove app pubbliche di SoundCloud.
- **YouTube Data API v3:** Autenticazione tramite Google Cloud API Key con test di validazione in tempo reale, eliminando gli errori `401: invalid_client`.

### 6. 🎨 Cambio Tema a Caldo & Interfaccia Ergonomica
- **Cambio Tema Dinamico Istantaneo:** Passaggio tra tema chiaro e tema scuro applicato a caldo tramite stylesheet `QApplication` e polish dei widget senza chiusura né riavvio della finestra Impostazioni.
- **Check-box e Selettori Standardizzati:** Stile coerente e moderno in tutta l'app, inclusa la scheda Account e Servizi.

---

## ⌨️ Scorciatoie da Tastiera DJ Console

| Tasto Rapido | Azione | Descrizione |
|---|---|---|
| `Ctrl + F` | Ricerca Rapida | Attiva la barra di ricerca rapida (Everything MFT / Spotlight / FTS) |
| `Ctrl + G` | Filtro Generi | Attiva la casella generi con completamento automatico |
| `Ctrl + B` | Filtro BPM | Seleziona il filtro target BPM |
| `Ctrl + K` | Ruota Camelot | Apre l'assistente visivo Ruota Camelot per il mix armonico |
| `Esc` | Ripristina Filtri | Cancella i filtri attivi e mostra la libreria completa |
| `Spazio` | Play / Pausa | Avvia o ferma la riproduzione del brano corrente |
| `Invio` | Carica nel Deck | Carica la traccia selezionata nel mini-player |
| `Ctrl + O` | Aggiungi File (Mp3tag) | Seleziona e importa file audio nel Tag Editor |
| `Ctrl + D` | Aggiungi Cartella (Mp3tag) | Importa ricorsivamente una cartella nel Tag Editor |
| `Ctrl + S` | Salva Modifiche | Scrive i tag fisici e aggiorna il database in Mp3tag |
| `Ctrl + Shift + P` / `Alt + F` | Tag da Pattern | Apre l'editor massivo per estrazione da maschera con anteprima live |
| `Ctrl + Q` | Qualità & Volume | Apre il modulo di diagnosi del volume e clipping EBU R128 |
| `Ctrl + Shift + S` | Trova Simili | Trova tracce compatibili nella collezione locale e online |
| `Ctrl + L` | Log Console | Mostra o nasconde la console dei log di sistema in tempo reale |
| `Ctrl + ,` | Impostazioni | Apre il pannello delle preferenze e configurazione account |

---

## 📦 Download & Release Ufficiali

| Piattaforma | File di Rilascio | Descrizione |
|---|---|---|
| **Windows 10/11 x64** | `Musicat-Windows-Portable.zip` | Versione portabile completa (FFmpeg, Qt6, libVLC, zero installazione) |
| **Windows 10/11 x64** | `Musicat.exe` | Eseguibile standalone 64-bit per Windows |
| **macOS Universal** | `Musicat-macOS.dmg` | Immagine disco DMG con installazione drag & drop in Applicazioni |
| **macOS Universal** | `Musicat-macOS-Portable.zip` | Pacchetto portatile per volumi APFS/HFS+ esterni |
| **Tutte le piattaforme** | `SHA256SUMS.txt` | Checksum crittografici SHA-256 per la verifica dell'integrità |

👉 **[Scarica l'Ultima Release Ufficiale (v1.3.0)](https://github.com/IlRed89/Musicat/releases/latest)**

---

## 🛠️ Installazione e Avvio dai Sorgenti

### Prerequisiti
- Python 3.11, 3.12 o 3.13 a 64-bit
- `git`
- libVLC (o VLC Media Player installato a 64-bit)

### Esecuzione

```bash
# 1. Clona il repository
git clone https://github.com/IlRed89/Musicat.git
cd Musicat

# 2. Crea ed attiva un ambiente virtuale
python -m venv venv
# Su Windows:
.\venv\Scripts\activate
# Su macOS:
source venv/bin/activate

# 3. Installa le dipendenze
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Esegui i test unitari mirati
python -m unittest tests/test_performance_and_features.py tests/test_updater.py

# 5. Avvia Musicat
python main.py
```

### Compilazione Standalone Locale

```bash
# Compilazione standalone per Windows (PyInstaller)
pyinstaller build_windows.spec --clean -y
```

---

## 📄 Licenza

Musicat è distribuito sotto licenza open-source **MIT**.  
Consulta il file [LICENSE](LICENSE) per i termini completi.
