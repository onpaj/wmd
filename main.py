from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import load_config
from models import DashboardData


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

    @app.get("/{full_path:path}")
    async def serve_index(full_path: str) -> FileResponse:
        return FileResponse("static/index.html")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
