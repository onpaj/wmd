# Data Loading Resilience Design

**Date:** 2026-04-08
**Status:** Approved

## Problem

The WMD backend fetches data from 7 external sources on a Raspberry Pi. Three failure scenarios need to be hardened:

1. **Hung sources** — a TCP connection establishes but no response arrives; the refresh loop blocks indefinitely
2. **Slow startup** — server waits for all sources before accepting connections; Chromium fails to load on boot
3. **Repeated failures** — a failing source retries at the full TTL interval; stale data ages faster than necessary

## Design

### 1. Non-blocking Startup

`startup()` fires `_populate_cache()` as a background task instead of awaiting it. The server accepts connections immediately and returns empty-but-valid JSON until the first cache fill completes. `_populate_cache` logic is unchanged — all sources run concurrently via `gather(return_exceptions=True)`.

### 2. Explicit Per-Source HTTP Timeouts

Standardize `timeout=` on every `httpx.AsyncClient`:

| Source | Timeout | Reason |
|---|---|---|
| `sources/icloud.py` | `20.0s` | 3 sequential requests per call |
| `sources/calendar.py` | `20.0s` | arbitrary ICS feeds can be slow |
| `sources/ms365.py` | `30.0s` | token fetch + calendar fetch sequential |
| `sources/weather.py` OpenMeteo / METno | `30.0s` (already set) | no change |
| `sources/homeassistant.py` | `10.0s` (already set per entity) | no change |

`_refresh_loop` additionally wraps each `fetch_fn()` call in `asyncio.wait_for(..., timeout=60)` as a hard ceiling, catching hangs that survive the httpx timeout (e.g. DNS stalls, OS-level TCP queue backup under CPU pressure).

### 3. Remove AccuWeather

AccuWeather is no longer supported. Remove:
- `AccuWeatherProvider` class and `_AW_ICON_KEYS` map from `sources/weather.py`
- `accuweather` provider branch in `get_forecast()`
- `accuweatherApiKey` field from `config.example.json`

### 4. Resilient Refresh Loop with Exponential Backoff

Replace the current fixed-sleep `_refresh_loop` with a version that tracks consecutive failures:

```
success  → reset backoff; sleep(ttl); fetch again
failure  → sleep(backoff); backoff = min(backoff * 2, ttl); retry
timeout  → treated identically to failure
```

Initial backoff: `10s`. Cap: source TTL. Backoff resets to `10s` on the next success.

Log levels:
- `logger.exception(...)` on unexpected errors (unchanged)
- `logger.warning(...)` on `asyncio.TimeoutError` — expected under load, not a crash

Cache behavior is unchanged: `/api/data` always returns stale data via `return_stale=True`; the backoff only affects retry cadence.

## Files Changed

| File | Change |
|---|---|
| `main.py` | Non-blocking startup; resilient `_refresh_loop` with backoff + `wait_for` |
| `sources/icloud.py` | Add `timeout=20.0` |
| `sources/calendar.py` | Add `timeout=20.0` to both `AsyncClient` uses |
| `sources/ms365.py` | Add `timeout=30.0` |
| `sources/weather.py` | Remove AccuWeather; OpenMeteo/METno unchanged |
| `config.example.json` | Remove `accuweatherApiKey` field |

## Non-Goals

- Circuit breaker / source disabling after N failures
- Per-source configurable timeouts
- Frontend indication of stale data
