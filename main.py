import asyncio
import glob
import logging
import os
import subprocess
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

_PRAGUE = ZoneInfo("Europe/Prague")

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from cache import Cache
from config import load_config
from models import DashboardData
from models import WeatherDay as WeatherDayModel
from sources.calendar import get_events, get_events_per_calendar, get_mini_cal_events
from sources.ms365 import get_ms365_events
from sources.homeassistant import get_entities, get_garden_temps, get_outdoor_temp
from sources.icloud import get_photo_url, get_photos
from sources.strava import get_strava_meals
from sources.weather import get_forecast

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_REASSERT_INTERVAL_SECONDS: int = 600  # re-issue commands every 10 min as a safety net
_LOOP_TICK_SECONDS: int = 60
_CEC_TIMEOUT_SECONDS: float = 8.0
_WLR_TIMEOUT_SECONDS: float = 5.0

_TTLS = {
    "photos": 3600,
    "events": 300,
    "mini_cal_events": 3600,
    "weather": 1800,
    "ha_entities": 60,
    "meals": 1800,
    "outdoor_temp": 60,
    "garden_temps": 60,
}

# Hard ceiling per source fetch, in seconds. Must exceed the slowest source's
# own client timeout so that timeout surfaces cleanly instead of being masked
# here. iCloud's webstream (see sources/icloud.py) can take ~50s for large
# albums, so this sits above its 90s read timeout with margin.
_FETCH_TIMEOUT: float = 120.0

# Calendar upstreams (Outlook published-ICS in particular) can reject requests
# for hours at a time. The default 1h stale window is shorter than those
# outages, so a calendar silently vanished from the dashboard instead of
# showing its last-known events. Keep calendar data servable for a day.
_CALENDAR_STALE_SECONDS: int = 86400
_DEFAULT_STALE_SECONDS: int = 3600
_CALENDAR_CACHE_KEYS: frozenset[str] = frozenset({"events", "mini_cal_events"})


def _stale_seconds_for(key: str) -> int:
    """How long a cache key stays servable past its TTL when refreshes keep failing."""
    if key in _CALENDAR_CACHE_KEYS:
        return _CALENDAR_STALE_SECONDS
    return _DEFAULT_STALE_SECONDS


def _backoff_delay(consecutive_failures: int, ttl: int) -> float:
    if consecutive_failures == 0:
        return ttl
    return min(10 * (2 ** (consecutive_failures - 1)), ttl)


def _wayland_env() -> dict[str, str] | None:
    runtime_dir = f"/run/user/{os.getuid()}"
    sockets = [
        s for s in sorted(glob.glob(f"{runtime_dir}/wayland-*"))
        if not s.endswith(".lock")
    ]
    if not sockets:
        return None
    return {
        **os.environ,
        "XDG_RUNTIME_DIR": runtime_dir,
        "WAYLAND_DISPLAY": os.path.basename(sockets[0]),
    }


def _primary_output_name(env: dict[str, str]) -> str | None:
    result = subprocess.run(
        ["wlr-randr"], env=env, capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        return None
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    return first_line.split()[0] if first_line else None


def _cec_set_power(sleep: bool) -> str:
    # cec-client reads commands from stdin. "standby 0" / "on 0" target the TV (logical address 0).
    stdin_bytes = b"standby 0\n" if sleep else b"on 0\n"
    try:
        result = subprocess.run(
            ["cec-client", "-s", "-d", "1"],
            input=stdin_bytes,
            capture_output=True,
            timeout=_CEC_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return "missing"
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception as exc:
        logger.warning("cec-client failed: %s", exc)
        return "error"
    if result.returncode != 0:
        logger.warning(
            "cec-client returned %d: %s",
            result.returncode,
            result.stderr.decode(errors="replace").strip(),
        )
        return "error"
    return "ok"


def _wlr_set_power(sleep: bool) -> str:
    env = _wayland_env()
    if env is None:
        return "no-wayland"
    output = _primary_output_name(env)
    if output is None:
        return "no-output"
    state = "--off" if sleep else "--on"
    try:
        subprocess.run(
            ["wlr-randr", "--output", output, state],
            env=env, check=True, capture_output=True, timeout=_WLR_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return "missing"
    except subprocess.CalledProcessError as exc:
        logger.warning("wlr-randr %s failed: %s", state, exc.stderr.decode(errors="replace").strip())
        return "error"
    except Exception as exc:
        logger.warning("wlr-randr %s raised: %s", state, exc)
        return "error"
    return "ok"


def create_app(config_path: str = "config.json") -> FastAPI:
    config = load_config(config_path)
    cache = Cache()
    app = FastAPI()

    app.mount("/static/css", StaticFiles(directory="static/css"), name="static-css")
    app.mount("/static/js", StaticFiles(directory="static/js"), name="static-js")

    def _to_weather_models(forecast: list) -> list[WeatherDayModel]:
        return [
            WeatherDayModel(
                date=w.date,
                icon=w.icon,
                temp_high=w.temp_high,
                temp_low=w.temp_low,
                precip_percent=w.precip_percent,
            )
            for w in forecast
        ]

    async def _populate_cache() -> None:
        photos, ics_events, ms365_events, mini_cal, forecast, ha, meals, outdoor_temp, garden_temps = await asyncio.gather(
            get_photos(config),
            get_events(config),
            get_ms365_events(config),
            get_mini_cal_events(config),
            get_forecast(config),
            get_entities(config),
            get_strava_meals(config),
            get_outdoor_temp(config),
            get_garden_temps(config),
            return_exceptions=True,
        )
        if not isinstance(photos, BaseException):
            cache.set("photos", photos, _TTLS["photos"])
        merged_events = []
        if not isinstance(ics_events, BaseException):
            merged_events.extend(ics_events)
        if not isinstance(ms365_events, BaseException):
            merged_events.extend(ms365_events)
        if merged_events or (not isinstance(ics_events, BaseException) and not isinstance(ms365_events, BaseException)):
            merged_events.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
            cache.set("events", merged_events, _TTLS["events"], stale_seconds=_stale_seconds_for("events"))
        if not isinstance(mini_cal, BaseException):
            cache.set("mini_cal_events", mini_cal, _TTLS["mini_cal_events"], stale_seconds=_stale_seconds_for("mini_cal_events"))
        if not isinstance(forecast, BaseException):
            cache.set("weather", _to_weather_models(forecast), _TTLS["weather"])
        if not isinstance(ha, BaseException):
            cache.set("ha_entities", ha, _TTLS["ha_entities"])
        if not isinstance(meals, BaseException):
            cache.set("meals", meals, _TTLS["meals"])
        if not isinstance(outdoor_temp, BaseException):
            cache.set("outdoor_temp", outdoor_temp, _TTLS["outdoor_temp"])
        if not isinstance(garden_temps, BaseException):
            cache.set("garden_temps", garden_temps, _TTLS["garden_temps"])

    async def _refresh_loop(key: str, fetch_fn, ttl: int) -> None:
        consecutive_failures = 0
        while True:
            await asyncio.sleep(_backoff_delay(consecutive_failures, ttl))
            try:
                value = await asyncio.wait_for(fetch_fn(), timeout=_FETCH_TIMEOUT)
                if key == "weather":
                    value = _to_weather_models(value)
                cache.set(key, value, ttl, stale_seconds=_stale_seconds_for(key))
                consecutive_failures = 0
            except asyncio.TimeoutError:  # must precede Exception; TimeoutError is a subclass of Exception
                consecutive_failures += 1
                logger.warning("Fetch timeout for %s (failure %d)", key, consecutive_failures)
            except Exception:
                consecutive_failures += 1
                logger.exception("Background refresh failed for %s (failure %d)", key, consecutive_failures)

    def _is_sleep_time() -> bool:
        cfg = config.display.sleep_hours
        if cfg is None:
            return False
        now = datetime.now(_PRAGUE).time().replace(second=0, microsecond=0)
        start = time.fromisoformat(cfg.start)
        end = time.fromisoformat(cfg.end)
        if start <= end:
            return start <= now < end
        # overnight window (e.g. 21:00 – 06:15)
        return now >= start or now < end

    async def _display_sleep_loop() -> None:
        last_state: bool | None = None
        last_applied_at: float = 0.0
        loop = asyncio.get_running_loop()
        while True:
            should_sleep = _is_sleep_time()
            now = loop.time()
            transition = should_sleep != last_state
            reassert = (now - last_applied_at) >= _REASSERT_INTERVAL_SECONDS
            if transition or reassert:
                cec_result = await asyncio.to_thread(_cec_set_power, should_sleep)
                wlr_result = await asyncio.to_thread(_wlr_set_power, should_sleep)
                logger.info(
                    "display sleep=%s cec=%s wlr=%s (transition=%s reassert=%s)",
                    "ON" if should_sleep else "OFF",
                    cec_result, wlr_result, transition, reassert,
                )
                last_state = should_sleep
                last_applied_at = now
            await asyncio.sleep(_LOOP_TICK_SECONDS)

    app.state.populate_cache = _populate_cache

    @app.on_event("startup")
    async def startup() -> None:
        async def _fetch_all_events():
            per_cal, window_start = await get_events_per_calendar(config)
            combined = []
            for i, (cal, result) in enumerate(zip(config.calendars, per_cal)):
                key = f"ics_cal_{i}"
                if isinstance(result, BaseException):
                    logger.warning("Calendar '%s' fetch failed: %s", cal.name, result)
                    combined.extend(cache.get(key, return_stale=True) or [])
                else:
                    cache.set(key, result, _TTLS["events"], stale_seconds=_CALENDAR_STALE_SECONDS)
                    combined.extend(result)

            try:
                ms365 = await get_ms365_events(config)
                cache.set("ms365_cal", ms365, _TTLS["events"], stale_seconds=_CALENDAR_STALE_SECONDS)
                combined.extend(ms365)
            except Exception as exc:
                logger.warning("MS365 calendar fetch failed: %s", exc)
                combined.extend(cache.get("ms365_cal", return_stale=True) or [])

            clamped = []
            for ev in combined:
                if ev.start < window_start < ev.end:
                    ev = ev.model_copy(update={"start": window_start})
                clamped.append(ev)
            clamped.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
            return clamped

        app.state.startup_task = asyncio.create_task(_populate_cache())
        asyncio.create_task(_refresh_loop("photos", lambda: get_photos(config), _TTLS["photos"]))
        asyncio.create_task(_refresh_loop("events", _fetch_all_events, _TTLS["events"]))
        asyncio.create_task(_refresh_loop("mini_cal_events", lambda: get_mini_cal_events(config), _TTLS["mini_cal_events"]))
        asyncio.create_task(_refresh_loop("weather", lambda: get_forecast(config), _TTLS["weather"]))
        asyncio.create_task(_refresh_loop("ha_entities", lambda: get_entities(config), _TTLS["ha_entities"]))
        asyncio.create_task(_refresh_loop("meals", lambda: get_strava_meals(config), _TTLS["meals"]))
        asyncio.create_task(_refresh_loop("outdoor_temp", lambda: get_outdoor_temp(config), _TTLS["outdoor_temp"]))
        asyncio.create_task(_refresh_loop("garden_temps", lambda: get_garden_temps(config), _TTLS["garden_temps"]))
        if config.display.sleep_hours is not None:
            asyncio.create_task(_display_sleep_loop())

    @app.get("/api/data", response_model=DashboardData)
    async def api_data() -> DashboardData:
        return DashboardData(
            photos=cache.get("photos", return_stale=True) or [],
            events=cache.get("events", return_stale=True) or [],
            mini_cal_events=cache.get("mini_cal_events", return_stale=True) or [],
            weather=cache.get("weather", return_stale=True) or [],
            ha_entities=cache.get("ha_entities", return_stale=True) or [],
            meals=cache.get("meals", return_stale=True),
            outdoor_temp=cache.get("outdoor_temp", return_stale=True),
            garden_temps=cache.get("garden_temps", return_stale=True),
            photo_interval_seconds=config.icloud.photo_interval_seconds,
            server_time=datetime.now(timezone.utc),
        )

    @app.get("/api/photo/{photo_id}")
    async def api_photo(photo_id: str) -> StreamingResponse:
        real_url = get_photo_url(photo_id)
        if real_url is None:
            raise HTTPException(status_code=404, detail="Photo not found")
        async with httpx.AsyncClient(timeout=20.0) as client:
            upstream = await client.get(real_url)
        content_type = upstream.headers.get("content-type", "image/jpeg")
        return StreamingResponse(iter([upstream.content]), media_type=content_type)

    @app.get("/{full_path:path}")
    async def serve_index(full_path: str) -> FileResponse:
        return FileResponse("static/index.html")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
