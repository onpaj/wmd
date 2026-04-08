# Data Loading Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden backend data loading against hung sources, slow startup, and repeated failures.

**Architecture:** Remove dead AccuWeather code; add explicit httpx timeouts to all sources; make startup non-blocking by firing cache population as a background task; replace `_refresh_loop`'s fixed sleep with exponential backoff (10s → 20s → 40s → TTL cap) and wrap every `fetch_fn()` call in `asyncio.wait_for(..., timeout=60)` as a hard ceiling.

**Tech Stack:** Python 3.11+, FastAPI, httpx, asyncio, pytest, respx

---

## File Map

| File | Change |
|---|---|
| `config.py` | Remove `accuweather_api_key` from `WeatherConfig` and `load_config` |
| `sources/weather.py` | Remove `_AW_ICON_KEYS`, `AccuWeatherProvider`, accuweather branch |
| `config.example.json` | Remove `accuweatherApiKey` field |
| `tests/conftest.py` | Remove `accuweatherApiKey` from SAMPLE_CONFIG |
| `tests/test_api.py` | Remove `accuweatherApiKey` from fixture; add `_backoff_delay` tests |
| `tests/test_api_integration.py` | Remove `accuweatherApiKey` from fixture |
| `tests/test_config.py` | Remove `accuweatherApiKey` from inline config dict |
| `tests/test_calendar.py` | Remove `accuweather_api_key` from `WeatherConfig` in `make_config` |
| `tests/test_homeassistant.py` | Remove `accuweather_api_key` from `WeatherConfig` in `make_cfg` |
| `tests/test_icloud.py` | Remove `accuweather_api_key` from `WeatherConfig` in `make_config` |
| `tests/test_ms365.py` | Remove `accuweather_api_key` from `WeatherConfig` (two places) |
| `tests/test_weather.py` | Remove `accuweather_api_key` from `WeatherConfig` in `_make_cfg` |
| `sources/icloud.py` | Add `timeout=20.0` to `AsyncClient` |
| `sources/calendar.py` | Add `timeout=20.0` to both `AsyncClient` calls |
| `sources/ms365.py` | Add `timeout=30.0` to `AsyncClient` |
| `main.py` | Module-level `_FETCH_TIMEOUT`, `_backoff_delay`; non-blocking startup; resilient `_refresh_loop` |

---

## Task 1: Remove AccuWeather

**Files:** `config.py`, `sources/weather.py`, `config.example.json`, all 8 test files listed above

- [ ] **Step 1: Run tests to establish baseline**

  ```
  pytest -q
  ```
  Expected: all tests pass before any changes.

- [ ] **Step 2: Remove `accuweather_api_key` from `WeatherConfig` in `config.py`**

  Replace:
  ```python
  @dataclass
  class WeatherConfig:
      provider: str
      latitude: float
      longitude: float
      accuweather_api_key: str
  ```
  with:
  ```python
  @dataclass
  class WeatherConfig:
      provider: str
      latitude: float
      longitude: float
  ```

- [ ] **Step 3: Remove `accuweatherApiKey` from `load_config` in `config.py`**

  Replace:
  ```python
      weather = WeatherConfig(
          provider=weather_data["provider"],
          latitude=weather_data["latitude"],
          longitude=weather_data["longitude"],
          accuweather_api_key=weather_data.get("accuweatherApiKey", ""),
      )
  ```
  with:
  ```python
      weather = WeatherConfig(
          provider=weather_data["provider"],
          latitude=weather_data["latitude"],
          longitude=weather_data["longitude"],
      )
  ```

- [ ] **Step 4: Remove AccuWeather from `sources/weather.py`**

  Delete the entire `_AW_ICON_KEYS` dictionary (the `dict[int, str]` block that starts at `_AW_ICON_KEYS: dict[int, str] = {`) and the entire `AccuWeatherProvider` class.

  Replace `get_forecast` at the bottom of the file:
  ```python
  async def get_forecast(cfg: AppConfig) -> list[WeatherDay]:
      if cfg.weather.provider == "metno":
          return await METNorwayProvider().get_forecast(cfg)
      return await OpenMeteoProvider().get_forecast(cfg)
  ```

- [ ] **Step 5: Remove `accuweatherApiKey` from `config.example.json`**

  Replace:
  ```json
    "weather": {
      "provider": "metno",
      "latitude": 50.07,
      "longitude": 14.43,
      "accuweatherApiKey": ""
    },
  ```
  with:
  ```json
    "weather": {
      "provider": "metno",
      "latitude": 50.07,
      "longitude": 14.43
    },
  ```

- [ ] **Step 6: Remove accuweather references from test fixtures**

  **`tests/conftest.py`** — in `SAMPLE_CONFIG`, replace:
  ```python
      "weather": {
          "provider": "openmeteo",
          "latitude": 50.07,
          "longitude": 14.43,
          "accuweatherApiKey": "",
      },
  ```
  with:
  ```python
      "weather": {
          "provider": "openmeteo",
          "latitude": 50.07,
          "longitude": 14.43,
      },
  ```

  **`tests/test_api.py`** — in `config_file`, replace:
  ```python
          "weather": {"provider": "openmeteo", "latitude": 50.07, "longitude": 14.43, "accuweatherApiKey": ""},
  ```
  with:
  ```python
          "weather": {"provider": "openmeteo", "latitude": 50.07, "longitude": 14.43},
  ```

  **`tests/test_api_integration.py`** — in `config_file`, replace:
  ```python
          "weather": {"provider": "openmeteo", "latitude": 50.07, "longitude": 14.43, "accuweatherApiKey": ""},
  ```
  with:
  ```python
          "weather": {"provider": "openmeteo", "latitude": 50.07, "longitude": 14.43},
  ```

  **`tests/test_config.py`** — in `test_load_config_reads_exclude_patterns`, replace:
  ```python
          "weather": {"provider": "metno", "latitude": 50.0, "longitude": 14.0, "accuweatherApiKey": ""},
  ```
  with:
  ```python
          "weather": {"provider": "metno", "latitude": 50.0, "longitude": 14.0},
  ```

  **`tests/test_calendar.py`** — in `make_config`, replace:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0, accuweather_api_key=""),
  ```
  with:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
  ```

  **`tests/test_homeassistant.py`** — in `make_cfg`, replace:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0, accuweather_api_key=""),
  ```
  with:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
  ```

  **`tests/test_icloud.py`** — in `make_config`, replace:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0, accuweather_api_key=""),
  ```
  with:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
  ```

  **`tests/test_ms365.py`** — in `make_config` (line ~26), replace:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0, accuweather_api_key=""),
  ```
  with:
  ```python
          weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
  ```

  Also in `test_returns_empty_when_ms365_not_configured` (line ~136), replace the same pattern.

  **`tests/test_weather.py`** — in `_make_cfg`, replace:
  ```python
          weather=WeatherConfig(
              provider=provider,
              latitude=50.07,
              longitude=14.43,
              accuweather_api_key="",
          ),
  ```
  with:
  ```python
          weather=WeatherConfig(
              provider=provider,
              latitude=50.07,
              longitude=14.43,
          ),
  ```

- [ ] **Step 7: Run tests**

  ```
  pytest -q
  ```
  Expected: all tests pass.

- [ ] **Step 8: Commit**

  ```bash
  git add config.py sources/weather.py config.example.json \
      tests/conftest.py tests/test_api.py tests/test_api_integration.py \
      tests/test_config.py tests/test_calendar.py tests/test_homeassistant.py \
      tests/test_icloud.py tests/test_ms365.py tests/test_weather.py
  git commit -m "refactor: remove AccuWeather provider"
  ```

---

## Task 2: Add Explicit HTTP Timeouts to Sources

**Files:** `sources/icloud.py`, `sources/calendar.py`, `sources/ms365.py`

No new tests — httpx timeout errors propagate through the existing exception handling already covered by current tests.

- [ ] **Step 1: Add `timeout=20.0` to `sources/icloud.py`**

  Replace:
  ```python
      async with httpx.AsyncClient() as client:
          # Step 1: get stream
  ```
  with:
  ```python
      async with httpx.AsyncClient(timeout=20.0) as client:
          # Step 1: get stream
  ```

- [ ] **Step 2: Add `timeout=20.0` to `get_mini_cal_events` in `sources/calendar.py`**

  Replace:
  ```python
      async with httpx.AsyncClient() as client:
          return await _fetch_calendar(client, cal_cfg, window_start, window_end)
  ```
  with:
  ```python
      async with httpx.AsyncClient(timeout=20.0) as client:
          return await _fetch_calendar(client, cal_cfg, window_start, window_end)
  ```

- [ ] **Step 3: Add `timeout=20.0` to `get_events` in `sources/calendar.py`**

  Replace:
  ```python
      async with httpx.AsyncClient() as client:
          results = await asyncio.gather(
  ```
  with:
  ```python
      async with httpx.AsyncClient(timeout=20.0) as client:
          results = await asyncio.gather(
  ```

- [ ] **Step 4: Add `timeout=30.0` to `sources/ms365.py`**

  Replace:
  ```python
      async with httpx.AsyncClient() as client:
          try:
              token = await _get_token(client, cfg.ms365.tenant_id, cfg.ms365.client_id, cfg.ms365.client_secret)
  ```
  with:
  ```python
      async with httpx.AsyncClient(timeout=30.0) as client:
          try:
              token = await _get_token(client, cfg.ms365.tenant_id, cfg.ms365.client_id, cfg.ms365.client_secret)
  ```

- [ ] **Step 5: Run tests**

  ```
  pytest -q
  ```
  Expected: all tests pass.

- [ ] **Step 6: Commit**

  ```bash
  git add sources/icloud.py sources/calendar.py sources/ms365.py
  git commit -m "fix: add explicit httpx timeouts to all data sources"
  ```

---

## Task 3: Non-Blocking Startup

**File:** `main.py`

The existing `test_api_data_returns_200` in `tests/test_api.py` already validates the non-blocking pattern — the test fixture calls `create_app` without triggering FastAPI startup events and still gets a 200. No new test needed.

- [ ] **Step 1: Replace `startup()` in `main.py`**

  Replace the entire `startup` async function:
  ```python
      @app.on_event("startup")
      async def startup() -> None:
          await _populate_cache()
          asyncio.create_task(_refresh_loop("photos", lambda: get_photos(config), _TTLS["photos"]))
          async def _fetch_all_events():
              ics, ms365 = await asyncio.gather(get_events(config), get_ms365_events(config), return_exceptions=True)
              combined = []
              if not isinstance(ics, BaseException):
                  combined.extend(ics)
              if not isinstance(ms365, BaseException):
                  combined.extend(ms365)
              combined.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
              return combined

          asyncio.create_task(_refresh_loop("events", _fetch_all_events, _TTLS["events"]))
          asyncio.create_task(_refresh_loop("mini_cal_events", lambda: get_mini_cal_events(config), _TTLS["mini_cal_events"]))
          asyncio.create_task(_refresh_loop("weather", lambda: get_forecast(config), _TTLS["weather"]))
          asyncio.create_task(_refresh_loop("ha_entities", lambda: get_entities(config), _TTLS["ha_entities"]))
          asyncio.create_task(_refresh_loop("meals", lambda: get_meals(config), _TTLS["meals"]))
          asyncio.create_task(_refresh_loop("outdoor_temp", lambda: get_outdoor_temp(config), _TTLS["outdoor_temp"]))
  ```
  with:
  ```python
      @app.on_event("startup")
      async def startup() -> None:
          async def _fetch_all_events():
              ics, ms365 = await asyncio.gather(get_events(config), get_ms365_events(config), return_exceptions=True)
              combined = []
              if not isinstance(ics, BaseException):
                  combined.extend(ics)
              if not isinstance(ms365, BaseException):
                  combined.extend(ms365)
              combined.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
              return combined

          asyncio.create_task(_populate_cache())
          asyncio.create_task(_refresh_loop("photos", lambda: get_photos(config), _TTLS["photos"]))
          asyncio.create_task(_refresh_loop("events", _fetch_all_events, _TTLS["events"]))
          asyncio.create_task(_refresh_loop("mini_cal_events", lambda: get_mini_cal_events(config), _TTLS["mini_cal_events"]))
          asyncio.create_task(_refresh_loop("weather", lambda: get_forecast(config), _TTLS["weather"]))
          asyncio.create_task(_refresh_loop("ha_entities", lambda: get_entities(config), _TTLS["ha_entities"]))
          asyncio.create_task(_refresh_loop("meals", lambda: get_meals(config), _TTLS["meals"]))
          asyncio.create_task(_refresh_loop("outdoor_temp", lambda: get_outdoor_temp(config), _TTLS["outdoor_temp"]))
  ```

- [ ] **Step 2: Run tests**

  ```
  pytest -q
  ```
  Expected: all tests pass.

- [ ] **Step 3: Commit**

  ```bash
  git add main.py
  git commit -m "fix: start server immediately; populate cache in background"
  ```

---

## Task 4: Resilient Refresh Loop with Exponential Backoff

**Files:** `main.py`, `tests/test_api.py`

- [ ] **Step 1: Write failing tests for `_backoff_delay` in `tests/test_api.py`**

  Add at the top of the file (after existing imports):
  ```python
  from main import _backoff_delay
  ```

  Add at the bottom of the file:
  ```python
  def test_backoff_delay_no_failures_returns_ttl():
      assert _backoff_delay(0, 60) == 60
      assert _backoff_delay(0, 1800) == 1800


  def test_backoff_delay_first_failure_returns_10s():
      assert _backoff_delay(1, 60) == 10
      assert _backoff_delay(1, 1800) == 10


  def test_backoff_delay_doubles_per_failure():
      assert _backoff_delay(2, 300) == 20
      assert _backoff_delay(3, 300) == 40


  def test_backoff_delay_caps_at_ttl():
      assert _backoff_delay(4, 60) == 60   # min(80, 60) = 60
      assert _backoff_delay(10, 60) == 60  # still capped


  def test_backoff_delay_long_ttl_not_capped_early():
      assert _backoff_delay(4, 1800) == 80   # min(80, 1800) = 80
      assert _backoff_delay(7, 1800) == 640  # min(10 * 2^6, 1800) = 640
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```
  pytest tests/test_api.py -k "backoff" -v
  ```
  Expected: `ImportError: cannot import name '_backoff_delay' from 'main'`

- [ ] **Step 3: Add `_FETCH_TIMEOUT` and `_backoff_delay` to `main.py` at module level**

  After the `_TTLS` dictionary (around line 30), add:
  ```python
  _FETCH_TIMEOUT = 60  # hard ceiling per source fetch, in seconds


  def _backoff_delay(consecutive_failures: int, ttl: int) -> float:
      if consecutive_failures == 0:
          return ttl
      return min(10 * (2 ** (consecutive_failures - 1)), ttl)
  ```

- [ ] **Step 4: Run backoff tests to confirm they pass**

  ```
  pytest tests/test_api.py -k "backoff" -v
  ```
  Expected: all 5 backoff tests PASS.

- [ ] **Step 5: Replace `_refresh_loop` inside `create_app` in `main.py`**

  Replace:
  ```python
      async def _refresh_loop(key: str, fetch_fn, ttl: int) -> None:
          while True:
              await asyncio.sleep(ttl)
              try:
                  value = await fetch_fn()
                  if key == "weather":
                      value = _to_weather_models(value)
                  cache.set(key, value, ttl)
              except Exception:
                  logger.exception("Background refresh failed for %s", key)
  ```
  with:
  ```python
      async def _refresh_loop(key: str, fetch_fn, ttl: int) -> None:
          consecutive_failures = 0
          while True:
              await asyncio.sleep(_backoff_delay(consecutive_failures, ttl))
              try:
                  value = await asyncio.wait_for(fetch_fn(), timeout=_FETCH_TIMEOUT)
                  if key == "weather":
                      value = _to_weather_models(value)
                  cache.set(key, value, ttl)
                  consecutive_failures = 0
              except asyncio.TimeoutError:
                  consecutive_failures += 1
                  logger.warning("Fetch timeout for %s (attempt %d)", key, consecutive_failures)
              except Exception:
                  consecutive_failures += 1
                  logger.exception("Background refresh failed for %s (attempt %d)", key, consecutive_failures)
  ```

- [ ] **Step 6: Run full test suite**

  ```
  pytest -q
  ```
  Expected: all tests pass.

- [ ] **Step 7: Commit**

  ```bash
  git add main.py tests/test_api.py
  git commit -m "fix: resilient refresh loop with exponential backoff and fetch timeout"
  ```
