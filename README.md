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
  <img src="https://img.shields.io/badge/tests-151%20passing-brightgreen.svg" alt="Test Suite">
  <a href="https://github.com/IlRed89/Musicat"><img src="https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg" alt="Repository Ufficiale"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licenza-MIT-purple.svg" alt="Licenza"></a>
</p>

---

## 🌟 Panoramica & Visione

La gestione di oltre **50.000 brani** su SSD esterni comporta criticità note a qualsiasi DJ:
- Le lettere di unità di Windows o i punti di mount APFS/HFS+ di macOS cambiano costantemente quando si collegano dischi a porte diverse o si passa tra computer diversi, corrompendo i database dei player tradizionali.
- I software DJ da console (Rekordbox, Traktor, Serato, Engine DJ) non offrono funzionalità complete di tag editing massivo, scraping da fonti multiple e diagnosi acustica.
- Gli editor di tag generici (come Mp3tag) non dispongono di player audio integrato con pitch bending, analisi DSP (BPM e Camelot Key), filtri live in tempo reale né sincronizzazione con le classifiche online.

**Musicat** integra in un'unica interfaccia desktop moderna a tema chiaro (ad alto contrasto, con Dark Mode opzionale) e ad alte prestazioni 10 macro-moduli compatibili nativamente con **Windows (10/11 x64)** e **macOS (Apple Silicon M-Series + Intel x64)**.

---

## 🚀 Architettura dei Moduli Chiave

```
+----------------------------------------------------------------------------------------------------+
|                                              MUSICAT                                               |
+----------------------------------------------------------------------------------------------------+
| [🏠 Analisi]  | [📁 Libreria] | [🏷️ Mp3tag]   | [📦 Crates]   | [🔍 Simili]   | [📂 Organizza]|
| - Avvio Default  | - Filtri 2-Row| - Rinumeratore  | - Workbench    | - Cosine.club  | - In-App Stack|
| - Trend 3-Piatta | - Albero Drive| - Pattern %tag% | - Guida & M3U8 | - Vettori Web  | - Collision   |
| - Diagnosi EBU   | - Ruota 1A-12B| - $num() Live   | - Dynamic Crate| - Hard Disk    | - Dry Run     |
+----------------------------------------------------------------------------------------------------+
|         Motore Ricerca Rapida (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)           |
+----------------------------------------------------------------------------------------------------+
|                 Engine libVLC con Pitch Bend +/-8% e Waveform Scrubbing Interattivo                |
+----------------------------------------------------------------------------------------------------+
|          Status Bar con Monitor Hardware Dinamico a Barre Grafiche (CPU & RAM con Soglie)          |
+----------------------------------------------------------------------------------------------------+
|       Suite di Logging Strutturato (.zip rotante 20MB, Bundle Diagnostico, Tracciamento Granulare) |
+----------------------------------------------------------------------------------------------------+
|          Risolutore Path Multi-Piattaforma ([VOL:XXXXXXXX] & portable.lock Drive Migration)        |
+----------------------------------------------------------------------------------------------------+
```

### 1. ⚪ Tema Chiaro Predefinito, Workspaces Incorporati & Navbar Modulare
- **Architettura a 6 Workspaces Incorporati (`QStackedWidget`):** I moduli principali non aprono finestre modali esterne ma sono completamente integrati nella finestra principale senza interruzioni di flusso:
  - **Indice 0: [🏠 Analisi / Home]** (Dashboard iniziale con classifiche multi-piattaforma Spotify/SoundCloud/Beatport e card bianche ad alto contrasto)
  - **Indice 1: [📁 Libreria]** (Catalogo DJ ad altissime prestazioni con barra filtri a due righe, menu contestuale colonne e albero cartelle)
  - **Indice 2: [🏷️ Tag Editor (Mp3tag)]** (Workspace tabellare completo con autonumerazione, pattern live e conversione case)
  - **Indice 3: [📦 Smart Crates]** (Workbench con guida interattiva, logiche booleane avanzate ed esportazione M3U8)
  - **Indice 4: [🔍 Trova Simili]** (Ricerca vettoriale locale e web discovery su Cosine.club con affinità armonica DJ)
  - **Indice 5: [📂 Organizza File]** (Smistamento fisico su disco integrato in-app con gestione collisioni e dry run)
- **Stile Visivo Moderno:** Palette chiara predefinita (`#FFFFFF` / `#F8F9FA`, testi `#212529`, accenti `#0D6EFD`) con card bordate e Dark Mode attivabile a caldo nelle Preferenze.
- **Icona Taskbar Nativa:** Configurazione esplicita di `AppUserModelID` su Windows per garantire l'icona Musicat ad alta risoluzione nella barra delle applicazioni anche in versione portabile su qualsiasi PC.

### 2. 📊 Monitor Hardware Visivo nella Status Bar (Progress Bar Dinamiche)
- **Barre Grafiche Integrate CPU & RAM:** Sostituito il vecchio testo monocromatico con due `QProgressBar` orizzontali compatte ed eleganti.
- **Soglie di Carico a Colori Dinamici:**
  - **Verde (`#28A745`):** Carico regolare e fluido (0% – 60%);
  - **Giallo / Arancione (`#FD7E14`):** Carico moderato o intenso (61% – 84%);
  - **Rosso (`#DC3545`):** Stress elevato o saturazione hardware (85% – 100%).
- **Trasparenza RAM a 64-bit:** Nessun limite artificiale di 2 GB; Musicat rileva la memoria fisica totale e visualizza `RAM X.X / YY GB` con aggiornamento asincrono continuo ogni 1.5 secondi.

### 3. 🗂️ Albero Drive & Cartelle a Sinistra, Gestione Colonne (Tasto Destro) & Filtri 2-Row
- **Explorer Cartelle/Unità a Sinistra Collassabile:** Pannello laterale integrato nella Libreria (`QFileSystemModel`) con rilevamento rapido di dischi rigidi, memorie USB e percorsi preferiti a 1-click.
- **Selezione e Personalizzazione Colonne (Tasto Destro):** Cliccando con il tasto destro su una qualsiasi intestazione della tabella, compare il menu contestuale per mostrare o nascondere ciascuna delle 19 colonne (`#`, `Cover`, `Titolo`, `Artista`, `Remixer`, `BPM`, `Camelot`, `Key`, `Genere`, `Anno`, `Album`, `Etichetta`, `Durata`, `Bitrate`, `Energia`, `LUFS`, `True Peak`, `Qualità Audio`, `Percorso`), con memorizzazione automatica di visibilità e larghezze in `config.json`.
- **ComboBox Generi Dinamica Unificata & Fallback "Vario":** Controllo unico editabile con completamento automatico in tempo reale e ordinamento alfabetico; le tracce prive di genere vengono raggruppate coerentemente sotto la voce `"Vario"`.
- **Barra Filtri Multi-Riga Ergonomica (<15ms):** Target BPM con stepping fine (`±2%`, `±4%`, `±6%`, `±8%`), ruota Camelot a 12 posizioni con percorsi armonici ($\pm 1$, Relativa, $+2$ Energy Boost, $+7$ Semitone Lift), filtri decennio, rating ed energia.

### 4. 🏷️ Workspace Mp3tag Avanzato: Autonumerazione & Pattern Live
- **Procedura Guidata Numerazione Tracce (`TrackNumberingWizardDialog`):**
  - Numerazione sequenziale automatica con offset configurabile;
  - Padding a zero configurabile (`01, 02...`);
  - Suffisso opzionale con numero totale di tracce (`01/12`);
  - Azzeramento contatore automatico al cambio di cartella o album;
  - Tabella di anteprima in tempo reale prima del salvataggio.
- **Convertitori Pattern Bidirezionali Live:**
  - **Nome File ➔ Tag (`FilenameToTagDialog`):** Estrazione intelligente dei metadati dal formato dei file con anteprima tabellare immediata;
  - **Tag ➔ Nome File (`TagToFilenameDialog`):** Ridenominazione fisica su disco con maschere flessibili e verifica stato;
  - **Supporto Token Avanzato `$num(%track%,2)`:** Formattazione e parsing avanzato del numero traccia con padding personalizzato.
- **Azioni Rapide Maiuscole/Minuscole:** Pulsanti a 1-click per *Title Case*, *MAIUSCOLO* e *minuscolo*.

### 5. ⚡ Motore di Indicizzazione Ultra-Rapido (`SearchEngine`)
- **Windows (NTFS MFT):** Binding Ctypes nativo su `Everything64.dll` per query dirette alla Master File Table in meno di 1 millisecondo su dischi con 100.000+ brani.
- **macOS (APFS/HFS+):** Driver nativo tramite CLI Spotlight (`mdfind`) filtrato su `kMDItemContentTypeTree == 'public.audio'`.
- **Fallback Automatico:** Passaggio trasparente a SQLite FTS5 (Full-Text Search) con trigger automatici e zero configurazione.

### 6. 🎛️ Analisi Acustica Parallela Multiprocesso & Cache L1 in RAM
- **Saturazione CPU Hardware-Aware:** Pool di worker dinamico (`ProcessPoolExecutor`) su tutti i core logici disponibili.
- **Streaming Window Reads:** Analisi spettrale focalizzata sulla finestra centrale di 60s (drop) a 22.050 Hz mono, tagliando l'uso della CPU dell'80%.
- **Cache L1 in RAM (SQLite In-Memory):** Buffer temporaneo in RAM (`:memory:`) per evitare scritture premature su SSD e preservare la vita dei supporti flash; cache LRU in memoria per forme d'onda istantanee.

### 7. 🔊 Plugin Qualità Audio, Clipping Detector & Loudnorm (EBU R128)
- **Conformità Standard EBU R128 / ITU-R BS.1770-4:** Misurazione Integrated Loudness (LUFS), True Peak (dBTP) con oversampling 4x sinc/spline e Loudness Range (LRA).
- **Diagnosi Anomalie:** Segnalazione visiva di tracce con clipping inter-sample ($>0$ dBTP), volume troppo basso ($<-18$ LUFS) o dinamica compressa tipo brickwall ($\text{LRA} < 3$ LU).
- **Doppia Correzione:**
  - *Non distruttiva:* Tag metadati ReplayGain (`REPLAYGAIN_TRACK_GAIN`, `REPLAYGAIN_TRACK_PEAK`).
  - *Fisica con FFmpeg:* Re-encoding a 2 passaggi con filtro `loudnorm` (target: $-14$ LUFS, $-1.0$ dBTP).

### 8. 🏠 Dashboard Trends Multi-Piattaforma & Motore Tracce Simili
- **Classifiche Multi-Sorgente:** Schede dedicate per `Top Spotify`, `Top SoundCloud / Hype` e `Top Beatport / Discogs`. Categorie musicali contestuali, dataset offline estesi e navigazione ad alta reattività.
- **Riconciliazione Istantanea con la Collezione:** Badge visivo per verificare al volo se la traccia in classifica è già presente nel proprio hard disk (`✓ In Libreria`) o mancante (`+ Mancante`).
- **Motore di Similarità (Cosine.club):** Ricerca vettoriale su database online e matching acustico diretto contro la propria libreria locale.

### 9. ⚖️ Scraping Multi-Fonte, Discogs Priority & Test Connessione Live
- **Discogs come Autorità Prioritaria:** Riconciliatore di metadati ottimizzato per dare precedenza autorevole a Discogs per anno, etichetta discografica, catalog number, formato vinile/digitale e artisti.
- **Integrazioni API Complete:** Campi credenziali persistenti per Spotify, SoundCloud, YouTube Data API v3, Discogs e Beatport con pulsanti di **Test Connessione Live** e riscontro visivo istantaneo (verde/rosso).
- **Tabella di Riconciliazione Conflitti:** Matrice visuale per risolvere punto per punto le discrepanze tra le varie fonti online prima dell'applicazione ai file fisici.

### 10. 💾 Installazione Dual-Mode & Portabilità Totale (`portable.lock`)
- **Modalità Standard:** Installazione guidata in `Program Files`, collegamenti di sistema e dati utente in `%APPDATA%\Musicat`.
- **Modalità Portable:** Estrazione pulita su qualsiasi chiavetta o SSD esterno. La presenza di `portable.lock` forza il salvataggio di impostazioni, database e log esclusivamente nella cartella locale dell'app (`./logs/`, `./musicat_data/`).
- **Risolutore Volume Serial Number (`[VOL:XXXXXXXX]`):** Converte i path assoluti in percorsi relativi al drive fisico, consentendo di spostare lo stesso SSD tra Windows e macOS senza perdere il catalogo.

---

## 🛠️ Suite di Logging Avanzato & Troubleshooting

Musicat integra una suite completa di tracciamento e diagnostica orientata al troubleshooting rapido:

### 1. Rotazione Automatica & Compressione `.zip`
- I log correnti vengono scritti in `musicat.log`.
- Al raggiungimento della soglia massima di **20 MB**, il file viene ruotato e compresso automaticamente in formato `.zip` (`musicat.log.1.zip`, `musicat.log.2.zip`, ...).
- Vengono conservati automaticamente gli ultimi **10 file compressi**, evitando consumi anomali di spazio su disco.

### 2. Tracciamento Granulare di Dominio
Ogni operazione interna ed esterna viene registrata con livello e categoria:
- **I/O & Scansioni (`[SCAN]`):** percorsi analizzati, file totali, inseriti, scartati e durata scansione.
- **Audio Engine libVLC (`[PLAYER:VLC]`):** inizializzazione libreria `libvlc`, carimento file, seek, pitch bending ed errori di decodifica.
- **Tag Editor Mutagen (`[TAG]` & `[TAG:DIFF]`):** dump dei metadati prima e dopo la modifica, diff campi sovrascritti ed errori ID3.
- **Scrapers & HTTP (`[HTTP:<Fonte>]`):** URL interrogati, parametri, codice di stato HTTP (200, 403, 404), latenza di risposta in millisecondi ed eventuali eccezioni.
- **File Manager (`[DISPATCH:<OP>]`):** percorsi sorgente/destinazione (`SRC -> DEST`), strategie di risoluzione collisioni (`RENAME`, `OVERWRITE`, `SKIP`).

### 3. Esportazione Log per Assistenza (Bundle Diagnostico)
Sia nella **Live Log Console** (`Ctrl+L`) sia nella sezione **Impostazioni > Prestazioni**, è presente il pulsante:
👉 **"Esporta Log per Assistenza (.zip)"**
Questo genera istantaneamente un archivio zip contenente:
- Tutti i file di log correnti e archiviati.
- Metriche hardware anonimizzate (CPU, RAM, GPU, OS).
- Statistiche del database (numero tracce, indici, stato WAL).
- File di configurazione sanificato (con credenziali e token API oscurati).

---

## 🔍 Guida alla Risoluzione dei Problemi (Troubleshooting)

### 1. Il player non riproduce i brani o segnala "libVLC non trovato"
- **Windows:** Assicurati di aver installato VLC Media Player a 64-bit (`C:\Program Files\VideoLAN\VLC`) oppure estrai `libvlc.dll` e la cartella `plugins/` nella directory dell'eseguibile di Musicat.
- **macOS:** Installa VLC tramite Homebrew (`brew install --cask vlc`) o posiziona `VLC.app` nella cartella `/Applications`.

### 2. La ricerca rapida Everything MFT non si attiva su Windows
- Musicat utilizza il servizio di **Voidtools Everything**. Assicurati che l'applicazione desktop Everything sia in esecuzione in background per consentire l'accesso istantaneo tramite IPC.
- In assenza del servizio Everything, Musicat attiva automaticamente il fallback su **SQLite FTS5**, garantendo la ricerca a pieno testo senza interruzioni.

### 3. Lettere dei dischi esterne modificate su Windows
- Musicat memorizza gli ID fisici del volume (`[VOL:XXXXXXXX]`). Se la lettera dell'unità USB passa ad esempio da `E:\` a `F:\`, Musicat ricollega automaticamente tutti i percorsi della libreria al primo avvio.

### 4. Errore di scrittura tag (Permesso Negato / File Occupato)
- Se un file audio è aperto in riproduzione in un altro software (es. Rekordbox o Traktor), Windows impone un blocco di scrittura. Chiudi il lettore esterno prima di avviare il tag editing batch.

---

## ⌨️ Scorciatoie da Tastiera DJ Console

| Tasto Rapido | Azione | Descrizione |
|---|---|---|
| `Ctrl + F` | Ricerca Rapida | Attiva la barra di ricerca unificata (Everything MFT / Spotlight / FTS) |
| `Ctrl + G` | Filtro Generi | Attiva la casella generi con autocomplete multi-selezione |
| `Ctrl + B` | Filtro BPM | Seleziona la casella Target BPM |
| `Ctrl + K` | Ruota Camelot | Apre l'assistente visivo Ruota Camelot per il mix armonico |
| `Esc` | Ripristina Filtri | Cancella istantaneamente ogni filtro e mostra l'intera libreria |
| `Spazio` | Play / Pausa | Avvia/ferma la riproduzione del brano o preascolta la traccia selezionata |
| `Invio` | Carica nel Deck | Carica il brano selezionato nel mini-player |
| `Ctrl + T` | Spazio Mp3tag | Apre la workbench dedicata in stile Mp3tag |
| `Ctrl + E` | Tag Rapidi | Apre il modal di modifica batch dei tag |
| `Ctrl + R` | Riconciliazione | Avvia la riconciliazione metadati da fonti multiple |
| `Ctrl + Q` | Qualità Audio | Apre la diagnostica del volume e clipping EBU R128 |
| `Ctrl + Shift + S`| Trova Simili | Trova tracce compatibili nella propria libreria locale e online |
| `Ctrl + Shift + P` / `Alt + F` | Tag da Pattern | Apre il dialog avanzato Mp3tag per estrazione massiva da maschera/pattern con anteprima live |
| `Ctrl + S` | Smart Organizer | Apre lo strumento di smistamento e spostamento fisico su disco |
| `Ctrl + L` | Log in Tempo Reale | Mostra/nasconde la console dei log di sistema |
| `Ctrl + ,` | Impostazioni | Apre la finestra Preferenze di Sistema |
| `Alt + 1` .. `Alt + 6` | Navigazione Viste | Alterna rapidamente tra i moduli della Top Bar |

---

## 📦 Download & Release Ufficiali

Ad ogni rilascio su GitHub vengono generati automaticamente tramite GitHub Actions i pacchetti pronti all'uso:

| Piattaforma | File di Rilascio | Descrizione |
|---|---|---|
| **Windows 10/11 x64** | `Musicat-Setup-Windows-x64.exe` | Installer Inno Setup Dual-Mode (Standard o Portabile) |
| **Windows 10/11 x64** | `Musicat-Windows-Portable.zip` | Archivio standalone portabile pronto all'uso (`portable.lock`) |
| **macOS Universal** | `Musicat-macOS.dmg` | DMG nativo con installazione Drag & Drop in Applicazioni |
| **macOS Universal** | `Musicat-macOS-Portable.zip` | Pacchetto portatile per SSD esterni formattati in APFS/HFS+ |

👉 **[Scarica l'Ultima Release Ufficiale (v1.5.0)](https://github.com/IlRed89/Musicat/releases/latest)**

---

## 🛠️ Installazione dai Sorgenti

### Prerequisiti
- Python 3.11, 3.12 o 3.13 (64-bit)
- `git`
- libVLC (o VLC Media Player installato nel sistema)
- (Opzionale su Windows) Inno Setup 6.2+ per generare l'installer

### Procedura

```bash
# 1. Clona il repository
git clone https://github.com/IlRed89/Musicat.git
cd Musicat

# 2. Crea ed attiva un ambiente virtuale
python -m venv venv
# Su Windows:
.\venv\Scripts\activate
# Su macOS / Linux:
source venv/bin/activate

# 3. Installa le dipendenze
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Esegui la suite completa di test unitari (132 test)
python -m unittest discover tests -v

# 5. Avvia l'applicazione
python main.py
```

### Compilazione Standalone Locale

```bash
# Eseguibile Standalone per Windows
pyinstaller --clean build_windows.spec

# Pacchetto Portatile Windows completo (Batch)
.\build\build_portable.bat

# Applicazione macOS e creazione DMG
pyinstaller --clean build_mac.spec
./build/build_mac_dmg.sh
```

---

## 📄 Licenza

Musicat è distribuito sotto licenza open-source **MIT**.  
Consulta il file [LICENSE](LICENSE) per i termini completi.
