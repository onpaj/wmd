# DAK Dashboard — Design Spec

**Date:** 2026-04-07
**Status:** Approved

---

## Overview

A self-hosted DAKBoard-style wall dashboard running on a Raspberry Pi connected to a wall-mounted TV. Displays a rotating iCloud shared album photo, merged multi-calendar event list, clock, 5-day weather forecast, and a mini calendar. Optionally shows Home Assistant entity values. Runs entirely on the local network — no external access.

---

## Architecture

```
RPi Boot
 ├── systemd: dak-server.service  → Python/FastAPI (uvicorn) on :3000
 │     ├── GET /api/data          → aggregated JSON response
 │     ├── GET /api/photo/:id     → proxied iCloud photo (avoids CORS)
 │     └── serves static files   → compiled frontend
 └── systemd: dak-browser.service → Chromium --kiosk http://localhost:3000
```

### Backend (Python/FastAPI)

- `main.py` — FastAPI app, defines routes, wires up sources and cache
- `sources/icloud.py` — fetches iCloud shared album asset list via JSON feed
- `sources/calendar.py` — fetches and parses ICS URLs, merges multiple calendars
- `sources/weather.py` — abstract `WeatherProvider` interface with `OpenMeteoProvider` (default) and `AccuWeatherProvider` (optional)
- `sources/homeassistant.py` — calls HA REST API for configured entity states
- `cache.py` — in-memory cache with per-source TTLs

### Frontend (TypeScript + esbuild)

- `src/app.ts` — entry point, owns polling loop (every 60s), coordinates modules
- `src/api.ts` — single `fetchData()` wrapper around `GET /api/data`
- `src/types.ts` — shared TypeScript interfaces (`CalendarEvent`, `WeatherDay`, `Photo`, `HaEntity`, etc.)
- `src/modules/photo.ts` — crossfade rotation logic
- `src/modules/calendar.ts` — renders merged event list
- `src/modules/clock.ts` — local clock tick, no network
- `src/modules/weather.ts` — 5-day forecast rendering
- `src/modules/mini-calendar.ts` — month grid rendering

Each module exports a single `render(data: T, container: HTMLElement): void` function.

Compiled to `static/js/app.js` via esbuild (single bundle, no framework).

---

## Directory Layout

```
/home/pi/dak/
├── main.py
├── config.json
├── requirements.txt
├── package.json             # esbuild scripts only
├── sources/
│   ├── icloud.py
│   ├── calendar.py
│   ├── weather.py
│   └── homeassistant.py
├── cache.py
├── src/
│   ├── app.ts
│   ├── api.ts
│   ├── types.ts
│   └── modules/
│       ├── photo.ts
│       ├── calendar.ts
│       ├── clock.ts
│       ├── weather.ts
│       └── mini-calendar.ts
├── static/
│   ├── index.html
│   ├── js/
│   │   └── app.js           # compiled output
│   └── css/
│       ├── base.css
│       ├── photo.css
│       ├── calendar.css
│       ├── clock.css
│       ├── weather.css
│       └── mini-calendar.css
└── systemd/
    ├── dak-server.service
    └── dak-browser.service
```

---

## Layout

Landscape fullscreen (CSS grid, resolution-agnostic):

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                   PHOTO (top ~55% height)                   │
│              crossfades between iCloud photos               │
│                                                             │
├──────────────────────────────┬──────────────────────────────┤
│                              │   CLOCK (large, top right)   │
│   CALENDAR (scrolling,       ├──────────────────────────────┤
│   today + next N days,       │   WEATHER (5-day forecast,   │
│   color-coded per calendar)  │   icons + high/low + rain %) │
│                              ├──────────────────────────────┤
│                              │   MINI CALENDAR (month view) │
└──────────────────────────────┴──────────────────────────────┘
```

---

## Data Sources

### iCloud Shared Album
- POST to `https://p[xx]-sharedstreams.icloud.com/[token]/sharedstreams/webstream` to retrieve asset list
- Individual photos proxied via `/api/photo/:id` — browser never calls iCloud directly
- Cache TTL: 1 hour
- Rotation interval: configurable (`photoIntervalSeconds` in config)
- Rotation order: randomized
- Transition: CSS crossfade using two overlapping `<img>` elements (opacity transition ~1s), no blank frame

### Calendars
- Each source is an ICS URL (supports MS365, Google Calendar, iCloud Calendar)
- Parsed with `icalendar` Python library — handles recurring events and timezones
- Events merged and sorted across all calendars
- Each calendar assigned a color in config
- Display window: today + N days ahead (configurable, default 2)
- Cache TTL: 5 minutes

### Weather
- Abstract interface: `WeatherProvider` with `get_forecast() -> list[WeatherDay]`
- `OpenMeteoProvider`: default, no API key required, uses latitude/longitude
- `AccuWeatherProvider`: optional replacement, requires API key in config
- Switched via `"provider"` field in config
- Returns: date, normalized icon key (e.g. `"sunny"`, `"cloudy"`, `"rainy"`, `"snow"`, `"storm"`, `"fog"`), high temp, low temp, precipitation probability
- Backend normalizes provider-specific codes (WMO for Open-Meteo, AccuWeather icon IDs) to this common set before returning to the frontend
- Cache TTL: 30 minutes

### Home Assistant
- Calls `GET http://[ha-host]/api/states/[entity_id]` with a long-lived access token
- Configurable list of entities with display labels
- Cache TTL: 1 minute
- Display position: below the weather widget in the right column

---

## Config Structure

```json
{
  "icloud": {
    "shareToken": "abc123...",
    "photoIntervalSeconds": 30
  },
  "calendars": [
    { "name": "Family", "url": "https://...", "color": "#4CAF50" },
    { "name": "Work",   "url": "https://...", "color": "#F44336" },
    { "name": "Terka",  "url": "https://...", "color": "#2196F3" }
  ],
  "weather": {
    "provider": "openmeteo",
    "latitude": 50.07,
    "longitude": 14.43,
    "accuweatherApiKey": ""
  },
  "homeAssistant": {
    "url": "http://homeassistant.local:8123",
    "token": "...",
    "entities": [
      { "id": "sensor.living_room_temp", "label": "Obývák" }
    ]
  },
  "display": {
    "calendarDaysAhead": 2,
    "weatherDays": 5
  }
}
```

---

## Caching

In-memory cache (`cache.py`) with per-source TTLs. On startup, all sources are fetched eagerly. Background async tasks refresh each source on its TTL interval. The `/api/data` endpoint always returns from cache — never blocks on an external call.

If a source fails, the last successful value is returned (stale-while-revalidate).

---

## Deployment (RPi)

### Build (run once after FE changes)
```bash
npm run build   # esbuild src/app.ts --bundle --outfile=static/js/app.js
```

### systemd: dak-server.service
```ini
[Unit]
Description=DAK Dashboard Server
After=network.target

[Service]
WorkingDirectory=/home/pi/dak
ExecStart=/home/pi/dak/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 3000
Restart=always

[Install]
WantedBy=multi-user.target
```

### systemd: dak-browser.service
```ini
[Unit]
Description=DAK Dashboard Browser
After=dak-server.service graphical.target
Wants=graphical.target

[Service]
User=pi
Environment=DISPLAY=:0
ExecStartPre=/bin/sleep 3
ExecStart=chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --no-first-run --check-for-update-interval=31536000 \
  http://localhost:3000
Restart=always

[Install]
WantedBy=graphical.target
```

`unclutter` hides the mouse cursor after inactivity.

---

## No-Flicker Strategy

- Page loads once at boot, never reloads
- Data updates are in-place DOM mutations — only changed elements updated
- Clock ticks locally every second (no network)
- Photo crossfade: two `<img>` elements stacked, next photo preloads hidden, opacity transition on swap
- No `location.reload()` anywhere

---

## Frontend Build Scripts (package.json)

```json
{
  "scripts": {
    "build": "esbuild src/app.ts --bundle --outfile=static/js/app.js",
    "watch": "esbuild src/app.ts --bundle --outfile=static/js/app.js --watch"
  },
  "devDependencies": {
    "esbuild": "^0.20.0",
    "typescript": "^5.0.0"
  }
}
```
