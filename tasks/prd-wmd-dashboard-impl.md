# PRD: WMD Dashboard — Implementation Stories

## Introduction

WMD is a self-hosted wall dashboard for a Raspberry Pi (Ubuntu Server) connected to a wall-mounted TV. It displays a rotating iCloud shared album photo, merged multi-calendar events, a live clock, a 5-day weather forecast, a mini month calendar, and optional Home Assistant sensor values. The backend is Python/FastAPI; the frontend is TypeScript compiled with esbuild running in Chromium kiosk mode. All data is cached server-side; the frontend never blocks on external API calls and never flickers.

This PRD translates the implementation plan into 18 executable user stories, each scoped to one focused session.

---

## Goals

- Greenfield project runnable end-to-end on RPi Ubuntu Server within one implementation cycle
- All four data sources (photos, calendars, weather, HA) return real data via `/api/data`
- Frontend displays all widgets with no flicker, no page reload, no blank frames during photo transitions
- System auto-starts on RPi boot and recovers from crashes via systemd
- Config changes (ICS URLs, tokens, coordinates) require only editing `config.json`, no code changes

---

## User Stories

---

### US-001: Project Scaffold
**Description:** As a developer, I need a clean project structure with all config files so that the rest of the implementation can proceed without setup friction.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] The following directories exist: `sources/`, `tests/`, `src/modules/`, `static/js/`, `static/css/`, `systemd/`, `docs/superpowers/plans/`, `docs/superpowers/specs/`, `tasks/`
- [ ] `sources/__init__.py` exists (empty)
- [ ] `requirements.txt` contains pinned versions: `fastapi==0.111.0`, `uvicorn[standard]==0.29.0`, `httpx==0.27.0`, `icalendar==5.0.12`, `python-dateutil==2.9.0`, `respx==0.21.1`, `pytest==8.2.0`, `pytest-asyncio==0.23.7`
- [ ] `package.json` has `build` script: `esbuild src/app.ts --bundle --outfile=static/js/app.js --minify` and `watch` script with `--watch` flag
- [ ] `package.json` has `devDependencies` for `esbuild ^0.20.0` and `typescript ^5.4.0`
- [ ] `tsconfig.json` exists with `target: ES2020`, `strict: true`, `noEmit: true`, `lib: ["ES2020", "DOM"]`
- [ ] `config.example.json` exists with all required keys: `icloud.shareToken`, `icloud.photoIntervalSeconds`, `calendars[]` (name/url/color), `weather` (provider/latitude/longitude/accuweatherApiKey), `homeAssistant` (url/token/entities[]), `display` (calendarDaysAhead/weatherDays)
- [ ] `config.json` exists (copied from example) and is listed in `.gitignore`
- [ ] `.gitignore` also excludes `.venv/`, `__pycache__/`, `*.pyc`, `node_modules/`, `static/js/app.js`
- [ ] Python venv created at `.venv/` and all requirements installed: `pip install -r requirements.txt` exits 0
- [ ] Node deps installed: `npm install` exits 0
- [ ] Git repository initialized with initial commit containing all scaffold files (excluding gitignored ones)

---

### US-002: Pydantic Response Models
**Description:** As a developer, I need typed Pydantic models for all API response shapes so that the FastAPI endpoint is type-safe and the frontend contract is explicit.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `models.py` exists with the following classes (all inheriting `BaseModel`):
  - `Photo`: fields `id: str`, `url: str`
  - `CalendarEvent`: fields `id: str`, `title: str`, `start: datetime`, `end: datetime`, `all_day: bool`, `calendar_name: str`, `color: str`
  - `WeatherDay`: fields `date: str`, `icon: str`, `temp_high: float`, `temp_low: float`, `precip_percent: int`
  - `HaEntity`: fields `id: str`, `label: str`, `state: str`, `unit: str`
  - `DashboardData`: fields `photos: list[Photo]`, `events: list[CalendarEvent]`, `weather: list[WeatherDay]`, `ha_entities: list[HaEntity]`, `photo_interval_seconds: int`, `server_time: datetime`
- [ ] Running `python3 -c "from models import DashboardData; print('models OK')"` prints `models OK` with no errors
- [ ] All imports (`from pydantic import BaseModel`, `from datetime import datetime`) are present
- [ ] Committed to git with message `feat: add Pydantic response models`

---

### US-003: Config Loading
**Description:** As a developer, I need a typed config loader that reads `config.json` and exposes all values as Python dataclasses so that all sources access config via typed attributes, not raw dict keys.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `config.py` contains dataclasses: `ICloudConfig`, `CalendarConfig`, `WeatherConfig`, `HaEntityConfig`, `HomeAssistantConfig`, `DisplayConfig`, `AppConfig`
- [ ] `ICloudConfig` has `share_token: str` and `photo_interval_seconds: int` (note: snake_case mapping from JSON camelCase)
- [ ] `WeatherConfig` has `provider: str`, `latitude: float`, `longitude: float`, `accuweather_api_key: str`
- [ ] `HomeAssistantConfig` has `url: str`, `token: str`, `entities: list[HaEntityConfig]`
- [ ] `DisplayConfig` has `calendar_days_ahead: int` and `weather_days: int`
- [ ] `load_config(path: str = "config.json") -> AppConfig` function exists
- [ ] `load_config` maps JSON camelCase keys to snake_case dataclass fields (e.g. `shareToken` → `share_token`, `calendarDaysAhead` → `calendar_days_ahead`)
- [ ] `tests/test_config.py` exists with test `test_load_config_returns_typed_object` that writes a temp config JSON and asserts field values
- [ ] `tests/conftest.py` exists with `sample_config` fixture that writes a full config JSON to `tmp_path` and returns the path as string
- [ ] `pytest tests/test_config.py -v` passes (1 test)
- [ ] Committed to git with message `feat: add config loader`

---

### US-004: In-Memory TTL Cache
**Description:** As a developer, I need a simple in-memory cache with per-key TTLs and stale-value fallback so that `/api/data` never blocks on an external API call.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `cache.py` contains `Cache` class with:
  - `set(key: str, value: Any, ttl_seconds: int) -> None`
  - `get(key: str, return_stale: bool = False) -> Any` — returns `None` for missing keys; returns `None` for expired keys unless `return_stale=True`; returns value for valid (non-expired) keys
  - `is_expired(key: str) -> bool` — returns `True` for missing or expired keys
- [ ] Internal storage uses `dict[str, tuple[Any, float]]` mapping key to `(value, expires_at)` using `time.monotonic()`
- [ ] `tests/test_cache.py` contains 5 tests:
  - `test_set_and_get` — set with TTL=60, get returns value
  - `test_get_missing_returns_none` — get on non-existent key returns None
  - `test_expired_returns_none` — set with TTL=0, sleep 10ms, get returns None
  - `test_stale_returns_last_value_when_flagged` — set with TTL=0, sleep 10ms, get with `return_stale=True` returns the old value
  - `test_overwrite` — set same key twice, get returns second value
- [ ] `pytest tests/test_cache.py -v` passes (5 tests)
- [ ] Committed to git with message `feat: in-memory TTL cache`

---

### US-005: FastAPI Skeleton with Mock `/api/data`
**Description:** As a developer, I need a running FastAPI server that serves `static/index.html` and returns a valid (but empty) `/api/data` response so that the frontend can be developed against a stable contract before real data sources are wired.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `main.py` has a `create_app(config_path: str = "config.json") -> FastAPI` factory function
- [ ] `main.py` has a module-level `app = create_app()` for uvicorn
- [ ] `GET /api/data` returns HTTP 200 with JSON body matching `DashboardData` schema: `photos: []`, `events: []`, `weather: []`, `ha_entities: []`, `photo_interval_seconds: <from config>`, `server_time: <utc ISO string>`
- [ ] `GET /` and any unknown path (`/{full_path:path}`) serves `static/index.html`
- [ ] CSS served at `/static/css/*` and JS at `/static/js/*` via `StaticFiles` mount
- [ ] `pytest.ini` exists with `[pytest]` section and `asyncio_mode = auto`
- [ ] `tests/test_api.py` has:
  - `test_api_data_returns_200` — async test using `httpx.AsyncClient(transport=ASGITransport(app=app))` asserting status 200 and all required keys present
  - `test_static_index_served` — asserts `GET /` returns 200
- [ ] `static/index.html` exists (minimal placeholder, to be replaced in US-011)
- [ ] `pytest tests/test_api.py -v` passes (2 tests)
- [ ] `python3 main.py &; curl http://localhost:3000/api/data` returns valid JSON; server killed after test
- [ ] Committed to git with message `feat: FastAPI skeleton with mock /api/data`

---

### US-006: iCloud Shared Album Photo Source
**Description:** As a developer, I need the backend to fetch the list of photos from an iCloud shared album and expose a proxy endpoint so that the frontend can display photos without CORS issues.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `sources/icloud.py` has `async def get_photos(cfg: AppConfig) -> list[Photo]`
- [ ] `get_photos` performs two-step iCloud API call:
  1. POST `{"streamCtag": None}` to `https://p00-sharedstreams.icloud.com/{token}/sharedstreams/webstream` with `Content-Type: application/json`
  2. If response has `X-Apple-MMe-Host` header, repeat step 1 using that host
  3. POST photo guids to `.../webasseturls` to get download URLs
- [ ] Returns `list[Photo]` where each `Photo.url` is `/api/photo/{guid}` (not the raw iCloud URL)
- [ ] Module-level `_photo_url_map: dict[str, str]` stores guid → real iCloud URL; populated on each `get_photos` call
- [ ] `get_photo_url(photo_id: str) -> str | None` function exported from module
- [ ] `main.py` `GET /api/photo/{photo_id}` endpoint uses `get_photo_url` and proxies the image bytes via `StreamingResponse` with correct `content-type`; returns HTTP 404 if guid unknown
- [ ] `tests/test_icloud.py` has:
  - `test_get_photos_returns_photo_list` — mocks both iCloud POSTs with `respx`, asserts 2 photos returned, `Photo.id == "guid1"`, `Photo.url == "/api/photo/guid1"`
  - `test_get_photos_handles_empty_album` — mocks empty responses, asserts empty list returned
- [ ] `pytest tests/test_icloud.py -v` passes (2 tests)
- [ ] Committed to git with message `feat: iCloud shared album photo source`

---

### US-007: Calendar ICS Source with Recurring Events
**Description:** As a developer, I need the backend to fetch multiple ICS calendar feeds concurrently, parse events (including recurring ones), merge them into a single sorted list, and assign colors so that the frontend displays a unified multi-calendar view.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `sources/calendar.py` has `async def get_events(cfg: AppConfig) -> list[CalendarEvent]`
- [ ] Fetches all ICS URLs concurrently using `httpx.AsyncClient` (not sequentially)
- [ ] Parses events with `icalendar.Calendar.from_ical()`; processes only `VEVENT` components
- [ ] All-day events detected by checking if `DTSTART.dt` is `datetime.date` (not `datetime.datetime`); `CalendarEvent.all_day = True`
- [ ] Recurring events (those with `RRULE` property) expanded using `dateutil.rrule.rrulestr`; `EXDATE` exclusions applied
- [ ] Events filtered to window: `today 00:00:00 UTC` through `today + calendarDaysAhead + 1 days`
- [ ] Result sorted: primary key = `event.start.date()`, secondary key = `not event.all_day` (all-day first within each day), tertiary key = `event.start`
- [ ] Each event `color` assigned from `CalendarConfig.color` of the matching calendar
- [ ] If any ICS fetch fails (network error, non-200, parse error), that calendar is silently skipped
- [ ] `tests/fixtures/simple.ics` exists with one timed event (`Trh Dka`) and one all-day event (`Celodení akce`)
- [ ] `tests/fixtures/recurring.ics` exists with a daily recurring `Standup` event
- [ ] `tests/test_calendar.py` has 4 tests (all using `@respx.mock`):
  - `test_parses_simple_events` — asserts `"Trh Dka"` in event titles
  - `test_all_day_events_flagged` — asserts `Celodení akce` has `all_day == True`
  - `test_recurring_events_expanded` — asserts at least 1 `Standup` occurrence in window
  - `test_calendar_color_assigned` — asserts Family calendar events have `color == "#4CAF50"`
- [ ] `pytest tests/test_calendar.py -v` passes (4 tests)
- [ ] Committed to git with message `feat: ICS calendar source with recurring event support`

---

### US-008: Weather Source with Open-Meteo and AccuWeather
**Description:** As a developer, I need a weather provider abstraction with Open-Meteo as the default (no API key) and AccuWeather as an optional alternative so that the weather widget always shows normalized forecast data regardless of provider.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `sources/weather.py` defines:
  - `ICON_KEYS: dict[int, str]` — mapping WMO weather codes to normalized icon keys. Must include: `0→sunny`, `1→sunny`, `2→partly-cloudy`, `3→cloudy`, `45→fog`, `48→fog`, `51-57→rainy`, `61-65→rainy/heavy-rain`, `66-67→rainy/heavy-rain`, `71-77→snow`, `80-82→rainy/heavy-rain`, `85-86→snow`, `95→storm`, `96→storm`, `99→storm`
  - `WeatherProvider` abstract base class with `async def get_forecast(cfg: AppConfig) -> list[WeatherDay]`
  - `OpenMeteoProvider(WeatherProvider)` — calls `https://api.open-meteo.com/v1/forecast` with params: `latitude`, `longitude`, `daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max`, `timezone=auto`, `forecast_days=cfg.display.weather_days`
  - `AccuWeatherProvider(WeatherProvider)` — two-step: get location key via geoposition search, then fetch 5-day daily forecast
  - `async def get_forecast(cfg: AppConfig) -> list[WeatherDay]` — dispatches to correct provider based on `cfg.weather.provider` (`"openmeteo"` or `"accuweather"`)
- [ ] Both providers return `WeatherDay` with fields: `date` (YYYY-MM-DD), `icon` (normalized key), `temp_high`, `temp_low`, `precip_percent`
- [ ] AccuWeather icon IDs mapped to normalized keys via `_AW_ICON_KEYS` dict (IDs 1-44 covered)
- [ ] `tests/test_weather.py` has 4 tests (using `@respx.mock`):
  - `test_openmeteo_returns_5_days` — mocks Open-Meteo response, asserts 5 `WeatherDay` objects returned
  - `test_openmeteo_normalizes_icons` — asserts WMO codes 0→`sunny`, 61→`rainy`, 71→`snow`, 95→`storm`, 45→`fog`
  - `test_openmeteo_temps_and_precip` — asserts `temp_high`, `temp_low`, `precip_percent` values are correct
  - `test_all_icon_keys_are_valid` — iterates all entries in `ICON_KEYS`, asserts each value is in `{"sunny","partly-cloudy","cloudy","rainy","heavy-rain","snow","storm","fog"}`
- [ ] `pytest tests/test_weather.py -v` passes (4 tests)
- [ ] Committed to git with message `feat: weather source with Open-Meteo and AccuWeather providers`

---

### US-009: Home Assistant Entity Source
**Description:** As a developer, I need the backend to concurrently fetch the state of configured Home Assistant entities so that the dashboard displays live sensor values.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `sources/homeassistant.py` has `async def get_entities(cfg: AppConfig) -> list[HaEntity]`
- [ ] If `cfg.home_assistant.entities` is empty, returns `[]` immediately without making any HTTP calls
- [ ] Fetches all entities concurrently via `asyncio.gather()` — not sequentially
- [ ] Each entity fetched via `GET {ha_url}/api/states/{entity_id}` with `Authorization: Bearer {token}` header
- [ ] `HaEntity` built from response: `id = entity_id`, `label = HaEntityConfig.label` (from config, not from HA), `state = data["state"]`, `unit = data["attributes"]["unit_of_measurement"]` (empty string if missing)
- [ ] If any entity fetch fails (non-200, timeout, network error), that entity is omitted from result; other entities still returned
- [ ] `tests/test_homeassistant.py` has 3 tests (using `@respx.mock`):
  - `test_fetches_entity_state` — mocks HA API, asserts `state=="22.5"`, `unit=="°C"`, `label=="Obývák"`
  - `test_returns_empty_when_no_entities_configured` — sets `cfg.home_assistant.entities = []`, asserts `[]` returned
  - `test_skips_unreachable_entity` — mocks 404 response, asserts empty list returned
- [ ] `pytest tests/test_homeassistant.py -v` passes (3 tests)
- [ ] Committed to git with message `feat: Home Assistant entity source`

---

### US-010: Wire All Sources into `/api/data` with Background Cache
**Description:** As a developer, I need the `/api/data` endpoint to return real data from all sources, fetched eagerly on startup and refreshed in the background, so that every response is instant and never depends on an in-flight external call.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `main.py` `create_app()` accepts a `config_path: str` parameter; config loaded via `load_config(config_path)`
- [ ] `Cache` instance created per app instance (not global)
- [ ] On `startup` event: all four sources (`photos`, `events`, `weather`, `ha_entities`) fetched concurrently via `asyncio.gather()`; results stored in cache with TTLs: photos=3600s, events=300s, weather=1800s, ha_entities=60s
- [ ] Background `asyncio.create_task` loops started for each source; each loop: `asyncio.sleep(ttl)`, then re-fetch, then update cache; on error, keeps stale value
- [ ] `GET /api/data` reads all four keys from cache using `return_stale=True` (returns `[]` if still missing); never makes external calls
- [ ] `GET /api/data` response time is under 50ms (always from cache)
- [ ] `tests/test_api_integration.py` exists with `test_api_data_returns_real_data` that:
  - Mocks Open-Meteo, iCloud webstream + webasseturls, both ICS feeds, HA API using `respx`
  - Calls `app.router.startup()` to trigger eager load
  - Calls `GET /api/data` and asserts: `weather` has 5 items, `weather[0].icon == "sunny"`, `photos` has 1 item, `photo_interval_seconds == 30`
- [ ] `pytest -v` (all tests) passes
- [ ] `curl -s http://localhost:3000/api/data | python3 -m json.tool` (server started manually) shows real JSON with all fields
- [ ] Committed to git with message `feat: wire all sources into /api/data with background TTL cache`

---

### US-011: TypeScript Frontend Scaffold, Shared Types, and HTML Shell
**Description:** As a developer, I need the TypeScript project scaffold, shared type definitions, the HTML shell, and the CSS grid layout so that all frontend modules can be built and compiled incrementally.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `src/types.ts` exports interfaces: `Photo` (id, url), `CalendarEvent` (id, title, start, end, all_day, calendar_name, color), `WeatherDay` (date, icon, temp_high, temp_low, precip_percent), `HaEntity` (id, label, state, unit), `DashboardData` (photos, events, weather, ha_entities, photo_interval_seconds, server_time) — all field names match the Python Pydantic models exactly
- [ ] `src/api.ts` exports `fetchData(): Promise<DashboardData>` that calls `fetch("/api/data")`, throws on non-OK response, returns parsed JSON
- [ ] `static/index.html` has: `<link>` tags for all 5 CSS files (`base.css`, `photo.css`, `calendar.css`, `clock.css`, `weather.css`, `mini-calendar.css`), `<script src="/static/js/app.js">` at end of body, and containers: `#photo-area` (with `#photo-a` and `#photo-b` img elements), `#calendar-area`, `#clock-area`, `#weather-area`, `#mini-cal-area`, `#ha-area`
- [ ] `static/css/base.css` defines CSS grid on `.dashboard` with `grid-template-areas`: photo spanning full width top row (55vh), calendar left column rows 2-5, clock/weather/mini-cal/ha in right column rows 2-5
- [ ] `.ha-area` has `grid-area: ha`, `display: none` by default
- [ ] `src/app.ts` minimal entry: calls `startClock()` placeholder and `fetchData()` on load; compiles without errors
- [ ] `npm run build` exits 0 and produces `static/js/app.js`
- [ ] `npx tsc --noEmit` exits 0 (no type errors)
- [ ] Committed to git with message `feat: TypeScript scaffold, shared types, HTML shell, base CSS grid`

---

### US-012: Clock Module
**Description:** As a user, I want a large digital clock in the top-right area of the dashboard updating every second so that I can see the current time at a glance without any network call.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `src/modules/clock.ts` exports `startClock(container: HTMLElement): void`
- [ ] `startClock` calls `setInterval` with 1000ms interval — no `fetch` or external call
- [ ] Each tick sets `container.textContent` to `HH:MM` (24-hour, zero-padded, e.g. `"07:43"`)
- [ ] `static/css/clock.css` styles `#clock-area`: large font (`clamp(3rem, 6vw, 7rem)`), weight 200, centered, white color
- [ ] `src/app.ts` updated to import and call `startClock(document.getElementById("clock-area")!)`
- [ ] `npm run build` exits 0
- [ ] `npx tsc --noEmit` exits 0
- [ ] Committed to git with message `feat: clock module`

---

### US-013: Photo Crossfade Rotation Module
**Description:** As a user, I want the background photo to smoothly rotate through iCloud shared album photos every N seconds with a 1-second crossfade so that there are never blank frames or jarring cuts.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `src/modules/photo.ts` exports `render(data: Photo[], container: HTMLElement, photoIntervalSeconds: number): void`
- [ ] Uses two stacked `<img>` elements (`#photo-a` and `#photo-b`) — both present in HTML; only one has `photo-img--active` class at any time
- [ ] On each rotation: the non-active img's `src` is set to the next photo URL; on `onload`, active class is swapped (remove from current, add to next) — CSS `transition: opacity 1s` handles the fade
- [ ] Photo order is randomized on first call when `photos` array changes
- [ ] `render()` called on first load sets initial photo on `#photo-a` immediately (no wait for interval)
- [ ] Rotation interval timer reset when `photoIntervalSeconds` changes between calls
- [ ] `static/css/photo.css`: both `.photo-img` have `position: absolute`, `inset: 0`, `width/height: 100%`, `object-fit: cover`, `opacity: 0`, `transition: opacity 1s ease-in-out`; `.photo-img--active` has `opacity: 1`
- [ ] `src/app.ts` updated to import and call `renderPhotos(data.photos, document.getElementById("photo-area")!, data.photo_interval_seconds)`
- [ ] `npm run build` exits 0
- [ ] `npx tsc --noEmit` exits 0
- [ ] Committed to git with message `feat: photo crossfade rotation module`

---

### US-014: Calendar Module
**Description:** As a user, I want to see today's and upcoming calendar events in a scrolling list, grouped by date with color-coded borders, so that I can plan my day at a glance.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `src/modules/calendar.ts` exports `render(events: CalendarEvent[], container: HTMLElement): void`
- [ ] `container.innerHTML = ""` called at start of each render (full redraw)
- [ ] Events grouped by date (`event.start.slice(0, 10)`); one date header per group
- [ ] Date header shows day number (e.g. `07`) and Czech label: `dnes` for today, `zítra` for tomorrow, abbreviated weekday (`po`, `út`, `st`, `čt`, `pá`, `so`, `ne`) for subsequent days
- [ ] Each event row has: colored left border (`border-left: 4px solid <color>`, set via `--cal-color` CSS variable), time range (`HH:MM` / `HH:MM`) or `celý den` for all-day events, and event title
- [ ] `static/css/calendar.css`: calendar area has `overflow-y: auto` with `scrollbar-width: none` (no visible scrollbar), dark semi-transparent event background, readable font sizes
- [ ] `src/app.ts` updated to import and call `renderCalendar(data.events, document.getElementById("calendar-area")!)`
- [ ] `npm run build` exits 0
- [ ] `npx tsc --noEmit` exits 0
- [ ] Committed to git with message `feat: calendar module with date grouping and Czech labels`

---

### US-015: Weather Module
**Description:** As a user, I want to see a 5-day weather forecast with icons, high/low temperatures, and precipitation percentage so that I can plan the week ahead.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `src/modules/weather.ts` exports `render(days: WeatherDay[], container: HTMLElement): void`
- [ ] `container.innerHTML = ""` at start of each render
- [ ] For each day: displays abbreviated Czech weekday (`po`, `út`, `st`, `čt`, `pá`, `so`, `ne`), weather emoji icon mapped from normalized icon key, high temp (rounded integer + `°`), low temp (rounded integer + `°`), precipitation % (integer + `%`)
- [ ] Icon mapping: `sunny→☀️`, `partly-cloudy→⛅`, `cloudy→☁️`, `rainy→🌧`, `heavy-rain→⛈`, `snow→❄️`, `storm→⛈`, `fog→🌫`; unknown keys render `🌡`
- [ ] `static/css/weather.css`: 5 days displayed in a horizontal row (`flex-direction: row`), each day as a column with icon, temps, precip stacked vertically; precipitation in blue (`#5b9bd5`), low temp in muted grey
- [ ] `src/app.ts` updated to import and call `renderWeather(data.weather, document.getElementById("weather-area")!)`
- [ ] `npm run build` exits 0
- [ ] `npx tsc --noEmit` exits 0
- [ ] Committed to git with message `feat: weather module with 5-day forecast`

---

### US-016: Mini Calendar Module, HA Display, and Polling Loop
**Description:** As a user, I want a mini month calendar (with today highlighted and event dots), and Home Assistant sensor values displayed below the weather — all updated automatically every 60 seconds without a page reload.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `src/modules/mini-calendar.ts` exports `render(events: CalendarEvent[], container: HTMLElement): void`
- [ ] Calendar header row shows Czech abbreviated weekdays: `po út st čt pá so ne` (Monday-first)
- [ ] Today's date cell has `mini-cal-today` class: red circle background (`#e53935`), white text, bold
- [ ] Days with events have colored dots below the day number — up to 3 dots, one per calendar color (duplicates collapsed)
- [ ] First day of month offset calculated correctly: Monday = 0, Sunday = 6
- [ ] `static/css/mini-calendar.css`: 7-column grid layout, compact cells, dots as 4px circles
- [ ] `src/app.ts` `update(data: DashboardData)` function calls all five render functions: `renderPhotos`, `renderCalendar`, `renderWeather`, `renderMiniCal`, and HA inline render
- [ ] HA inline render in `app.ts`: if `data.ha_entities.length > 0`, sets `#ha-area` `display = "flex"` and populates `innerHTML` with `"Label: value unit"` spans; if empty, sets `display = "none"`
- [ ] `init()` in `app.ts`: calls `startClock`, awaits initial `fetchData()` → `update()`, then sets `setInterval(async () => { update(await fetchData()) }, 60_000)`
- [ ] `setInterval` errors caught with `console.error` — never crashes the page
- [ ] `npm run build` exits 0
- [ ] `npx tsc --noEmit` exits 0
- [ ] Committed to git with message `feat: mini calendar module with event dots and complete polling loop`

---

### US-017: systemd Service Files
**Description:** As a developer, I need systemd service files for both the FastAPI server and the Chromium kiosk browser so that both auto-start on RPi boot and restart on crash.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `systemd/wmd-server.service` exists with:
  - `[Unit]`: `After=network.target`, `Wants=network.target`
  - `[Service]`: `User=ubuntu`, `WorkingDirectory=/home/ubuntu/wmd`, `ExecStart=/home/ubuntu/wmd/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 3000`, `Restart=always`, `RestartSec=5`, `StandardOutput=journal`, `StandardError=journal`
  - `[Install]`: `WantedBy=multi-user.target`
- [ ] `systemd/wmd-browser.service` exists with:
  - `[Unit]`: `After=wmd-server.service graphical-session.target`, `Wants=graphical-session.target`
  - `[Service]`: `User=ubuntu`, `Environment=DISPLAY=:0`, `Environment=XAUTHORITY=/home/ubuntu/.Xauthority`, `ExecStartPre=/bin/sleep 3`, `ExecStart=/usr/bin/chromium-browser` with flags: `--kiosk --noerrdialogs --disable-infobars --no-first-run --check-for-update-interval=31536000 --disable-translate --disable-features=Translate --autoplay-policy=no-user-gesture-required http://localhost:3000`, `Restart=always`, `RestartSec=5`
  - `[Install]`: `WantedBy=graphical-session.target`
- [ ] A comment in both files notes that `ubuntu` should be replaced with `pi` on Raspberry Pi OS
- [ ] Committed to git with message `feat: systemd service files for server and kiosk browser`

---

### US-018: README and Deployment Guide
**Description:** As a developer, I need a complete README covering Ubuntu Server setup, dependency installation, frontend build, systemd service enablement, and config documentation so that the dashboard can be deployed from scratch on a fresh RPi.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `README.md` exists with the following sections:
  - **Requirements**: Raspberry Pi + Ubuntu Server 22.04+, Python 3.11+, Node.js 18+, Chromium, `unclutter`
  - **Setup / Step 1 — Install system dependencies**: `sudo apt install -y chromium-browser unclutter xorg lightdm`
  - **Setup / Step 2 — Clone and configure**: `git clone`, `cp config.example.json config.json`, edit config
  - **Setup / Step 3 — Install Python dependencies**: create `.venv`, activate, `pip install -r requirements.txt`
  - **Setup / Step 4 — Build frontend**: `npm install && npm run build`
  - **Setup / Step 5 — Install systemd services**: `sudo cp systemd/*.service /etc/systemd/system/`, `systemctl daemon-reload`, `systemctl enable wmd-server wmd-browser`, `systemctl start wmd-server wmd-browser`
  - **Setup / Step 6 — Enable auto-login**: set `graphical.target` as default, configure `lightdm.conf` for `autologin-user=ubuntu`
  - **Updating config**: `nano config.json` → `sudo systemctl restart wmd-server` (no rebuild needed)
  - **Updating frontend**: `npm run build` → `sudo systemctl restart wmd-server`
  - **Calendar ICS URLs**: how to get ICS links from iCloud, Google, and MS365/Outlook
  - **iCloud Share Token**: how to extract token from share URL
  - **Logs**: `journalctl -u wmd-server -f` and `journalctl -u wmd-browser -f`
- [ ] Committed to git with message `docs: deployment guide and setup README`

---

### US-019: Final Verification
**Description:** As a developer, I need to verify that the complete system — all tests, type checks, and a manual smoke test — passes before declaring the implementation complete.

> **Use superpowers:executing-plans skill for implementing this user story.**

**Acceptance Criteria:**
- [ ] `pytest -v` passes all tests (target: ≥18 tests across test_cache, test_config, test_calendar, test_weather, test_icloud, test_homeassistant, test_api, test_api_integration)
- [ ] `npx tsc --noEmit` exits 0 (no TypeScript errors)
- [ ] `npm run build` exits 0 and produces `static/js/app.js`
- [ ] `python3 main.py` starts without errors; `curl -s http://localhost:3000/api/data | python3 -m json.tool | head -30` returns valid JSON with correct schema
- [ ] `curl http://localhost:3000/` returns HTML (status 200)
- [ ] Final git commit created: `git add -A && git commit -m "chore: final verification pass"`

---

## Functional Requirements

- FR-1: `GET /api/data` returns `DashboardData` JSON; response time < 50ms (always from in-memory cache)
- FR-2: `GET /api/photo/{id}` proxies iCloud photo bytes; browser never calls iCloud directly
- FR-3: iCloud photo list refreshed every 3600s; frontend rotates photos every `photoIntervalSeconds` seconds with CSS crossfade; no blank frame during transition
- FR-4: ICS feeds fetched concurrently every 300s; recurring events expanded; all-day events shown first within each day; broken feeds silently skipped
- FR-5: Weather refreshed every 1800s; backend normalizes WMO codes and AccuWeather icon IDs to a fixed 8-icon vocabulary; provider switchable via `config.json`
- FR-6: HA entities fetched every 60s; individual entity failures don't block others; empty list hides the HA widget entirely
- FR-7: Frontend polls `/api/data` every 60s; all updates are in-place DOM mutations; no `location.reload()` anywhere
- FR-8: Clock updates every second via `setInterval`; no network call
- FR-9: Chromium runs in `--kiosk` mode; `unclutter` hides mouse cursor
- FR-10: Both systemd services start on boot (`systemctl enable`) and restart on failure (`Restart=always`, `RestartSec=5`)
- FR-11: All config (ICS URLs, tokens, coordinates, intervals, colors) lives in `config.json`; no code changes needed to add a calendar or swap weather provider

---

## Non-Goals

- No external access / HTTPS / port forwarding
- No write access to calendars (read-only ICS only)
- No user authentication
- No admin UI for config editing
- No mobile/portrait layout
- No PWA or offline mode
- No multi-dashboard or multi-display support
- No push notifications or alerts

---

## Technical Considerations

- **Python 3.11+** required for `str | None` union syntax and `asyncio.TaskGroup`; Ubuntu 22.04 ships Python 3.10 — install 3.11 via `deadsnakes` PPA if needed
- **iCloud API**: undocumented private API; two-step POST flow; may return `X-Apple-MMe-Host` redirect header that must be followed
- **Recurring events**: use `dateutil.rrule.rrulestr` for RRULE expansion; apply EXDATE exclusions before filtering to window
- **esbuild bundle**: single output `static/js/app.js`; all TypeScript compiled at build time; no runtime transpilation on RPi
- **CSS crossfade**: two `<img>` elements in `#photo-area`; `transition: opacity 1s`; swap via JS class toggle on `onload`
- **Ubuntu Server kiosk**: requires `xorg` + display manager (`lightdm`) + auto-login configured; `DISPLAY=:0` must be set in browser systemd service

---

## Success Metrics

- `pytest -v` passes all tests with no failures
- Dashboard visible within 10 seconds of RPi boot
- All four data sources display real data (photos rotating, calendar events listed, weather forecast shown, HA value displayed)
- No visible flicker or blank frames during photo rotation or 60s data refresh
- System runs continuously for 7+ days without manual intervention
- Adding a new ICS calendar requires only editing `config.json` and restarting `wmd-server`

---

## Confirmed Decisions

- Mini calendar shows event dots for all configured calendars (up to 3 dots per day)
- All labels use Czech locale: `dnes`, `zítra`, `po/út/st/čt/pá/so/ne`
- Home Assistant widget hidden entirely when `ha_entities` is empty in config
