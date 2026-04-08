# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WMD is a self-hosted wall dashboard for Raspberry Pi (replacing DAKBoard), displaying photos, calendars, weather, and Home Assistant sensors on a wall-mounted TV via Chromium kiosk mode.

The project is **specification-driven** — see `tasks/prd-wmd-dashboard.md` (user stories) and `docs/superpowers/specs/2026-04-07-wmd-dashboard-design.md` (technical design) before implementing anything.

For deployment instructions, see `DEPLOY.md`.

## Wall Mount Display (WMD) Access

SSH into the Raspberry Pi with: `ssh -i ~/.ssh/id_ed25519_rpi rem@192.168.10.66`

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, uvicorn, httpx, icalendar, python-dateutil
- **Frontend:** TypeScript 5+, esbuild (no framework — vanilla TS with in-place DOM mutations)
- **Runtime:** Chromium `--kiosk` mode, systemd services
- **Target hardware:** Raspberry Pi, Ubuntu Server 22.04/24.04

## Commands

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 3000

# Frontend
npm install
npm run build    # esbuild src/app.ts --bundle --outfile=static/js/app.js
npm run watch    # development watch mode

# Tests
pytest

# Deploy systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl enable wmd-server wmd-browser
sudo systemctl start wmd-server wmd-browser
```

## Architecture

```
systemd: wmd-server (FastAPI :3000)
  ├── GET /api/data          → aggregated JSON (always <50ms, served from cache)
  ├── GET /api/photo/:id     → proxied iCloud photo (avoids CORS)
  └── static/                → compiled frontend bundle

systemd: wmd-browser
  └── Chromium --kiosk http://localhost:3000
```

**Backend modules** (`sources/`): `icloud.py`, `calendar.py`, `weather.py`, `homeassistant.py`, `ms365.py`
**Cache** (`cache.py`): in-memory, per-source TTLs, stale-while-revalidate with background refresh tasks

| Source | Module | TTL |
|--------|--------|-----|
| iCloud photos | `sources/icloud.py` | 1 hour |
| ICS calendars | `sources/calendar.py` | 5 min |
| Mini-calendar feed | `sources/calendar.py` | 1 hour |
| Weather forecast | `sources/weather.py` | 30 min |
| Home Assistant entities | `sources/homeassistant.py` | 1 min |
| HA meal sensors | `sources/homeassistant.py` | 5 min |
| HA outdoor temperature | `sources/homeassistant.py` | 1 min |
| MS365 calendars | `sources/ms365.py` | 5 min |

**Frontend modules** (`src/modules/`): `photo.ts`, `calendar.ts`, `clock.ts`, `weather.ts`, `mini-calendar.ts`
- `src/app.ts` owns the 60-second polling loop
- All UI updates are in-place DOM mutations — no page reloads, no flicker
- `src/api.ts` wraps `GET /api/data`; `src/types.ts` holds shared interfaces

## Implemented Features

### Photo Slideshow
- Fetches photos from an iCloud shared album via Apple's API
- Cross-fade transitions between photos (CSS, no flicker)
- Configurable interval (`photoIntervalSeconds`)
- Photos served via `/api/photo/:id` proxy to avoid CORS

### Calendar
- Parses ICS feeds (iCloud, Google Calendar, Outlook, any RFC 5545 source)
- Supports recurring events with RRULE and EXDATE exclusions
- Multiple calendars with color-coded borders (gradient for overlapping events)
- Czech locale: "dnes" / "zítra" day labels; "celý den" for all-day events
- Shows N days ahead (configurable via `calendarDaysAhead`)
- Microsoft 365 calendar integration via OAuth2 client credentials (Graph API)

### Mini Calendar
- 3-week grid (Monday-first), highlights today
- Up to 3 event color bars per day
- Separate ICS feed (`miniCalendar.url`)

### Weather Forecast
- 5-day forecast (configurable via `weatherDays`)
- Three provider options:
  - **MET.no** (free, no API key, recommended)
  - **OpenMeteo** (free, no API key)
  - **AccuWeather** (requires API key)
- Emoji weather icons mapped from WMO weather codes
- High/low temperature, precipitation probability
- Czech weekday labels

### Clock & Meals
- Live clock updating every second
- Outdoor temperature from Home Assistant sensor
- Meal display (soup + lunch) for today/tomorrow from HA entities
- Switches to tomorrow's meals after 12:30

### Home Assistant Integration
- Fetches arbitrary entity states via REST API
- Dedicated support for meal sensors (soup today/tomorrow, lunch today/tomorrow)
- Outdoor temperature sensor
- Concurrent entity fetching; errors are non-fatal

## Configuration

Runtime config lives in `config.json` (not committed — copy from `config.example.json`). Full structure:

```json
{
  "icloud": {
    "shareToken": "...",
    "photoIntervalSeconds": 30
  },
  "calendars": [
    { "name": "Family", "url": "https://...", "color": "#4CAF50", "excludePatterns": [] }
  ],
  "weather": {
    "provider": "metno",
    "latitude": 50.07,
    "longitude": 14.43,
    "accuweatherApiKey": ""
  },
  "homeAssistant": {
    "url": "http://homeassistant.local:8123",
    "token": "...",
    "entities": [{ "id": "sensor.foo", "label": "Foo" }],
    "soupTodayEntityId": "sensor.soup_today",
    "soupTomorrowEntityId": "sensor.soup_tomorrow",
    "lunchTodayEntityId": "sensor.lunch_today",
    "lunchTomorrowEntityId": "sensor.lunch_tomorrow",
    "outsideTemperature": "sensor.outside_temp"
  },
  "display": {
    "calendarDaysAhead": 2,
    "weatherDays": 5
  },
  "ms365": {
    "tenantId": "...",
    "clientId": "...",
    "clientSecret": "...",
    "users": [
      { "email": "user@example.com", "name": "User", "color": "#4CAF50" }
    ]
  },
  "miniCalendar": {
    "url": "https://...",
    "color": "#888888"
  }
}
```

All top-level keys except `icloud`, `calendars`, `weather`, `homeAssistant`, and `display` are optional.

## Deploy Routine

After every commit, always run these three steps in order:

```bash
git push
./update.sh
```

This pushes to GitHub and then pulls + rebuilds + restarts the service on the Raspberry Pi. Never skip the device update after a commit.

## Key Design Constraints

- **No external access** — fully local network, no cloud dependency beyond data source APIs
- **Flicker-free** — photo crossfade via CSS transitions, in-place DOM updates only
- **Always responsive** — `/api/data` must return from cache immediately; external fetches happen in background
- **Czech locale** — date/time formatting should use `cs-CZ`
- **Stable for 7+ days** — systemd `Restart=always` handles crashes; no manual intervention expected
