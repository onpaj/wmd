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
from sources.calendar import get_events
from sources.homeassistant import get_entities
from sources.icloud import get_photo_url, get_photos
from sources.weather import get_forecast

logger = logging.getLogger(__name__)

_TTLS = {
    "photos": 3600,
    "events": 300,
    "weather": 1800,
    "ha_entities": 60,
}


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
        photos, events, forecast, ha = await asyncio.gather(
            get_photos(config),
            get_events(config),
            get_forecast(config),
            get_entities(config),
            return_exceptions=True,
        )
        if not isinstance(photos, BaseException):
            cache.set("photos", photos, _TTLS["photos"])
        if not isinstance(events, BaseException):
            cache.set("events", events, _TTLS["events"])
        if not isinstance(forecast, BaseException):
            cache.set("weather", _to_weather_models(forecast), _TTLS["weather"])
        if not isinstance(ha, BaseException):
            cache.set("ha_entities", ha, _TTLS["ha_entities"])

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

    app.state.populate_cache = _populate_cache

    @app.on_event("startup")
    async def startup() -> None:
        await _populate_cache()
        asyncio.create_task(_refresh_loop("photos", lambda: get_photos(config), _TTLS["photos"]))
        asyncio.create_task(_refresh_loop("events", lambda: get_events(config), _TTLS["events"]))
        asyncio.create_task(_refresh_loop("weather", lambda: get_forecast(config), _TTLS["weather"]))
        asyncio.create_task(_refresh_loop("ha_entities", lambda: get_entities(config), _TTLS["ha_entities"]))

    @app.get("/api/data", response_model=DashboardData)
    async def api_data() -> DashboardData:
        return DashboardData(
            photos=cache.get("photos", return_stale=True) or [],
            events=cache.get("events", return_stale=True) or [],
            weather=cache.get("weather", return_stale=True) or [],
            ha_entities=cache.get("ha_entities", return_stale=True) or [],
            photo_interval_seconds=config.icloud.photo_interval_seconds,
            server_time=datetime.now(timezone.utc),
        )

    @app.get("/api/photo/{photo_id}")
    async def api_photo(photo_id: str) -> StreamingResponse:
        real_url = get_photo_url(photo_id)
        if real_url is None:
            raise HTTPException(status_code=404, detail="Photo not found")
        async with httpx.AsyncClient() as client:
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
