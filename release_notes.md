# Musicat v1.3.0 — Official Consolidated Release

Release ufficiale consolidata di **Musicat** che introduce una suite avanzata di ottimizzazioni prestazionali per l'analisi audio e metadati, layout completamente responsive con eliminazione dell'overflow, importazione istantanea via Drag & Drop, scorciatoie ad Accesso Rapido nell'albero cartelle, isolamento completo dello spazio di lavoro Mp3tag e revisione dell'autenticazione per Spotify, SoundCloud e YouTube.

---

### 🚀 Novità Principali in v1.3.0

#### 1. ⚡ Analisi Acustica Accelerata (Multi-Core & Fast-Pass)
- **Parallelizzazione Concorrente:** Analisi audio su thread pool parallelo dimensionato sul numero effettivo di core CPU fisici (`ThreadPoolExecutor`), garantendo reattività assoluta dell'interfaccia e salvataggi SQLite thread-safe.
- **Fast-Pass Acoustic Analysis:** Calcolo rapido di BPM e chiave armonica Camelot su finestra centrale ottimizzata (60–90 secondi al 25% della durata), riducendo dell'80% i tempi di decodifica e I/O.
- **Scraping Asincrono a Bassa Latenza:** Timeout stringenti (2.5s – 3.0s) su Discogs, MusicBrainz, Wikipedia e YouTube per evitare code di analisi bloccate.

#### 2. 📱 Responsive Layout & Eliminazione Overflow
- **Barra Filtri Scorrevole:** Filtri Live racchiusi in una `QScrollArea` orizzontale a scorrimento fluido, prevenendo tagli di testo e sovrapposizioni su schermi piccoli o finestre ridimensionate.
- **Pulsante `[🧹 Svuota Vista]`:** Consente di ripulire immediatamente la tabella della Libreria a video senza toccare i file su disco né cancellare il database SQLite.

#### 3. 📂 Drag & Drop e Accesso Rapido
- **Drag & Drop Diretto su Tabella:** Rilascio diretto di file o intere cartelle audio sulla griglia della Libreria, con scansione ricorsiva automatica e caricamento istantaneo.
- **Accesso Rapido nel File Explorer:** Scorciatoie fisse per *Desktop*, *Documenti*, *Download* e *Musica* in cima alla colonna sinistra, con la sezione *Questo PC / Dischi* posizionata sotto.
- **Menu Contestuale con `[⚡ Analizza Tracce Selezionate]`:** Primo elemento in grassetto per avviare l'analisi audio e metadati esclusivamente sui brani evidenziati.

#### 4. 🏷️ Disaccoppiamento Completo di Mp3tag Workspace
- **Isolamento della Vista:** Rimossa la sincronizzazione automatica all'apertura del Tag Editor. La tabella di Mp3tag conserva i brani aperti senza interferenze.
- **Comandi di Caricamento Autonomi:** Pulsanti toolbar/menu `[➕ Aggiungi File...]`, `[📁 Aggiungi Cartella...]`, `[🧹 Svuota Elenco]` e Drag & Drop diretto su griglia.

#### 5. 🔑 Autenticazione OAuth2 & Servizi Online
- **Spotify:** Flusso standard con `response_type=code`, callback su porta `8888` e permessi di sincronizzazione playlist.
- **SoundCloud:** Modalità token di sessione per bypassare le limitazioni di registrazione per nuove app sviluppatori.
- **YouTube Data API v3:** Autenticazione diretta con Google Cloud API Key e test di validazione in tempo reale.

#### 6. 🎨 Cambio Tema a Caldo & FFmpeg Bundled
- **Switch Dinamico del Tema:** Transizione istantanea tra chiaro e scuro senza chiusura né riavvio della finestra Impostazioni.
- **FFmpeg Predefinito Bundled:** Rilevamento automatico di `bin/ffmpeg.exe` integrato nell'applicazione, con pulsante "Sfoglia..." opzionale.

---

### 📦 Asset Inclusi

| File | Piattaforma | Descrizione |
|---|---|---|
| `Musicat-Windows-Portable.zip` | Windows x64 | Versione portabile completa (FFmpeg pre-incluso, Qt6, libVLC, zero installazione) |
| `Musicat.exe` | Windows x64 | Eseguibile standalone 64-bit compilato per Windows |
| `Musicat-macOS.dmg` | macOS (Universal) | Immagine disco DMG con installazione drag & drop in Applicazioni |
| `Musicat-macOS-Portable.zip` | macOS (Universal) | Pacchetto portatile per macOS |
| `SHA256SUMS.txt` | Tutte | Checksum crittografici SHA-256 di integrità |
