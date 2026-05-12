# YouTube Watch Later → Appunti Markdown

Agente CLI che trasforma i video della tua lista "Watch Later" di YouTube in appunti Markdown strutturati, usando Claude per generare riassunti, punti chiave e note approfondite.

## Funzionalità

- Legge automaticamente la tua playlist Watch Later
- Scarica i trascritti automatici/manuali (italiano e inglese)
- Genera appunti in italiano con Claude (riassunto, punti chiave, momenti salienti)
- Salva file `.md` con frontmatter YAML (compatibili con Obsidian, Logseq, ecc.)
- Tiene traccia dei video già processati (nessuna duplicazione)

## Setup

### 1. Dipendenze Python

```bash
pip install -r requirements.txt
```

### 2. Chiave API Anthropic

```bash
cp .env.example .env
# Modifica .env e inserisci la tua ANTHROPIC_API_KEY
```

### 3. Credenziali Google/YouTube

1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuovo progetto (o usa uno esistente)
3. Abilita **YouTube Data API v3**: `API & Services → Library → YouTube Data API v3 → Enable`
4. Crea credenziali OAuth 2.0: `API & Services → Credentials → Create Credentials → OAuth client ID`
   - Application type: **Desktop app**
5. Scarica il JSON e salvalo come `client_secret.json` nella stessa cartella di `main.py`

Al primo avvio si aprirà il browser per autorizzare l'accesso al tuo account YouTube.  
Le credenziali vengono salvate in `token.json` per gli usi successivi.

## Utilizzo

```bash
# Processa tutti i nuovi video nella Watch Later
python main.py

# Processa al massimo 5 video
python main.py --limit 5

# Mostra i video nella Watch Later (con indicatore ✓ se già processati)
python main.py --list

# Mostra statistiche di elaborazione
python main.py --status

# Riprocessa un video specifico (sovrascrive la nota)
python main.py --reprocess dQw4w9WgXcQ
```

## Struttura degli appunti generati

```
notes/
├── 2026-05-12_come-funziona-il-cervello.md
├── 2026-05-12_introduzione-al-machine-learning.md
└── ...
```

Ogni file `.md` ha questo formato:

```markdown
---
title: "Titolo del video"
channel: "Nome del canale"
url: "https://www.youtube.com/watch?v=..."
video_id: "dQw4w9WgXcQ"
duration: "12:34"
published: "2024-01-15"
processed: "2026-05-12"
has_transcript: true
---

## Riassunto
...

## Punti Chiave
1. ...
2. ...

## Note
...

## Momenti Salienti
- [00:00] Introduzione
- [03:45] Concetto principale
...
```

## File generati

| File | Descrizione |
|------|-------------|
| `token.json` | Token OAuth Google (non condividere) |
| `client_secret.json` | Credenziali app Google (non condividere) |
| `processed_videos.json` | Stato dei video processati |
| `notes/` | Cartella con gli appunti Markdown |

Aggiungi `token.json` e `client_secret.json` al `.gitignore`.
