import asyncio
import logging
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from cache import Cache
from config import load_config
from models import DashboardData
from models import WeatherDay as WeatherDayModel
from sources.calendar import get_events, get_mini_cal_events
from sources.ms365 import get_ms365_events
from sources.homeassistant import get_entities, get_meals, get_outdoor_temp
from sources.icloud import get_photo_url, get_photos
from sources.weather import get_forecast

logger = logging.getLogger(__name__)

_TTLS = {
    "photos": 3600,
    "events": 300,
    "mini_cal_events": 3600,
    "weather": 1800,
    "ha_entities": 60,
    "meals": 300,
    "outdoor_temp": 60,
}

_FETCH_TIMEOUT: float = 60.0  # hard ceiling per source fetch, in seconds


def _backoff_delay(consecutive_failures: int, ttl: int) -> float:
    if consecutive_failures == 0:
        return ttl
    return min(10 * (2 ** (consecutive_failures - 1)), ttl)


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
        photos, ics_events, ms365_events, mini_cal, forecast, ha, meals, outdoor_temp = await asyncio.gather(
            get_photos(config),
            get_events(config),
            get_ms365_events(config),
            get_mini_cal_events(config),
            get_forecast(config),
            get_entities(config),
            get_meals(config),
            get_outdoor_temp(config),
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
            cache.set("events", merged_events, _TTLS["events"])
        if not isinstance(mini_cal, BaseException):
            cache.set("mini_cal_events", mini_cal, _TTLS["mini_cal_events"])
        if not isinstance(forecast, BaseException):
            cache.set("weather", _to_weather_models(forecast), _TTLS["weather"])
        if not isinstance(ha, BaseException):
            cache.set("ha_entities", ha, _TTLS["ha_entities"])
        if not isinstance(meals, BaseException):
            cache.set("meals", meals, _TTLS["meals"])
        if not isinstance(outdoor_temp, BaseException):
            cache.set("outdoor_temp", outdoor_temp, _TTLS["outdoor_temp"])

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
            except asyncio.TimeoutError:  # must precede Exception; TimeoutError is a subclass of Exception
                consecutive_failures += 1
                logger.warning("Fetch timeout for %s (failure %d)", key, consecutive_failures)
            except Exception:
                consecutive_failures += 1
                logger.exception("Background refresh failed for %s (failure %d)", key, consecutive_failures)

    app.state.populate_cache = _populate_cache

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

        app.state.startup_task = asyncio.create_task(_populate_cache())
        asyncio.create_task(_refresh_loop("photos", lambda: get_photos(config), _TTLS["photos"]))
        asyncio.create_task(_refresh_loop("events", _fetch_all_events, _TTLS["events"]))
        asyncio.create_task(_refresh_loop("mini_cal_events", lambda: get_mini_cal_events(config), _TTLS["mini_cal_events"]))
        asyncio.create_task(_refresh_loop("weather", lambda: get_forecast(config), _TTLS["weather"]))
        asyncio.create_task(_refresh_loop("ha_entities", lambda: get_entities(config), _TTLS["ha_entities"]))
        asyncio.create_task(_refresh_loop("meals", lambda: get_meals(config), _TTLS["meals"]))
        asyncio.create_task(_refresh_loop("outdoor_temp", lambda: get_outdoor_temp(config), _TTLS["outdoor_temp"]))

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
