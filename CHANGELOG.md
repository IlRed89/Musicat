# 📋 Registro Modifiche (Changelog)

Tutte le modifiche e le funzionalità ufficiali di **Musicat** sono documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto aderisce al [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[![Lingua: Italiano](https://img.shields.io/badge/Lingua-Italiano-green.svg)](CHANGELOG.md)
[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](CHANGELOG_EN.md)

---

## [1.3.0] - 2026-10-28 — Official Consolidated Release (Release Ufficiale Consolidata)

Release ufficiale consolidata di **Musicat** focalizzata su incremento delle prestazioni dell'analisi audio, layout responsive adattivo per display compatti, Drag & Drop unificato, scorciatoie ad Accesso Rapido nell'albero delle cartelle, isolamento completo del Tag Editor (Mp3tag) e revisione completa dei protocolli di autenticazione online.

### 🌟 Novità e Interventi della Release v1.3.0

#### 1. ⚡ Analisi Acustica Accelerata & Parallelizzazione Multi-Thread
- **Worker Pool Multi-Thread Concorrente:** `AsyncAnalysisWorker` esegue l'analisi audio appoggiandosi a `ThreadPoolExecutor` dimensionato sul numero di core fisici disponibili (`os.cpu_count()`), processando più tracce contemporaneamente senza saturare l'Event Loop dell'interfaccia.
- **Fast-Pass Acoustic Analysis:** Implementato campionamento rapido su finestra centrale ottimizzata (60–90 secondi al 25% della durata della traccia) per il calcolo di BPM e tonalità Camelot, riducendo drasticamente l'impatto di I/O e i tempi di elaborazione.
- **Scraping di Rete Asincrono con Timeout Stringenti:** Limite di timeout a 2.5 – 3.0 secondi su tutte le chiamate esterne (Discogs, MusicBrainz, Wikipedia, YouTube), prevenendo colli di bottiglia o blocchi della coda di analisi.

#### 2. 📱 Layout Responsive Adattivo & Risoluzione Overflow
- **Barra Filtri Scorrevole:** La barra di controllo e filtraggio è racchiusa in una `QScrollArea` orizzontale invisibile con scroll fluido, eliminando qualsiasi sovrapposizione di pulsanti o troncamento di testo su display a bassa risoluzione o finestre ridotte.
- **Padding e Min-Width Ottimizzati:** Regolazione delle dimensioni minime dei selettori per una resa fluida e proporzionata a ogni livello di zoom o ridimensionamento.

#### 3. 🧹 Pulsante "Svuota Vista" nella Libreria
- **Reset Visuale a 1-Click:** Aggiunto il pulsante `[🧹 Svuota Vista]` nella barra strumenti della Libreria (`table_model.clear_view()`), permettendo di ripulire immediatamente la tabella a video senza cancellare file fisici su disco né rimuovere record dal database SQLite.

#### 4. 📂 Drag & Drop Diretto su Tabella Libreria
- **Importazione Rapida via Trascinamento:** Abilitato il rilascio diretto (`dragEnterEvent`, `dropEvent`) di file singoli o intere cartelle audio direttamente sulla griglia principale della Libreria, con scansione ricorsiva automatica dei formati supportati e inserimento trasparente a video e nel database.

#### 5. 🖥️ Sezione Accesso Rapido nell'Esplora File
- **Scorciatoie Cartelle di Sistema:** Ridisegnata la colonna sinistra della Libreria posizionando in cima una sezione fissa ad Accesso Rapido con icone native per Desktop, Documenti, Download e Musica, mantenendo sotto la voce "Questo PC / Dischi" per la navigazione delle sole unità fisiche.

#### 6. ⚡ Menu Contestuale con Tasto "Analizza" Dedicato
- **Analisi Mirata su Selezione:** Inserita come prima voce in grassetto del menu contestuale (tasto destro) l'azione `[⚡ Analizza Tracce Selezionate]`, consentendo di avviare l'elaborazione acustica esclusivamente sui file evidenziati.
- **Instradamento Diretto Mp3tag:** Aggiunta la voce `[🏷️ Invia a Tag Editor (Mp3tag)...]` per inviare le tracce selezionate alla vista di tagging in un solo click.

#### 7. 🏷️ Disaccoppiamento Completo dello Spazio di Lavoro Mp3tag
- **Isolamento dello Stato della Vista:** Eliminata qualsiasi sincronizzazione o azzeramento automatico all'apertura del Tag Editor. La tabella di Mp3tag mantiene intatto il suo stato operativo indipendente.
- **Controlli di Caricamento Autonomi:**
  - Aggiunti pulsanti dedicati in toolbar e menu: `[➕ Aggiungi File...]` (`Ctrl+O`), `[📁 Aggiungi Cartella...]` (`Ctrl+D`), `[🧹 Svuota Elenco]`.
  - Drag & Drop autonomo di file e directory direttamente sulla griglia di Mp3tag (`Mp3tagTableWidget`).

#### 8. 🔑 Autenticazione OAuth2 & Servizi Online
- **Spotify OAuth2 Conforme:** Generazione dell'URL di login con parametri espliciti `response_type=code`, `client_id`, `redirect_uri=http://localhost:8888/callback` e scope per la lettura e manipolazione delle playlist utente.
- **SoundCloud Token Fallback:** Aggiunta la possibilità di inserire direttamente il token di sessione per aggirare la chiusura delle registrazioni di app pubbliche su SoundCloud.
- **YouTube Data API v3:** Autenticazione diretta con Google Cloud API Key e test di validazione in tempo reale, eliminando gli errori `401: invalid_client`.

#### 9. 🎨 Cambio Tema Dinamico a Caldo & FFmpeg Bundled
- **Switch Tema Istantaneo:** Passaggio tra tema chiaro e tema scuro applicato a caldo a livello di applicazione senza riavvii né chiusure forzate della finestra Impostazioni.
- **FFmpeg Pre-incluso di Default:** Ricerca e impostazione automatica dell'eseguibile predefinito in `bin/ffmpeg.exe`, con indicatore visivo di stato e pulsante "Sfoglia..." opzionale.

---

## [1.2.0] - 2026-10-19 — Release Ufficiale Consolidata

- Motore di elaborazione audio DSP professionale basato su Spotify Pedalboard, FFmpeg libavfilter e JUCE VST3.
- Autofit dinamico della larghezza delle colonne con margine di sicurezza +16px anti-ellissi.
- Avvio massimizzato a schermo intero di default.
- Riorganizzazione della barra di navigazione con Smart Crates ancorato a destra.
- Ripristino del pulsante "Simili" nel player e isolamento del contesto delle classifiche.
