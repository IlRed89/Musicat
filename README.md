# 🐱🎧 Musicat

> **Il Catalogatore Universale per DJ, Metadata Engine Stile Mp3tag & Smart Organizer Acustico.**  
> *Sviluppato specificamente per DJ professionisti, collezionisti musicali e archivisti con librerie di grandi dimensioni (50.000+ tracce su dischi esterni).*

[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](README.md)
[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](README_EN.md)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Piattaforma](https://img.shields.io/badge/piattaforma-Windows%2010%2F11%20x64%20%7C%20macOS%20Universal-brightgreen.svg)]()
[![Repository Ufficiale](https://img.shields.io/badge/github-IlRed89%2FMusicat-orange.svg)](https://github.com/IlRed89/Musicat)
[![Licenza](https://img.shields.io/badge/licenza-MIT-purple.svg)](LICENSE)

---

## 🌟 Panoramica & Visione

La gestione di oltre **50.000 brani** su SSD esterni comporta criticità note a qualsiasi DJ:
- Le lettere di unità di Windows o i punti di mount APFS/HFS+ di macOS cambiano costantemente quando si collegano dischi a porte diverse o si passa tra computer diversi, corrompendo i database dei player tradizionali.
- I software DJ da console (Rekordbox, Traktor, Serato, Engine DJ) non offrono funzionalità complete di tag editing massivo, scraping da fonti multiple e diagnosi acustica.
- Gli editor di tag generici (come Mp3tag) non dispongono di player audio integrato con pitch bending, analisi DSP (BPM e Camelot Key), filtri live in tempo reale né sincronizzazione con le classifiche online.

**Musicat** integra in un'unica interfaccia desktop dark e ad alte prestazioni 10 pilastri fondamentali compatibili nativamente con **Windows (10/11 x64)** e **macOS (Apple Silicon M-Series + Intel x64)**.

---

## 🚀 Architettura dei 10 Moduli Chiave

```
+----------------------------------------------------------------------------------------------------+
|                                              MUSICAT                                               |
+----------------------------------------------------------------------------------------------------+
|  [Live DJ Crates]   |  [Spazio Mp3tag]     |  [Motore Acustico]  |  [Plugin Loudnorm]  | [Trends]  |
|  - Filtri RAM <15ms |  - Foglio di Calcolo |  - Multiprocessing  |  - EBU R128 LUFS    | - Spotify |
|  - Ruota Camelot    |  - Editing Batch     |  - FFT BPM & Key    |  - True Peak dBTP   | - Cosine  |
|  - Generi Multi (OR)|  - Pattern %tag%     |  - Cache L1 in RAM  |  - Normalizzazione  | - Simili  |
+----------------------------------------------------------------------------------------------------+
|         Motore Ricerca Rapida (Voidtools Everything MFT / macOS Spotlight / SQLite FTS5)           |
+----------------------------------------------------------------------------------------------------+
|                 Engine libVLC con Pitch Bend +/-8% e Waveform Scrubbing Interattivo                |
+----------------------------------------------------------------------------------------------------+
|          Risolutore Path Multi-Piattaforma ([VOL:XXXXXXXX] & portable.lock Drive Migration)        |
+----------------------------------------------------------------------------------------------------+
```

### 1. 🎛️ Live DJ Crates & Barra Filtri Rapidi (<15ms di Latenza)
- **Selettore Multi-Genere:** Autocomplete istantaneo con selezione multipla e logica `OR` (es. *Tech House* OR *Afro House* OR *Melodic Techno*).
- **Target BPM & Tolleranze Pitch:** Box numerico con preset a percentuale (`±2%`, `±4%`, `±6%`, `±8%`) ed estremi Min/Max personalizzabili.
- **Assistente Armonico Ruota Camelot:** Griglia interattiva a 12 colonne (`1A`–`12B`) con indicazione di percorsi armonici:
  - $\pm 1$ Passaggio armonico fluido (stabilità energetica)
  - Scala Relativa (passaggio Maggiore $\leftrightarrow$ Minore)
  - $+2$ Energy Boost (innalzamento netto dell'energia)
  - $+7$ Semitone Peak Lift (salto di semitono per picchi di climax)
- **Smart Crates & Esportazione M3U8:** Salvataggio istantaneo delle combinazioni di filtri in crate dinamici ed esportazione in playlist `.m3u8` compatibili con Pioneer CDJ, Rekordbox, Traktor, Serato ed Engine DJ.

### 2. 🏷️ Spazio Mp3tag Dedicato & Tag Editor Avanzato
- **Visualizzazione Tabellare a Foglio di Calcolo:** Modifica inline rapida su singola cella o editing simultaneo batch su selezioni multiple.
- **Convertitore Pattern Nome File <-> Tag:** Motore bidirezionale con token `%artist% - %title% (%bpm% BPM) [%camelot%]`.
- **Iniezione Copertine HD Studio:** Download e incorporamento di cover fino a 3000x3000px (da Apple Music CDN e Beatport) direttamente nei file (`APIC`, Picture block FLAC, atomo `covr` MP4).
- **Supporto Contenitori Universali:** MP3, FLAC, WAV (fino a 32-bit float), AIFF, M4A/ALAC, OGG Vorbis e OPUS.

### 3. ⚡ Motore di Indicizzazione Ultra-Rapido (`SearchEngine`)
- **Windows (NTFS MFT):** Binding Ctypes nativo su `Everything64.dll` per query dirette alla Master File Table in meno di 1 millisecondo su dischi con 100.000+ brani.
- **macOS (APFS/HFS+):** Driver nativo tramite CLI Spotlight (`mdfind`) filtrato su `kMDItemContentTypeTree == 'public.audio'`.
- **Fallback Automatico:** Passaggio trasparente a SQLite FTS5 (Full-Text Search) con trigger automatici e zero configurazione.

### 4. 🎛️ Analisi Acustica Parallela Multiprocesso & Cache L1 in RAM
- **Saturazione CPU Hardware-Aware:** Pool di worker dinamico (`ProcessPoolExecutor`) su tutti i core logici disponibili.
- **Streaming Window Reads:** Analisi spettrale focalizzata sulla finestra centrale di 60s (drop) a 22.050 Hz mono, tagliando l'uso della CPU dell'80%.
- **Cache L1 in RAM (SQLite In-Memory):** Buffer temporaneo in RAM (`:memory:`) per evitare scritture premature su SSD e preservare la vita dei supporti flash; cache LRU in memoria per forme d'onda istantanee.

### 5. 🔊 Plugin Qualità Audio, Clipping Detector & Loudnorm (EBU R128)
- **Conformità Standard EBU R128 / ITU-R BS.1770-4:** Misurazione Integrated Loudness (LUFS), True Peak (dBTP) con oversampling 4x e Loudness Range (LRA).
- **Diagnosi Anomalie:** Segnalazione visiva di tracce con clipping inter-sample ($>0$ dBTP), volume troppo basso ($<-18$ LUFS) o dinamica compressa tipo brickwall ($\text{LRA} < 3$ LU).
- **Doppia Correzione:**
  - *Non distruttiva:* Tag metadati ReplayGain (`REPLAYGAIN_TRACK_GAIN`, `REPLAYGAIN_TRACK_PEAK`).
  - *Fisica con FFmpeg:* Re-encoding a 2 passaggi con filtro `loudnorm` (target: $-14$ LUFS, $-1.0$ dBTP).

### 6. 🏠 Spotify Top Trends & Motore Tracce Simili
- **Top Trends Spotify Live:** Classifiche suddivise per genere (Dance/Electro, Tech House, Techno, Global Top 50) con caching locale di 24 ore.
- **Riconciliazione Istantanea con la Collezione:** Badge visivo per verificare al volo se la traccia in classifica è già presente nel proprio hard disk (`✓ In Libreria`) o mancante (`+ Mancante`).
- **Motore di Similarità (Cosine.club):** Ricerca vettoriale su database online e matching acustico diretto contro la propria libreria locale.

### 7. ⚖️ Scraping Multi-Fonte & Riconciliazione Conflitti
- Query simultanea verso **Beatport**, **Traxsource**, **Discogs**, **MusicBrainz** e piattaforme social (**SoundCloud**, **YouTube Music**, **Hypeddit**, **Remix.audio**).
- Tabella di riconciliazione "Prima / Dopo" con risoluzione campo per campo (seleziona Titolo da Beatport, Anno da Discogs, Etichetta da Traxsource).

### 8. 📦 Smart Organizer & Smistamento Fisico su Disco
- Riorganizzazione della struttura delle cartelle in base a maschere flessibili: `{Genre}/{bpm_range}/{Camelot} - {Artist} - {Title}.ext`.
- Modalità **Dry Run (Simulazione)** obbligatoria con tabella di anteprima, collision detection e spostamento fisico sicuro.

### 9. 💾 Installazione Dual-Mode & Portabilità Totale (`portable.lock`)
- **Modalità Standard:** Installazione guidata in `Program Files`, collegamenti di sistema e dati utente in `%APPDATA%\Musicat`.
- **Modalità Portable:** Estrazione pulita su qualsiasi chiavetta o SSD esterno. La presenza di `portable.lock` forza il salvataggio di impostazioni, database e log esclusivamente nella cartella locale dell'app.
- **Risolutore Volume Serial Number (`[VOL:XXXXXXXX]`):** Converte i path assoluti in percorsi relativi al drive fisico, consentendo di spostare lo stesso SSD tra Windows e macOS senza perdere il catalogo.

### 10. 🌐 Localizzazione Bilingue (Italiano / Inglese)
- **Italiano (Lingua Predefinita):** Supporto completo in lingua italiana di ogni finestra, tabella, filtro e menu contestuale.
- **Inglese (Lingua Secondaria):** Traduzione integrale per il mercato internazionale.
- **Cambio Istantaneo a Caldo:** Selezione della lingua nelle Preferenze senza alcun riavvio dell'applicazione.

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
| `Ctrl + S` | Smart Organizer | Apre lo strumento di smistamento e spostamento fisico su disco |
| `Ctrl + L` | Log in Tempo Reale | Mostra/nasconde la console dei log di sistema |
| `Ctrl + ,` | Impostazioni | Apre la finestra Preferenze di Sistema |
| `Alt + 1` / `Alt + 2` | Cambio Vista | Alterna rapidamente tra Libreria DJ e Home Trends |

---

## 📦 Download & Release Ufficiali

Ad ogni rilascio su GitHub vengono generati automaticamente tramite GitHub Actions i pacchetti pronti all'uso:

| Piattaforma | File di Rilascio | Descrizione |
|---|---|---|
| **Windows 10/11 x64** | `Musicat-Setup-Windows-x64.exe` | Installer Inno Setup Dual-Mode (Standard o Portabile) |
| **Windows 10/11 x64** | `Musicat-Windows-Portable.zip` | Archivio standalone portabile pronto all'uso (`portable.lock`) |
| **macOS Universal** | `Musicat-macOS.dmg` | DMG nativo con installazione Drag & Drop in Applicazioni |
| **macOS Universal** | `Musicat-macOS-Portable.zip` | Pacchetto portatile per SSD esterni formattati in APFS/HFS+ |

👉 **[Scarica l'Ultima Release Ufficiale (v1.0.0)](https://github.com/IlRed89/Musicat/releases)**

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

# 4. Esegui la suite completa di test unitari (124+ test)
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
