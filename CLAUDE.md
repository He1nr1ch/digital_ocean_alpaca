# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Catalan Trading Dashboard — a Flask web app that displays real-time metrics for multiple Alpaca paper trading accounts. It serves a single-page dashboard that polls a JSON API every 30 seconds.

## Running the App

```bash
pip install -r requirements.txt
python app.py          # runs on port 8080 by default
```

**With Docker:**
```bash
docker build -t catalan-dashboard .
docker run -p 8080:8080 --env-file .env catalan-dashboard
```

Production uses Gunicorn (2 workers, 30s timeout) as configured in the Dockerfile.

## Environment Variables

Copy `.env.example` to `.env` and fill in Alpaca API credentials for each account:

| Variable | Account |
|---|---|
| `API_KEY` / `API_SECRET` | Heinrich |
| `API_KEY_VALYA` / `API_SECRET_VALYA` | Valya |
| `PORT` | Server port (default: 8080) |

Credentials are loaded server-side only and never exposed to the client.

## Architecture

**Backend (`app.py`):**
- `GET /` — serves `templates/index.html`
- `GET /api/accounts` — fetches live data from Alpaca for each configured account and returns JSON
- `fetch_account_data()` handles Alpaca API calls, calculates daily P&L (equity vs last equity), and counts positions by profit/loss state
- Accounts are configured in the `ACCOUNTS` dict; adding a new account requires adding credentials to env and an entry there

**Frontend (`templates/index.html`):**
- Self-contained single file with inline CSS and JS (no build step)
- Calls `/api/accounts` on load and every 30 seconds
- Renders account cards dynamically; handles per-account and global API errors independently