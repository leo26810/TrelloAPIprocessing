# AI Finder Suite

High-end Fullstack Webapp (Backend + Frontend) für einen KI-Finder.

## Features
- Prompt-Analyse: Ermittelt die besten KI-Apps auf Basis deiner Anfrage.
- Suche & Filter: Durchsuche die App-Datenbank nach Kategorie, Pricing und Popularity.
- SQLite Datenbank + JSON Seed.
- Modernes UI mit Tabs.

## Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Dann öffnen: `http://127.0.0.1:8000`
