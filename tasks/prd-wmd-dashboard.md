# PRD: WMD Dashboard

## Introduction

WMD is a self-hosted wall dashboard running on a Raspberry Pi (Ubuntu Server) connected to a wall-mounted TV. It replaces DAKBoard with a fully custom, locally-hosted solution. The system displays a rotating iCloud shared album photo, a merged multi-calendar event list, a live clock, a 5-day weather forecast, a mini calendar, and Home Assistant entity values.

The backend is a Python/FastAPI server that fetches and caches all external data. The frontend is a TypeScript app compiled with esbuild — no framework, no page reloads, no flicker. Two systemd services manage the server and the Chromium kiosk browser. The whole system auto-starts on RPi boot.

---

## Goals

- Display a rotating photo slideshow from an iCloud shared album with smooth crossfade transitions
- Show merged calendar events from multiple ICS sources (MS365, Google, iCloud) color-coded per calendar
- Show a live clock (local, no network)
- Show a 5-day weather forecast using Open-Meteo (AccuWeather as a configurable alternative)
- Show a mini month calendar with today highlighted
- Show Home Assistant entity values (e.g. room temperature)
- All external data fetched server-side, cached, and served via a single `/api/data` endpoint
- Frontend never flickers — in-place DOM updates only
- Full-screen kiosk mode on TV startup, no borders, no cursor
- Auto-start on RPi reboot via systemd

---

## User Stories

### US-001: Project scaffold
**Description:** As a developer, I need a clean project structure with all config files in place so that development can start without setup friction.

**Acceptance Criteria:**
- [ ] Directory structure matches the spec: `sources/`, `src/modules/`, `static/css/`, `static/js/`, `systemd/`, `tasks/`, `docs/`
- [ ] `config.json` present with all keys from the spec (icloud, calendars, weather, homeAssistant, display) and placeholder values
- [ ] `requirements.txt` lists: `fastapi`, `uvicorn`, `httpx`, `icalendar`, `python-dateutil`
- [ ] `package.json` with `build` and `watch` scripts using esbuild
- [ ] `README.md` with setup instructions (install deps, build FE, run server)

---

### US-002: FastAPI backend skeleton
**Description:** As a developer, I need a running FastAPI app that serves the frontend and returns mock data from `/api/data` so that the frontend can be built against a stable contract.

**Acceptance Criteria:**
- [ ] `main.py` starts with `uvicorn main:app --port 3000`
- [ ] `GET /` serves `static/index.html`
- [ ] `GET /static/*` serves static files
- [ ] `GET /api/data` returns a hardcoded JSON response matching the full data shape (photos array, events array, weather array, ha_entities array, current datetime)
- [ ] All fields in the response are defined as Pydantic models
- [ ] Server starts without errors

---

### US-003: TypeScript frontend scaffold
**Description:** As a developer, I need a minimal HTML shell and TypeScript entry point so that frontend modules can be built incrementally.

**Acceptance Criteria:**
- [ ] `static/index.html` defines the CSS grid layout with named regions: `photo`, `calendar`, `clock`, `weather`, `mini-calendar`
- [ ] `src/types.ts` defines interfaces: `DashboardData`, `CalendarEvent`, `WeatherDay`, `Photo`, `HaEntity`
- [ ] `src/api.ts` exports `fetchData(): Promise<DashboardData>` that calls `GET /api/data`
- [ ] `src/app.ts` imports all modules, calls `fetchData()` on load and every 60 seconds, passes data to each module's `render()` function
- [ ] `npm run build` produces `static/js/app.js` without errors
- [ ] `static/css/base.css` sets full-screen dark background, CSS grid layout matching the spec wireframe, no scrollbars, no margins

---

### US-004: Clock module
**Description:** As a user, I want to see the current time updating every second so that the dashboard always shows the correct time.

**Acceptance Criteria:**
- [ ] `src/modules/clock.ts` exports `startClock(container: HTMLElement): void`
- [ ] Displays current time in `HH:MM` format, large font
- [ ] Updates every second using `setInterval` — no network call
- [ ] Typecheck passes

---

### US-005: Photo module
**Description:** As a user, I want the photo area to smoothly rotate through family photos so that the dashboard feels alive.

**Acceptance Criteria:**
- [ ] `src/modules/photo.ts` exports `render(data: Photo[], container: HTMLElement): void`
- [ ] Two `<img>` elements stacked via CSS; one visible, one preloading
- [ ] On each rotation: preloads next image, then CSS opacity crossfade (~1s transition)
- [ ] Rotation interval is passed from `DashboardData` (from config)
- [ ] No blank frame visible during transition
- [ ] `static/css/photo.css` styles the photo area to fill its grid region, `object-fit: cover`
- [ ] Typecheck passes

---

### US-006: Calendar module
**Description:** As a user, I want to see today's and upcoming events in a scrolling list so that I can plan my day at a glance.

**Acceptance Criteria:**
- [ ] `src/modules/calendar.ts` exports `render(data: CalendarEvent[], container: HTMLElement): void`
- [ ] Groups events by date with a date header (day number + label e.g. "07 dnes", "08 zítra")
- [ ] Each event shows: colored left border (calendar color), time range, event title
- [ ] All-day events shown at top of their day group with "celý den" label
- [ ] Events are pre-sorted and pre-filtered by the backend; frontend just renders
- [ ] `static/css/calendar.css` styles the list; dark background, readable font
- [ ] Typecheck passes

---

### US-007: Weather module
**Description:** As a user, I want to see a 5-day weather forecast so that I can plan the week ahead.

**Acceptance Criteria:**
- [ ] `src/modules/weather.ts` exports `render(data: WeatherDay[], container: HTMLElement): void`
- [ ] Shows each day: abbreviated day name, weather icon (emoji or inline SVG mapped from normalized icon key), high temp, low temp, precipitation %
- [ ] Normalized icon keys: `sunny`, `partly-cloudy`, `cloudy`, `rainy`, `heavy-rain`, `snow`, `storm`, `fog`
- [ ] `static/css/weather.css` styles the forecast row
- [ ] Typecheck passes

---

### US-008: Mini calendar module
**Description:** As a user, I want to see the current month as a grid so that I can orient myself in the week and month.

**Acceptance Criteria:**
- [ ] `src/modules/mini-calendar.ts` exports `render(container: HTMLElement): void` (no external data needed — uses current date)
- [ ] Shows abbreviated weekday headers (po, út, st, čt, pá, so, ne — Czech locale)
- [ ] Today's date is highlighted
- [ ] Days with events (from `CalendarEvent[]`) are marked with a colored dot — update signature to `render(events: CalendarEvent[], container: HTMLElement): void`
- [ ] `static/css/mini-calendar.css` styles the grid compactly
- [ ] Typecheck passes

---

### US-009: iCloud photos source
**Description:** As a developer, I need the backend to fetch and cache photos from an iCloud shared album so that the frontend can display them.

**Acceptance Criteria:**
- [ ] `sources/icloud.py` exports `async def get_photos(config) -> list[Photo]`
- [ ] POSTs to `https://p[xx]-sharedstreams.icloud.com/{token}/sharedstreams/webstream` to retrieve asset list
- [ ] Follows up with a second POST to `webasseturls` to get download URLs
- [ ] Returns list of `Photo` objects with `id` and `url` fields
- [ ] `GET /api/photo/{photo_id}` in `main.py` proxies the image bytes to the browser (avoids CORS)
- [ ] Photo list cached for 1 hour
- [ ] If fetch fails, last successful list returned

---

### US-010: Calendar source
**Description:** As a developer, I need the backend to fetch, parse, and merge ICS calendar feeds so that the frontend receives a unified event list.

**Acceptance Criteria:**
- [ ] `sources/calendar.py` exports `async def get_events(config) -> list[CalendarEvent]`
- [ ] Fetches each ICS URL from config concurrently using `httpx`
- [ ] Parses with `icalendar` library — handles `VEVENT`, recurring events (`RRULE`), and timezones
- [ ] Each event includes: `id`, `title`, `start`, `end`, `all_day`, `calendar_name`, `color`
- [ ] Events filtered to today + `calendarDaysAhead` days (from config)
- [ ] Result sorted by start time, all-day events first within each day
- [ ] Cached for 5 minutes; stale data returned on fetch failure

---

### US-011: Weather source
**Description:** As a developer, I need the backend to fetch weather forecasts via an abstracted provider interface so that Open-Meteo and AccuWeather are interchangeable.

**Acceptance Criteria:**
- [ ] `sources/weather.py` defines abstract base class `WeatherProvider` with `async def get_forecast(config) -> list[WeatherDay]`
- [ ] `OpenMeteoProvider` calls `https://api.open-meteo.com/v1/forecast` with lat/lon, returns 5-day forecast, no API key required
- [ ] `AccuWeatherProvider` calls AccuWeather API using `accuweatherApiKey` from config
- [ ] Both providers normalize output to: `date`, `icon` (normalized key), `temp_high`, `temp_low`, `precip_percent`
- [ ] WMO weather codes (Open-Meteo) mapped to normalized icon keys in a lookup table
- [ ] Active provider selected by `config.weather.provider` field (`"openmeteo"` or `"accuweather"`)
- [ ] Cached for 30 minutes

---

### US-012: Home Assistant source
**Description:** As a developer, I need the backend to fetch configured HA entity states so that the frontend can display sensor values.

**Acceptance Criteria:**
- [ ] `sources/homeassistant.py` exports `async def get_entities(config) -> list[HaEntity]`
- [ ] Calls `GET {ha_url}/api/states/{entity_id}` with `Authorization: Bearer {token}` header for each configured entity
- [ ] Returns list of `HaEntity` objects: `id`, `label`, `state`, `unit`
- [ ] Fetches all entities concurrently
- [ ] Cached for 1 minute
- [ ] If HA is unreachable, returns last known values (or empty list on first failure)

---

### US-013: Caching layer
**Description:** As a developer, I need a centralized cache with per-source TTLs and background refresh so that `/api/data` never blocks on an external API call.

**Acceptance Criteria:**
- [ ] `cache.py` provides `Cache` class with `get(key)`, `set(key, value, ttl_seconds)`, `is_expired(key)` methods
- [ ] On server startup, all sources fetched eagerly before first request is served
- [ ] Background `asyncio` tasks refresh each source on its TTL interval independently
- [ ] `/api/data` always reads from cache — zero external calls on the hot path
- [ ] If a background refresh fails, the previous cached value is kept (stale-while-revalidate)
- [ ] Cache is in-memory only (no Redis, no disk)

---

### US-014: `/api/data` endpoint integration
**Description:** As a developer, I need the `/api/data` endpoint to return real data from all sources so that the frontend displays live information.

**Acceptance Criteria:**
- [ ] `GET /api/data` returns JSON with: `photos`, `events`, `weather`, `ha_entities`, `photo_interval_seconds`, `server_time`
- [ ] All fields populated from cached source data
- [ ] Response matches the Pydantic models defined in US-002
- [ ] Endpoint responds in under 50ms (always from cache)
- [ ] Tested with `curl` returning valid JSON with real data from each source

---

### US-015: systemd services
**Description:** As a developer, I need systemd service files so that both the server and the browser start automatically on RPi boot.

**Acceptance Criteria:**
- [ ] `systemd/wmd-server.service` starts uvicorn using the project's `.venv`, restarts on failure, runs after `network.target`
- [ ] `systemd/wmd-browser.service` starts Chromium in `--kiosk` mode at `http://localhost:3000`, runs as user `pi` (or configured user), depends on `wmd-server.service` with a 3s pre-start delay
- [ ] Chromium flags: `--kiosk --noerrdialogs --disable-infobars --no-first-run --check-for-update-interval=31536000`
- [ ] `DISPLAY=:0` set in browser service environment
- [ ] Both services have `WantedBy` set correctly (`multi-user.target` for server, `graphical.target` for browser)
- [ ] `README.md` includes install commands: `sudo cp systemd/*.service /etc/systemd/system/ && sudo systemctl enable wmd-server wmd-browser`

---

### US-016: RPi Ubuntu Server deployment guide
**Description:** As a developer, I need a complete setup guide for Ubuntu Server on RPi so that the dashboard can be deployed from scratch reliably.

**Acceptance Criteria:**
- [ ] `README.md` covers: install Python deps (`python3 -m venv .venv && pip install -r requirements.txt`), install Node.js (for esbuild build step), build frontend (`npm install && npm run build`), install `unclutter` for cursor hiding, enable systemd services
- [ ] Guide notes that a desktop environment (or at minimum `xorg`) must be installed for Chromium kiosk to work on Ubuntu Server
- [ ] Guide includes how to set up auto-login for the display user
- [ ] Guide covers how to update ICS URLs and other config without restarting the service

---

## Functional Requirements

- FR-1: `GET /api/data` returns all dashboard data from in-memory cache; response time < 50ms
- FR-2: `GET /api/photo/{id}` proxies iCloud photo bytes server-side; browser never calls iCloud directly
- FR-3: iCloud photo list refreshed every 60 minutes; photos rotate in the frontend every `photoIntervalSeconds` seconds with a CSS crossfade
- FR-4: ICS calendar feeds fetched concurrently every 5 minutes; recurring events expanded; events filtered to today + N days
- FR-5: Weather forecast refreshed every 30 minutes; provider switchable via config; backend normalizes icon codes to a fixed set
- FR-6: Home Assistant entities fetched every 60 seconds; stale data served on HA unavailability
- FR-7: Frontend polls `/api/data` every 60 seconds; all updates are in-place DOM mutations; no page reload ever
- FR-8: Clock ticks every second using `setInterval`; no network call
- FR-9: Chromium runs in `--kiosk` mode fullscreen; `unclutter` hides the cursor
- FR-10: Both systemd services start on boot and restart on failure

---

## Non-Goals

- No user authentication or access control
- No external access / port forwarding / HTTPS
- No write access to calendars (read-only ICS feeds only)
- No push notifications or alerts
- No mobile responsive layout (landscape TV only)
- No PWA / offline mode
- No admin UI for config editing (edit `config.json` directly)
- No multi-dashboard support
- No DAKBoard migration tool

---

## Technical Considerations

- **Python version:** 3.11+ (available on Ubuntu 22.04/24.04)
- **Node.js:** Required only for the esbuild build step; not present at runtime
- **iCloud API:** Undocumented private API; uses a two-step POST flow (webstream → webAssetURLs). May require handling `X-Apple-MMe-Host` redirect headers.
- **Recurring calendar events:** Use `python-dateutil`'s `rrule` for RRULE expansion within the display window
- **Weather icons:** Map WMO codes to normalized keys using a static dict in `OpenMeteoProvider`; AccuWeather uses its own icon IDs mapped separately
- **Crossfade:** Two `<img>` elements in the photo container; CSS `transition: opacity 1s`; swap via JS class toggle
- **esbuild bundle:** Single output file `static/js/app.js`; no source maps needed in production
- **RPi Ubuntu Server:** Requires installing `xorg`, a display manager, and Chromium separately; `pi` user may be named differently on Ubuntu (use `ubuntu` or configure in systemd service)

---

## Success Metrics

- Dashboard is visible and updating within 10 seconds of RPi boot
- All four data sources (photos, calendars, weather, HA) display real data
- No visible flicker or blank frames during photo transitions or data refreshes
- System runs stably for 7+ days without manual intervention
- Adding a new calendar requires only editing `config.json` (no code changes)

---

## Confirmed Decisions

- Mini calendar shows event dots per day from all configured calendars
- All day/month labels use Czech locale (dnes, zítra, po/út/st/čt/pá/so/ne)
- Home Assistant widget is hidden entirely when `ha_entities` is empty in config
