# Musicat v1.2.1 — Audio Enhancer Overhaul, Versioning Display & Extended Genres

Release consolidata multi-piattaforma per **Musicat** con rifinitura grafica del modulo audio, sblocco dei controlli, glossario integrato e visualizzazione del numero di versione in tutta l'interfaccia.

---

### 🚀 Novità Principali in v1.2.1

#### 1. 🔊 Diagnosi & Normalizzazione Audio (Zero Strisce Grigie & Controlli Sempre Sbloccati)
- **Sfondo Bianco Puro:** Rimosse tutte le strisce o sfondi grigi alternati dalle righe di diagnosi (`QLabel` con sfondo trasparente su canvas bianco puro).
- **Selezione Uniforme delle Opzioni:** Tutte e tre le modalità (`ReplayGain Non Distruttivo`, `Normalizzazione Fisica Nuovo File`, `Sovrascrittura con Backup di Sicurezza`) sono card uniformi in `QButtonGroup`. Qualsiasi opzione selezionata si illumina in azzurro chiaro (`#e7f1ff`) con bordo blu scuro (`#0d6efd`) e testo in risalto.
- **Controlli Inferiori Sempre Sbloccati:** I selettori di **Preset Audio** (*DJ Club, Streaming, Anti-Clipping, Warm Analog, Vocal Clarity*), **Formato** (*MP3 320 kbps, FLAC, WAV*), slider **Volume Target (LUFS)** e **Limiter Headroom (dBTP)** rimangono sempre attivi, sbloccati e interattivi.
- **📖 Indice & Glossario Audio Integrato:**
  - Pulsante dedicato `[📖 Indice & Spiegazione Termini]` nell'intestazione.
  - Pulsanti rapidi inline `[ℹ️ Cos'è LUFS?]`, `[ℹ️ Cos'è True Peak?]` e `[ℹ️ Cos'è LRA?]` accanto a ciascun valore rilevato.
  - Card di riepilogo rapido visibile direttamente nella finestra con le specifiche tecniche (LUFS volume percepito, True Peak -1.0 dBTP headroom di sicurezza anti-clipping).

#### 2. 🏷️ Numero di Versione Visibile nelle Impostazioni e nel Titolo Finestra
- **Titolo Finestra Principale:** La barra del titolo mostra chiaramente `Musicat v1.2.1 — DJ Catalog & Smart Organizer`.
- **Finestra Impostazioni:** 
  - Titolo finestra aggiornato a `⚙️ Impostazioni — Musicat v1.2.1`.
  - Card informativa dedicata in fondo alla barra laterale sinistra con versione e tag di release ufficiale.
  - Badge visibile `Versione: v1.2.1` nella barra comandi inferiore.
  - Sezione *Aggiornamenti Software* con stato versione attuale installata.
  - Intestazione *Guida all'Uso* (Categoria 6) aggiornata a `v1.2.1`.

#### 3. 🔥 Top Charts & Discovery DJ Estesa
- **Nuove Categorie Generi Musicali:** Integrazione selettori per Latin & Reggaeton, Tech House / Techno, Afro House / Amapiano, Hip-Hop / Trap, R&B / Soul, Pop / Commerciale, Dance / EDM e Rock / Indie.
- **Risoluzione Percorsi File System:** Apertura in Esplora Risorse / Finder con il file già selezionato ed evidenziato via `explorer /select, <path>`.

---

### 📦 Asset Inclusi

| File | Piattaforma | Descrizione |
|---|---|---|
| `Musicat-Windows-Portable.zip` | Windows x64 | Versione completa portatile senza installazione (estraibile su USB/disco) |
| `Musicat.exe` | Windows x64 | Eseguibile standalone compilato |
| `Musicat-macOS.dmg` | macOS (Universal) | Immagine disco per installazione drag & drop in Applicazioni |
| `Musicat-macOS-Portable.zip` | macOS (Universal) | Bundle portatile per macOS |
| `SHA256SUMS.txt` | Tutti | Checksum crittografici SHA-256 di integrità |
