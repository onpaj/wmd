from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import load_config
from models import DashboardData
from sources.icloud import get_photo_url


def create_app(config_path: str = "config.json") -> FastAPI:
    config = load_config(config_path)
    app = FastAPI()

    app.mount("/static/css", StaticFiles(directory="static/css"), name="static-css")
    app.mount("/static/js", StaticFiles(directory="static/js"), name="static-js")

    @app.get("/api/data", response_model=DashboardData)
    async def api_data() -> DashboardData:
        return DashboardData(
            photos=[],
            events=[],
            weather=[],
            ha_entities=[],
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
