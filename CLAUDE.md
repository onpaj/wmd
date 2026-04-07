# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DAK is a self-hosted wall dashboard for Raspberry Pi (replacing DAKBoard), displaying photos, calendars, weather, and Home Assistant sensors on a wall-mounted TV via Chromium kiosk mode.

The project is **specification-driven** — see `tasks/prd-dak-dashboard.md` (user stories) and `docs/superpowers/specs/2026-04-07-dak-dashboard-design.md` (technical design) before implementing anything.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, uvicorn, httpx, icalendar, python-dateutil
- **Frontend:** TypeScript 5+, esbuild (no framework — vanilla TS with in-place DOM mutations)
- **Runtime:** Chromium `--kiosk` mode, systemd services
- **Target hardware:** Raspberry Pi, Ubuntu Server 22.04/24.04

## Commands

Once implemented, the expected commands are:

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 3000

# Frontend
npm install
npm run build    # esbuild src/app.ts --bundle --outfile=static/js/app.js
npm run watch    # development watch mode

# Deploy systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl enable dak-server dak-browser
sudo systemctl start dak-server dak-browser
```

## Architecture

```
systemd: dak-server (FastAPI :3000)
  ├── GET /api/data          → aggregated JSON (always <50ms, served from cache)
  ├── GET /api/photo/:id     → proxied iCloud photo (avoids CORS)
  └── static/                → compiled frontend bundle

systemd: dak-browser
  └── Chromium --kiosk http://localhost:3000
```

**Backend modules** (`sources/`): `icloud.py`, `calendar.py`, `weather.py`, `homeassistant.py`
**Cache** (`cache.py`): in-memory, per-source TTLs, stale-while-revalidate with background refresh tasks

**Frontend modules** (`src/modules/`): `photo.ts`, `calendar.ts`, `clock.ts`, `weather.ts`, `mini-calendar.ts`
- `src/app.ts` owns the 60-second polling loop
- All UI updates are in-place DOM mutations — no page reloads, no flicker
- `src/api.ts` wraps `GET /api/data`; `src/types.ts` holds shared interfaces

## Configuration

Runtime config lives in `config.json` (not committed). Structure:

```json
{
  "icloud": { "shareToken": "...", "photoIntervalSeconds": 30 },
  "calendars": [{ "name": "Family", "url": "https://...", "color": "#4CAF50" }],
  "weather": { "provider": "openmeteo", "latitude": 50.07, "longitude": 14.43 },
  "homeAssistant": { "url": "http://homeassistant.local:8123", "token": "...", "entities": [] },
  "display": { "calendarDaysAhead": 2, "weatherDays": 5 }
}
```

## Key Design Constraints

- **No external access** — fully local network, no cloud dependency beyond data source APIs
- **Flicker-free** — photo crossfade via CSS transitions, in-place DOM updates only
- **Always responsive** — `/api/data` must return from cache immediately; external fetches happen in background
- **Czech locale** — date/time formatting should use `cs-CZ`
- **Stable for 7+ days** — systemd `Restart=always` handles crashes; no manual intervention expected
