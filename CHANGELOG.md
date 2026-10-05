# 📋 Registro Modifiche (Changelog)

Tutte le modifiche e le funzionalità ufficiali di **Musicat** sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto aderisce al [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)
[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)

---

## [1.1.0] - 2026-10-05 — Release Ufficiale Consolidata (Official Consolidated Release)

Prima release pubblica ufficiale e consolidata di **Musicat**, il catalogatore desktop universale per DJ, tag editor stile Mp3tag e smart organizer acustico ad alte prestazioni.

### 🌟 Panoramica delle Funzionalità Consolidate

#### 1. 🌐 Motore di Arricchimento Metadati & Scraping Multi-Source a Cascata
- **Cascata Multi-Provider Intelligente:** Interrogazione asincrona e parallela delle maggiori banche dati musicali:
  - **Discogs API:** Identificazione della *Master Release* per l'anno di prima pubblicazione originale e prioritizzazione del campo `styles` (es. *Tech House*, *Melodic Techno*, *Afro House*, *Deep House*) per superare l'etichettatura generica *"Electronic"*.
  - **MusicBrainz / AcousticBrainz:** Recupero della release date originaria e dei tag di stile assegnati dalla community.
  - **Beatport & Traxsource:** Estrazione mirata dei sottogeneri per musica dance ed elettronica da club.
  - **WebEnricher Fallback (Wikipedia Knowledge Graph & YouTube Search):** In assenza di match nei database musicali, esegue query web `"[Artista] - [Titolo] genre year"` per parsare la data di caricamento e la categoria musicale verificata.
- **Normalizzazione Rigorosa dei Generi:** Rifiuto preventivo di etichette vaghe (*Other*, *Unknown*, *Soundtrack*, *Music*, *Various*, *General*), preferenza netta per i sottogeneri DJ specifici e assegnazione di `"Vario"` rigorosamente come ultima risorsa estrema.
- **Dialogo di Riconciliazione Asincrono (`ReconcilerDialog`):** Layout chiaro a quattro colonne (*Campo*, *Valore Attuale*, *Valore Rilevato*, *Valore da Applicare*) con altezza righe ottimizzata (36px), ridimensionamento elastico e traduzione integrale in lingua italiana.

#### 2. 📁 Libreria DJ ad Alte Prestazioni & Riordino Colonne Drag & Drop
- **Schermata Predefinita all'Avvio:** Avvio istantaneo diretto sulla vista Libreria (Index 0 del container principale).
- **Riordino Interattivo Drag & Drop:** Header della tabella mobile (`setSectionsMovable(True)`, `setDragEnabled(True)`) con riorganizzazione visiva immediata delle colonne.
- **Persistenza Layout Esadecimale:** Lo stato dell'intestazione (ordine visivo, visibilità e larghezze in pixel) viene serializzato tramite `saveState()` in formato esadecimale e memorizzato in `config.json` (`ui.header_state`), con ripristino automatico a ogni riavvio.
- **Colonne DJ Essenziali:** Nascoste di default le colonne superflue di calcolo interno (`energy_level`, `lufs`, `true_peak`, `audio_status`), lasciando spazio perfetto per le 12 colonne essenziali: `#`, `Cover`, `Titolo`, `Artista`, `Remixer`, `BPM`, `Camelot`, `Key`, `Genere`, `Anno`, `Durata`, `Bitrate`.
- **Menu Contestuale Intestazione (Tasto Destro):** Possibilità di attivare/disattivare a piacimento qualsiasi colonna dell'archivio (19 colonne complessive) con funzione a 1-click *"Mostra Tutte le Colonne"*.
- **Pannello File Explorer a Sinistra:** Albero di navigazione delle cartelle e unità disco (`QFileSystemModel`) con visualizzazione rapida dei drive collegati e sincronizzazione bidirezionale senza lock sui file.
- **Filtri Live a Due Righe (<15ms):** Ricerca Full-Text istantanea con normalizzazione automatica dei separatori di cartella (`/` e `\`), filtri BPM con tolleranza percentuale ($\pm 2\% \dots \pm 8\%$), ruota Camelot a 12 posizioni con percorsi armonici ($\pm 1$, Relativa, $+2$ Energy Boost, $+7$ Semitone Lift), filtri decennio, energia e rating.
- **Menu a Tendina Generi Dinamico:** Rimosso qualsiasi elenco fisso; il selettore è alimentato esclusivamente dai brani reali presenti nel database SQLite, con `"🏷️ Tutti i Generi"` in cima, generi in ordine alfabetico e voce `"Vario"` in fondo. Sottocontrolli CSS espliciti (`QComboBox::drop-down` e `QComboBox::down-arrow`) con freccia sempre visibile sia in tema chiaro che in tema scuro.

#### 3. ⚡ Tasto Rapido Toolbar "Analizza Selezionate" & Worker Asincrono
- **Pulsante Principale Toolbar `[⚡ Analizza Selezionate]`:** Integrato direttamente nella riga comandi superiore della Libreria con styling accent visibile.
- **Logica di Analisi Flessibile:** Analizza le tracce selezionate nella tabella; se nessuna traccia è selezionata, analizza l'intera cartella correntemente aperta nell'albero cartelle; se non c'è nulla, mostra notifica discreta nella barra di stato.
- **Worker Multithread Asincrono (`AsyncAnalysisWorker`):** Calcolo DSP (BPM, Chiave Camelot/Musicale), estrazione pattern e scrittura fisica eseguiti in background senza alcun blocco o freeze dell'interfaccia grafica.
- **Avanzamento Discreto & Annullamento:** Barra di progresso integrata nella status bar con pulsante rosso `[✕ Annulla]` per interrompere il processo in tempo reale.
- **Persistenza Fisica Tag con Mutagen:** Separazione automatica del pattern `"Artista - Titolo"` se l'artista è vuoto, rilascio esplicito dei file handle e gestione dei lock di sistema operativo su dischi esterni.

#### 4. 🏷️ Workspace Mp3tag Incorporato & Bulk Pattern Tagging
- **Interfaccia Foglio di Calcolo Integrata:** Vista tabellare avanzata per l'editing massivo dei metadati senza finestre modali esterne.
- **Procedura Guidata Numerazione Tracce (`TrackNumberingWizardDialog`):** Numerazione sequenziale automatica con padding (`01, 02...`), formato frazionario (`01/12`), offset iniziale e azzeramento contatore a ogni cambio di cartella/album.
- **Convertitori Pattern Bidirezionali Live:**
  - **Nome File ➔ Tag (`FilenameToTagDialog`):** Parsing automatico dei metadati dai nomi dei file con token flessibili (`%artist%`, `%title%`, `%album%`, `%bpm%`, `%key%`, `%year%`, `%genre%`) e supporto al token avanzato `$num(%track%,2)`.
  - **Tag ➔ Nome File (`TagToFilenameDialog`):** Ridenominazione fisica massiva dei file su disco con anteprima in tempo reale.
- **Azioni Rapide Maiuscole/Minuscole:** Pulsanti a 1-click per conversione immediata in *Title Case*, *MAIUSCOLO* e *minuscolo*.

#### 5. 📦 Smart Crates Dedicati & Esportazione Playlist M3U8
- **Workbench Dedicato:** Sezione incorporata con guida interattiva alla creazione delle regole di filtraggio intelligente.
- **Regole Dinamiche DJ:** Creazione di casse intelligenti basate su genere, intervalli BPM precisi, tonalità Camelot compatibili, anno di rilascio e rating.
- **Esportazione Universale:** Generazione ed esportazione di playlist compatibili in formato M3U / M3U8 esteso per Serato DJ, Pioneer Rekordbox, Traktor Pro e Engine DJ.

#### 6. 🔍 Ricerca Rapida Universale & Trova Simili
- **Ricerca Ultra-Rapida su Disco:**
  - **Windows:** Indicizzazione NTFS Master File Table (MFT) a livello di kernel tramite `Everything64.dll` (<1ms per 100.000 file).
  - **macOS:** Driver nativo Spotlight (`mdfind`) per il recupero istantaneo dei file audio.
  - **Fallback Universale:** Motore SQLite FTS5 integrato per qualsiasi file system o volume di rete.
- **Discovery Armonica "Trova Simili":** Ricerca locale basata sulla distanza euclidea e similarità coseno tra vettori acustici (BPM, Camelot, Loudness), affiancata dalla ricerca online su Chosic e Cosine.club per la scoperta di brani affini da suonare in sequenza.

#### 7. 🔊 Player Audio libVLC, Loudness Meter EBU R128 & Dialog "Correggi Audio"
- **Motore Audio libVLC Integrato:** Mini-player con waveform interattiva, pitch bending $\pm 8\%$, loop A-B, volume digitale e supporto a tutti i formati (MP3, WAV, FLAC, AIFF, M4A, OGG).
- **Ascolto Anteprima Streaming Top Charts:** Riproduzione immediata dei 30 secondi di preview forniti da Spotify, SoundCloud e Beatport senza interruzioni.
- **Loudness Meter Disattivato su Brani Non Analizzati:** Eliminata l'indicazione fittizia `-70 LUFS / -100 dBTP`; i brani non ancora analizzati mostrano il segnaposto neutro disattivato `"— LUFS | TP: — dBTP (Non analizzato)"`.
- **Dialog "Correggi Audio" Nativo in Tema Chiaro:** Sfondo nativo bianco `#ffffff`, testi ad alto contrasto `#212529`, card didattica *"Tips & Spiegazioni Operative"* con le specifiche tecniche di normalizzazione (ReplayGain metadati non distruttivi vs FFmpeg loudnorm a -1.0 dBTP headroom) e cursori target configurabili per DJ/Club (-9/-10 LUFS) e streaming (-14 LUFS).

#### 8. ⚪ Interfaccia Grafica ad Alto Contrasto (Light Default / Dark Mode)
- **Palette Chiara Predefinita:** Stile moderno ed ergonomico basato su sfondi ad alto contrasto (`#FFFFFF` / `#F8F9FA`), testi scuri leggibili (`#212529`), bordi definiti (`#DEE2E6`) e accenti blu elettrico (`#0D6EFD`).
- **Dark Theme Istantaneo:** Modalità scura attivabile nelle Impostazioni senza riavviare l'applicazione.
- **Monitor Hardware Visivo:** Status bar con progress bar a colori dinamici (Verde 0-60%, Arancione 61-84%, Rosso 85-100%) per CPU e RAM a 64-bit (`RAM X.X / YY GB`).

#### 9. 📂 Organizzatore Fisico File su Disco
- **Smistamento Massivo:** Riorganizzazione fisica delle cartelle per *Artista/Album*, *Genere/BPM* o maschere personalizzate.
- **Sicurezza e Prevenzione Collisioni:** Modalità *Dry-Run* di simulazione prima della copia/spostamento, gestione delle collisioni di nomi file (rinomina progressiva automatica o skip) e log di operazione.

#### 10. 🩺 Early Bootstrap Diagnostics Suite & Esecuzione Portabile
- **Early Logging Multi-Piattaforma:** Inizializzazione immediata su file flushato prima dell'importazione di PySide6 o libVLC, con rilevamento architettura CPU (Apple Silicon ARM64, Rosetta 2, Intel x64), memoria totale e versione del sistema operativo.
- **Trap dei Crash con `faulthandler`:** Scrittura automatica dello stack trace su disco in caso di segfault o crash C/C++ non gestiti.
- **Portabilità Assoluta:** Riconoscimento automatico del marker `portable.lock` per salvare configurazione, database SQLite e log all'interno della cartella dell'eseguibile, consentendo l'uso trasparente su chiavette USB e dischi esterni senza installazione.
