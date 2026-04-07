# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **pytest pythonpath**: `pytest.ini` with `pythonpath = .` is required to import root-level modules (cache.py, config.py, etc.) from tests/. Without it, `from cache import Cache` fails with ModuleNotFoundError.
- **ASGI lifespan in tests**: `httpx.ASGITransport` does NOT trigger ASGI startup events. Store the startup logic in `app.state.populate_cache` and call it directly in integration tests with `await app.state.populate_cache()` under `@respx.mock`.

---

## 2026-04-07 - US-001
- Implemented full project scaffold from scratch
- Files created: sources/__init__.py, requirements.txt, package.json, tsconfig.json, config.example.json, config.json, .gitignore, src/app.ts
- Directories created: sources/, tests/, src/modules/, static/js/, static/css/, systemd/
- Python venv created at .venv/ with all pinned dependencies installed
- npm install completed with esbuild ^0.20.0 and typescript ^5.4.0
- TypeScript typecheck passes (tsc --noEmit)
- **Learnings:**
  - tsconfig.json needs `"moduleResolution": "bundler"` for esbuild compatibility with ESNext module target
  - src/app.ts must exist (even as a stub) for tsc to have something to check
  - config.json is gitignored and copied from config.example.json
---

## 2026-04-07 - US-002
- Implemented Pydantic response models in models.py
- Files changed: models.py (new)
- **Learnings:**
  - Use `.venv/bin/python3` to run Python in this project (venv at .venv/)
  - `list[Photo]` syntax works fine with Python 3.11+ and pydantic v2
---

## 2026-04-07 - US-003
- Implemented typed config loader using Python dataclasses
- Files changed: config.py (new), tests/conftest.py (new), tests/test_config.py (new)
- **Learnings:**
  - No mypy in requirements.txt; typecheck means syntax/import correctness only for now
  - camelCase JSON keys are mapped manually in load_config() — no external library needed
  - pytest conftest.py with tmp_path fixture works well for file-based config tests
---

## 2026-04-07 - US-004
- Implemented in-memory TTL cache using `time.monotonic()` for expiry
- Files changed: cache.py (new), tests/test_cache.py (new), pytest.ini (new)
- **Learnings:**
  - pytest.ini with `pythonpath = .` is needed so tests can import root-level modules
  - `time.monotonic()` is preferred over `time.time()` for TTL expiry (immune to clock adjustments)
  - TTL=0 entries expire immediately; a 10ms sleep reliably triggers expiry in tests
---

## 2026-04-07 - US-005
- Implemented FastAPI skeleton with mock /api/data endpoint
- Files created: main.py, static/index.html, tests/test_api.py
- Files changed: pytest.ini (added asyncio_mode = auto)
- **Learnings:**
  - `asyncio_mode = auto` in pytest.ini allows async test functions without `@pytest.mark.asyncio` decorator
  - `ASGITransport` from httpx is the correct way to test FastAPI apps without a running server; use `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`
  - FastAPI catch-all route `/{full_path:path}` must be defined AFTER specific routes (like /api/data) and static mounts to avoid shadowing them
  - `create_app(config_path)` factory pattern lets tests inject a temp config file, avoiding dependency on real config.json at test time
  - `StaticFiles(directory=...)` raises `RuntimeError` if the directory doesn't exist at mount time — directories must exist before app startup
---

## 2026-04-07 - US-006
- Implemented iCloud shared album photo source in sources/icloud.py
- Added GET /api/photo/{photo_id} proxy endpoint in main.py
- Files created: sources/icloud.py, tests/test_icloud.py
- Files changed: main.py (added photo proxy route and get_photo_url import)
- **Learnings:**
  - iCloud shared album API: POST `{streamCtag: None}` to webstream, then POST guids to webasseturls; asset items have `url_location` + `url_path` fields that must be combined
  - `X-Apple-MMe-Host` redirect pattern: if header present, repeat both API calls using that host as base
  - respx mock with `@respx.mock` decorator works cleanly for async httpx tests alongside `asyncio_mode = auto`
  - Module-level `_photo_url_map` dict acts as a side-channel for guid→real URL lookup, populated on each `get_photos()` call
---

## 2026-04-07 - US-007
- Implemented ICS calendar source in sources/calendar.py with async concurrent fetching, recurring event expansion, and all-day event detection
- Files created: sources/calendar.py, tests/test_calendar.py, tests/fixtures/simple.ics, tests/fixtures/recurring.ics
- **Learnings:**
  - **rrulestr timezone gotcha**: `rrulestr` inherits the tzinfo from `dtstart`. If dtstart is timezone-aware (UTC), `rule.between()` requires aware bounds too. Solution: strip tzinfo before passing to rrulestr (`dtstart_naive = dtstart_dt.replace(tzinfo=None)`) and re-attach UTC when building CalendarEvent.
  - `mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW)` is the pattern to freeze time in module-level functions without freezegun; the mock replaces the callable so it returns the fixed value directly.
  - icalendar `DTSTART;VALUE=DATE` produces `datetime.date` (not `datetime.datetime`); checking `isinstance(raw_start, date) and not isinstance(raw_start, datetime)` correctly distinguishes all-day from timed events.
  - EXDATE properties can be a single `vDDDLists` or a Python list of them; handle both: `props = exdate_prop if isinstance(exdate_prop, list) else [exdate_prop]`.
---

## 2026-04-07 - US-009
- Implemented Home Assistant entity source with concurrent fetching via asyncio.gather()
- Files created: sources/homeassistant.py, tests/test_homeassistant.py
- Files changed: config.py (added `label` field to HaEntityConfig, updated loader)
- **Learnings:**
  - `HaEntityConfig` needed a `label` field added (was missing from initial scaffold)
  - `_fetch_entity` helper returns `HaEntity | None`; None results filtered after `asyncio.gather()` — clean pattern for concurrent partial failures
  - `unit_of_measurement` may be absent or None; `or ""` handles both cases
---

## 2026-04-07 - US-010
- Wired all four sources into /api/data with background TTL cache
- Files changed: main.py (full rewrite with Cache, startup event, background refresh loops), tests/test_api_integration.py (new)
- **Learnings:**
  - `httpx.ASGITransport` does NOT trigger ASGI startup lifecycle events — store startup logic in `app.state.populate_cache` so integration tests can call it directly under `@respx.mock`
  - `sources/weather.WeatherDay` is a dataclass; `models.WeatherDay` is a Pydantic model — convert at cache boundary in main.py with `WeatherDayModel(**vars(w))` or explicit field mapping
  - `asyncio.gather(..., return_exceptions=True)` returns exceptions as values; check with `isinstance(result, BaseException)` before storing into cache; stale value is kept on error by simply not updating
  - `app.on_event("startup")` is deprecated in newer FastAPI — it still works but emits a `DeprecationWarning`; acceptable for now
---

## 2026-04-07 - US-008
- Implemented weather source with Open-Meteo and AccuWeather providers
- Files created: sources/weather.py, tests/test_weather.py
- **Learnings:**
  - `WeatherProvider` ABC pattern with `OpenMeteoProvider` and `AccuWeatherProvider` subclasses; module-level `get_forecast()` dispatches by `cfg.weather.provider`
  - `ICON_KEYS` maps WMO weather codes to normalized icon strings; `_AW_ICON_KEYS` maps AccuWeather icon IDs 1-44 to the same set
  - `respx.mock` decorator works cleanly with `asyncio_mode = auto` for mocking httpx calls in async tests (same pattern as icloud tests)
---

## 2026-04-07 - US-011
- Implemented TypeScript frontend scaffold: src/types.ts, src/api.ts, updated src/app.ts
- Created static/index.html with proper grid containers and CSS link tags
- Created static/css/base.css with 2-column/5-row CSS grid layout using grid-template-areas
- Created placeholder CSS files: photo.css, calendar.css, clock.css, weather.css, mini-calendar.css
- `npm run build` exits 0, `npx tsc --noEmit` exits 0
- **Learnings:**
  - TS interfaces use `string` for datetime fields (Python datetime serializes to ISO string in JSON)
  - `#ha-area` needs `display: none` in base.css (not in a separate ha.css) per acceptance criteria
  - CSS grid-template-areas names must not contain hyphens — use `mini-cal` as area name but it works fine in modern browsers
---

## 2026-04-07 - US-013
- Implemented photo crossfade rotation module
- Files created: src/modules/photo.ts, static/css/photo.css (updated)
- Files changed: src/app.ts (added renderPhotos import and call)
- **Learnings:**
  - Two-img swap pattern: non-active img gets new src; onload fires when image is ready, then classes swap — CSS opacity transition handles the 1s fade automatically
  - Module-level state (`_interval`, `_photos`, `_index`, `_currentIntervalSeconds`) persists across render() calls; interval is only reset when photoIntervalSeconds changes
  - `data !== _photos` reference check is insufficient alone — compare length+ids to detect photo array changes reliably
---

## 2026-04-07 - US-012
- Implemented clock module with 1-second interval updating HH:MM display
- Files created: src/modules/clock.ts
- Files changed: static/css/clock.css (added #clock-area styles), src/app.ts (import + startClock call)
- `npm run build` exits 0, `npx tsc --noEmit` exits 0
- **Learnings:**
  - `startClock` calls `tick()` immediately before starting the interval to avoid 1-second blank on load
  - `clamp(3rem, 6vw, 7rem)` in CSS provides responsive font sizing without media queries
---

## 2026-04-07 - US-015
- Implemented weather module with 5-day forecast display
- Files created: src/modules/weather.ts, static/css/weather.css (updated)
- Files changed: src/app.ts (added renderWeather import and call)
- `npm run build` exits 0, `npx tsc --noEmit` exits 0
- **Learnings:**
  - Czech abbreviated weekday from `date.getUTCDay()` — use UTC methods on YYYY-MM-DD strings since `new Date('2026-04-07')` parses as UTC midnight; `getDay()` would return previous day in UTC+1 or later timezones
  - `ICON_MAP[key] ?? '🌡'` — nullish coalescing handles both missing keys and empty string cleanly
  - `Math.round()` for temperature and precip % to produce integer display values
---

## 2026-04-07 - US-014
- Implemented calendar module with date grouping and Czech labels
- Files created: src/modules/calendar.ts, static/css/calendar.css (updated)
- Files changed: src/app.ts (added renderCalendar import and call)
- `npm run build` exits 0, `npx tsc --noEmit` exits 0
- **Learnings:**
  - Czech day labels use `new Date(dateStr).getDay()` on a date-only string — works reliably because Date constructor for YYYY-MM-DD parses as UTC midnight, so getDay() must use UTC methods or adjust; simpler to just build the lookup array indexed by getDay() result
  - `--cal-color` CSS variable set via `row.style.setProperty('--cal-color', ev.color)` — inline style property setProperty is required for custom properties (style.cssText assignment also works but setProperty is cleaner)
  - `scrollbar-width: none` (Firefox) + `::-webkit-scrollbar { display: none }` (Chrome) both needed for cross-browser hidden scrollbar
---
