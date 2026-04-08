# WMD Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted wall dashboard on Raspberry Pi (Ubuntu Server) showing iCloud photos, merged calendars, weather, clock, and Home Assistant data — served by a FastAPI backend with a TypeScript frontend in Chromium kiosk mode.

**Architecture:** Python/FastAPI backend fetches and caches all external data (iCloud, ICS feeds, Open-Meteo, Home Assistant) and serves a single `/api/data` endpoint. TypeScript frontend compiled with esbuild polls that endpoint every 60 seconds and updates the DOM in-place — no flicker, no page reloads. Two systemd services auto-start on boot.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, httpx, icalendar, python-dateutil, pytest, respx, pytest-asyncio; TypeScript, esbuild; Chromium kiosk; systemd on Ubuntu Server (RPi).

---

## File Map

```
/home/pi/wmd/
├── main.py                        # FastAPI app, routes, startup
├── models.py                      # Pydantic response models
├── config.py                      # Config loading + validation
├── cache.py                       # In-memory TTL cache with bg refresh
├── sources/
│   ├── __init__.py
│   ├── icloud.py                  # iCloud shared album fetcher
│   ├── calendar.py                # ICS fetcher + parser + merger
│   ├── weather.py                 # Abstract WeatherProvider + OpenMeteo + AccuWeather
│   └── homeassistant.py           # HA REST API fetcher
├── tests/
│   ├── conftest.py                # shared fixtures
│   ├── test_cache.py
│   ├── test_calendar.py
│   ├── test_weather.py
│   ├── test_icloud.py
│   ├── test_homeassistant.py
│   └── test_api.py
├── src/
│   ├── types.ts                   # Shared TS interfaces
│   ├── api.ts                     # fetchData() wrapper
│   ├── app.ts                     # Entry point + polling loop
│   └── modules/
│       ├── clock.ts
│       ├── photo.ts
│       ├── calendar.ts
│       ├── weather.ts
│       └── mini-calendar.ts
├── static/
│   ├── index.html
│   ├── js/app.js                  # compiled output
│   └── css/
│       ├── base.css
│       ├── photo.css
│       ├── calendar.css
│       ├── clock.css
│       ├── weather.css
│       └── mini-calendar.css
├── systemd/
│   ├── wmd-server.service
│   └── wmd-browser.service
├── config.json                    # User config (not committed)
├── config.example.json            # Template committed to repo
├── requirements.txt
├── package.json
└── README.md
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `package.json`
- Create: `config.example.json`
- Create: `config.json` (gitignored)
- Create: `.gitignore`
- Create: `sources/__init__.py`
- Create: `tests/` directory

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p sources tests src/modules static/js static/css systemd docs/superpowers/plans docs/superpowers/specs tasks
touch sources/__init__.py
```

- [ ] **Step 2: Create `requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.0
icalendar==5.0.12
python-dateutil==2.9.0
respx==0.21.1
pytest==8.2.0
pytest-asyncio==0.23.7
```

- [ ] **Step 3: Create `package.json`**

```json
{
  "scripts": {
    "build": "esbuild src/app.ts --bundle --outfile=static/js/app.js --minify",
    "watch": "esbuild src/app.ts --bundle --outfile=static/js/app.js --watch"
  },
  "devDependencies": {
    "esbuild": "^0.20.0",
    "typescript": "^5.4.0"
  }
}
```

- [ ] **Step 4: Create `tsconfig.json`** (for IDE support only — esbuild handles compilation)

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "lib": ["ES2020", "DOM"]
  },
  "include": ["src/**/*"]
}
```

- [ ] **Step 5: Create `config.example.json`**

```json
{
  "icloud": {
    "shareToken": "YOUR_ICLOUD_SHARE_TOKEN_HERE",
    "photoIntervalSeconds": 30
  },
  "calendars": [
    { "name": "Family", "url": "https://p123-caldav.icloud.com/published/2/...", "color": "#4CAF50" },
    { "name": "Work",   "url": "https://outlook.office365.com/owa/calendar/.../reachcalendar.ics", "color": "#F44336" }
  ],
  "weather": {
    "provider": "openmeteo",
    "latitude": 50.07,
    "longitude": 14.43,
    "accuweatherApiKey": ""
  },
  "homeAssistant": {
    "url": "http://homeassistant.local:8123",
    "token": "YOUR_HA_LONG_LIVED_TOKEN",
    "entities": [
      { "id": "sensor.living_room_temperature", "label": "Obývák" }
    ]
  },
  "display": {
    "calendarDaysAhead": 2,
    "weatherDays": 5
  }
}
```

- [ ] **Step 6: Copy example to working config**

```bash
cp config.example.json config.json
```

- [ ] **Step 7: Create `.gitignore`**

```
config.json
.venv/
__pycache__/
*.pyc
node_modules/
static/js/app.js
```

- [ ] **Step 8: Create Python venv and install deps**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 9: Install Node deps**

```bash
npm install
```

- [ ] **Step 10: Commit**

```bash
git init
git add requirements.txt package.json tsconfig.json config.example.json .gitignore sources/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: Pydantic Models

**Files:**
- Create: `models.py`

- [ ] **Step 1: Create `models.py`**

```python
from pydantic import BaseModel
from datetime import datetime


class Photo(BaseModel):
    id: str
    url: str  # proxied URL: /api/photo/{id}


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    calendar_name: str
    color: str  # hex, e.g. "#4CAF50"


class WeatherDay(BaseModel):
    date: str          # "YYYY-MM-DD"
    icon: str          # normalized: sunny|partly-cloudy|cloudy|rainy|heavy-rain|snow|storm|fog
    temp_high: float   # Celsius
    temp_low: float    # Celsius
    precip_percent: int  # 0-100


class HaEntity(BaseModel):
    id: str
    label: str
    state: str
    unit: str


class DashboardData(BaseModel):
    photos: list[Photo]
    events: list[CalendarEvent]
    weather: list[WeatherDay]
    ha_entities: list[HaEntity]
    photo_interval_seconds: int
    server_time: datetime
```

- [ ] **Step 2: Verify models parse correctly**

```bash
source .venv/bin/activate
python3 -c "from models import DashboardData; print('models OK')"
```

Expected output: `models OK`

- [ ] **Step 3: Commit**

```bash
git add models.py
git commit -m "feat: add Pydantic response models"
```

---

## Task 3: Config Loading

**Files:**
- Create: `config.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import pytest
from config import load_config, AppConfig


def test_load_config_returns_typed_object(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("""{
        "icloud": {"shareToken": "abc", "photoIntervalSeconds": 30},
        "calendars": [{"name": "A", "url": "https://example.com/cal.ics", "color": "#fff"}],
        "weather": {"provider": "openmeteo", "latitude": 50.0, "longitude": 14.0, "accuweatherApiKey": ""},
        "homeAssistant": {"url": "http://ha.local:8123", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5}
    }""")
    cfg = load_config(str(cfg_file))
    assert cfg.icloud.share_token == "abc"
    assert cfg.icloud.photo_interval_seconds == 30
    assert cfg.calendars[0].name == "A"
    assert cfg.weather.provider == "openmeteo"
    assert cfg.display.calendar_days_ahead == 2
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
source .venv/bin/activate
pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Create `config.py`**

```python
import json
from dataclasses import dataclass


@dataclass
class ICloudConfig:
    share_token: str
    photo_interval_seconds: int


@dataclass
class CalendarConfig:
    name: str
    url: str
    color: str


@dataclass
class WeatherConfig:
    provider: str  # "openmeteo" or "accuweather"
    latitude: float
    longitude: float
    accuweather_api_key: str


@dataclass
class HaEntityConfig:
    id: str
    label: str


@dataclass
class HomeAssistantConfig:
    url: str
    token: str
    entities: list[HaEntityConfig]


@dataclass
class DisplayConfig:
    calendar_days_ahead: int
    weather_days: int


@dataclass
class AppConfig:
    icloud: ICloudConfig
    calendars: list[CalendarConfig]
    weather: WeatherConfig
    home_assistant: HomeAssistantConfig
    display: DisplayConfig


def load_config(path: str = "config.json") -> AppConfig:
    with open(path) as f:
        raw = json.load(f)

    return AppConfig(
        icloud=ICloudConfig(
            share_token=raw["icloud"]["shareToken"],
            photo_interval_seconds=raw["icloud"]["photoIntervalSeconds"],
        ),
        calendars=[
            CalendarConfig(name=c["name"], url=c["url"], color=c["color"])
            for c in raw["calendars"]
        ],
        weather=WeatherConfig(
            provider=raw["weather"]["provider"],
            latitude=raw["weather"]["latitude"],
            longitude=raw["weather"]["longitude"],
            accuweather_api_key=raw["weather"].get("accuweatherApiKey", ""),
        ),
        home_assistant=HomeAssistantConfig(
            url=raw["homeAssistant"]["url"],
            token=raw["homeAssistant"]["token"],
            entities=[
                HaEntityConfig(id=e["id"], label=e["label"])
                for e in raw["homeAssistant"]["entities"]
            ],
        ),
        display=DisplayConfig(
            calendar_days_ahead=raw["display"]["calendarDaysAhead"],
            weather_days=raw["display"]["weatherDays"],
        ),
    )
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import pytest
import json
import os


@pytest.fixture
def sample_config(tmp_path):
    cfg = {
        "icloud": {"shareToken": "testtoken", "photoIntervalSeconds": 30},
        "calendars": [
            {"name": "Family", "url": "https://example.com/family.ics", "color": "#4CAF50"},
            {"name": "Work", "url": "https://example.com/work.ics", "color": "#F44336"},
        ],
        "weather": {
            "provider": "openmeteo",
            "latitude": 50.07,
            "longitude": 14.43,
            "accuweatherApiKey": "accu_key_123",
        },
        "homeAssistant": {
            "url": "http://ha.local:8123",
            "token": "ha_token_123",
            "entities": [
                {"id": "sensor.living_room_temperature", "label": "Obývák"}
            ],
        },
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    return str(path)
```

- [ ] **Step 5: Run tests to confirm pass**

```bash
pytest tests/test_config.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add config.py tests/test_config.py tests/conftest.py
git commit -m "feat: add config loader"
```

---

## Task 4: Cache Layer

**Files:**
- Create: `cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cache.py
import asyncio
import time
import pytest
from cache import Cache


def test_set_and_get():
    c = Cache()
    c.set("key", "value", ttl_seconds=60)
    assert c.get("key") == "value"


def test_get_missing_returns_none():
    c = Cache()
    assert c.get("missing") is None


def test_expired_returns_none():
    c = Cache()
    c.set("key", "value", ttl_seconds=0)
    time.sleep(0.01)
    assert c.get("key") is None


def test_stale_returns_last_value_when_flagged():
    c = Cache()
    c.set("key", "old_value", ttl_seconds=0)
    time.sleep(0.01)
    assert c.get("key", return_stale=True) == "old_value"


def test_overwrite():
    c = Cache()
    c.set("key", "first", ttl_seconds=60)
    c.set("key", "second", ttl_seconds=60)
    assert c.get("key") == "second"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_cache.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `cache.py`**

```python
import time
from typing import Any


class Cache:
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires_at = time.monotonic() + ttl_seconds
        self._store[key] = (value, expires_at)

    def get(self, key: str, return_stale: bool = False) -> Any:
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.monotonic() < expires_at:
            return value
        if return_stale:
            return value
        return None

    def is_expired(self, key: str) -> bool:
        if key not in self._store:
            return True
        _, expires_at = self._store[key]
        return time.monotonic() >= expires_at
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/test_cache.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add cache.py tests/test_cache.py
git commit -m "feat: in-memory TTL cache"
```

---

## Task 5: FastAPI Skeleton with Mock `/api/data`

**Files:**
- Create: `main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import create_app
from config import load_config


@pytest.fixture
def app(sample_config):
    return create_app(sample_config)


@pytest.mark.asyncio
async def test_api_data_returns_200(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/data")
    assert resp.status_code == 200
    data = resp.json()
    assert "photos" in data
    assert "events" in data
    assert "weather" in data
    assert "ha_entities" in data
    assert "photo_interval_seconds" in data
    assert "server_time" in data


@pytest.mark.asyncio
async def test_static_index_served(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
```

- [ ] **Step 2: Create `pytest.ini`** (needed for asyncio mode)

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: Run test to confirm failure**

```bash
pytest tests/test_api.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Create `main.py`**

```python
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import AppConfig, load_config
from models import DashboardData, Photo, CalendarEvent, WeatherDay, HaEntity
from cache import Cache

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config_path: str = "config.json") -> FastAPI:
    cfg = load_config(config_path)
    cache = Cache()
    app = FastAPI()

    @app.get("/api/data", response_model=DashboardData)
    async def get_data():
        return DashboardData(
            photos=[],
            events=[],
            weather=[],
            ha_entities=[],
            photo_interval_seconds=cfg.icloud.photo_interval_seconds,
            server_time=datetime.now(timezone.utc),
        )

    @app.get("/api/photo/{photo_id}")
    async def get_photo(photo_id: str):
        # implemented in Task 6
        return {"error": "not implemented"}

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR / "css"), html=False), name="css")
    app.mount("/js", StaticFiles(directory=str(STATIC_DIR / "js"), html=False), name="js")

    @app.get("/{full_path:path}")
    async def serve_index(full_path: str):
        return FileResponse(str(STATIC_DIR / "index.html"))

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=False)
```

- [ ] **Step 5: Create a minimal `static/index.html`** (will be replaced in Task 11)

```html
<!DOCTYPE html>
<html lang="cs">
<head><meta charset="UTF-8"><title>WMD</title></head>
<body><p>WMD loading...</p></body>
</html>
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_api.py -v
```

Expected: 2 passed

- [ ] **Step 7: Smoke test manually**

```bash
python3 main.py &
curl http://localhost:3000/api/data
kill %1
```

Expected: JSON with empty arrays

- [ ] **Step 8: Commit**

```bash
git add main.py pytest.ini static/index.html tests/test_api.py
git commit -m "feat: FastAPI skeleton with mock /api/data"
```

---

## Task 6: iCloud Photos Source

**Files:**
- Create: `sources/icloud.py`
- Create: `tests/test_icloud.py`

Background: iCloud shared albums expose a two-step undocumented API. Step 1: POST `{"streamCtag": null}` to get the photo asset list. The response may include `X-Apple-MMe-Host` header redirecting to a specific server. Step 2: POST the photo checksums to `/webasseturls` to get download URLs.

- [ ] **Step 1: Write failing test**

```python
# tests/test_icloud.py
import pytest
import respx
import httpx
from sources.icloud import get_photos
from config import load_config


WEBSTREAM_RESPONSE = {
    "photos": [
        {
            "photoGuid": "guid1",
            "derivatives": {
                "2": {"checksum": "chk1", "fileSize": 12345, "width": 1920, "height": 1080}
            }
        },
        {
            "photoGuid": "guid2",
            "derivatives": {
                "2": {"checksum": "chk2", "fileSize": 23456, "width": 1920, "height": 1080}
            }
        }
    ]
}

WEBASSETURLS_RESPONSE = {
    "items": {
        "chk1": {"url_location": "https://cvws.icloud-content.com/B/photo1.jpg"},
        "chk2": {"url_location": "https://cvws.icloud-content.com/B/photo2.jpg"},
    }
}


@pytest.mark.asyncio
@respx.mock
async def test_get_photos_returns_photo_list(sample_config):
    cfg = load_config(sample_config)
    token = cfg.icloud.share_token

    respx.post(
        f"https://p00-sharedstreams.icloud.com/{token}/sharedstreams/webstream"
    ).mock(return_value=httpx.Response(200, json=WEBSTREAM_RESPONSE))

    respx.post(
        f"https://p00-sharedstreams.icloud.com/{token}/sharedstreams/webasseturls"
    ).mock(return_value=httpx.Response(200, json=WEBASSETURLS_RESPONSE))

    photos = await get_photos(cfg)
    assert len(photos) == 2
    assert photos[0].id == "guid1"
    assert "/api/photo/guid1" in photos[0].url


@pytest.mark.asyncio
@respx.mock
async def test_get_photos_handles_empty_album(sample_config):
    cfg = load_config(sample_config)
    token = cfg.icloud.share_token

    respx.post(
        f"https://p00-sharedstreams.icloud.com/{token}/sharedstreams/webstream"
    ).mock(return_value=httpx.Response(200, json={"photos": []}))

    respx.post(
        f"https://p00-sharedstreams.icloud.com/{token}/sharedstreams/webasseturls"
    ).mock(return_value=httpx.Response(200, json={"items": {}}))

    photos = await get_photos(cfg)
    assert photos == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_icloud.py -v
```

Expected: FAIL

- [ ] **Step 3: Create `sources/icloud.py`**

```python
import httpx
from models import Photo
from config import AppConfig

BASE_URL = "https://p00-sharedstreams.icloud.com"

# Maps photo guid -> iCloud download URL (populated by fetch, used by proxy endpoint)
_photo_url_map: dict[str, str] = {}


async def get_photos(cfg: AppConfig) -> list[Photo]:
    token = cfg.icloud.share_token
    base = BASE_URL

    async with httpx.AsyncClient(timeout=15) as client:
        # Step 1: get asset list
        resp = await client.post(
            f"{base}/{token}/sharedstreams/webstream",
            json={"streamCtag": None},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()

        # Follow X-Apple-MMe-Host redirect if present
        if mme_host := resp.headers.get("X-Apple-MMe-Host"):
            base = f"https://{mme_host}"
            resp = await client.post(
                f"{base}/{token}/sharedstreams/webstream",
                json={"streamCtag": None},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()

        data = resp.json()
        photos_raw = data.get("photos", [])
        if not photos_raw:
            return []

        # Pick best derivative (key "2" = large)
        checksums = []
        guid_to_checksum: dict[str, str] = {}
        for p in photos_raw:
            derivs = p.get("derivatives", {})
            chk = (derivs.get("2") or next(iter(derivs.values()), {})).get("checksum")
            if chk:
                checksums.append(chk)
                guid_to_checksum[p["photoGuid"]] = chk

        if not checksums:
            return []

        # Step 2: get download URLs
        url_resp = await client.post(
            f"{base}/{token}/sharedstreams/webasseturls",
            json={"photoGuids": list(guid_to_checksum.keys())},
            headers={"Content-Type": "application/json"},
        )
        url_resp.raise_for_status()
        items = url_resp.json().get("items", {})

    # Store mapping for proxy endpoint
    checksum_to_url = {chk: item["url_location"] for chk, item in items.items()}
    global _photo_url_map
    _photo_url_map = {
        guid: checksum_to_url[chk]
        for guid, chk in guid_to_checksum.items()
        if chk in checksum_to_url
    }

    return [
        Photo(id=guid, url=f"/api/photo/{guid}")
        for guid in _photo_url_map
    ]


def get_photo_url(photo_id: str) -> str | None:
    return _photo_url_map.get(photo_id)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_icloud.py -v
```

Expected: 2 passed

- [ ] **Step 5: Add photo proxy to `main.py`** — update the `get_photo` endpoint:

```python
# In main.py, update get_photo endpoint:
from sources.icloud import get_photo_url
import httpx as _httpx
from fastapi.responses import StreamingResponse

@app.get("/api/photo/{photo_id}")
async def get_photo(photo_id: str):
    url = get_photo_url(photo_id)
    if not url:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Photo not found")
    async with _httpx.AsyncClient() as client:
        r = await client.get(url)
        return StreamingResponse(
            content=iter([r.content]),
            media_type=r.headers.get("content-type", "image/jpeg"),
        )
```

- [ ] **Step 6: Commit**

```bash
git add sources/icloud.py tests/test_icloud.py main.py
git commit -m "feat: iCloud shared album photo source"
```

---

## Task 7: Calendar Source

**Files:**
- Create: `sources/calendar.py`
- Create: `tests/test_calendar.py`
- Create: `tests/fixtures/simple.ics`
- Create: `tests/fixtures/recurring.ics`

- [ ] **Step 1: Create ICS fixture files**

`tests/fixtures/simple.ics`:
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:simple1@test
DTSTART:20260407T080000Z
DTEND:20260407T090000Z
SUMMARY:Trh Dka
END:VEVENT
BEGIN:VEVENT
UID:simple2@test
DTSTART:20260407
DTEND:20260408
SUMMARY:Celodení akce
X-MICROSOFT-CDO-ALLDAYEVENT:TRUE
END:VEVENT
END:VCALENDAR
```

`tests/fixtures/recurring.ics`:
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:recurring1@test
DTSTART:20260401T090000Z
DTEND:20260401T093000Z
RRULE:FREQ=DAILY;COUNT=30
SUMMARY:Standup
END:VEVENT
END:VCALENDAR
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_calendar.py
import pytest
import respx
import httpx
from pathlib import Path
from datetime import date
from sources.calendar import get_events
from config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_parses_simple_events(sample_config):
    cfg = load_config(sample_config)
    ics_content = (FIXTURES / "simple.ics").read_bytes()
    respx.get("https://example.com/family.ics").mock(
        return_value=httpx.Response(200, content=ics_content)
    )
    respx.get("https://example.com/work.ics").mock(
        return_value=httpx.Response(200, content=b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
    )
    events = await get_events(cfg)
    titles = [e.title for e in events]
    assert "Trh Dka" in titles


@pytest.mark.asyncio
@respx.mock
async def test_all_day_events_flagged(sample_config):
    cfg = load_config(sample_config)
    ics_content = (FIXTURES / "simple.ics").read_bytes()
    respx.get("https://example.com/family.ics").mock(
        return_value=httpx.Response(200, content=ics_content)
    )
    respx.get("https://example.com/work.ics").mock(
        return_value=httpx.Response(200, content=b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
    )
    events = await get_events(cfg)
    all_day = [e for e in events if e.all_day]
    assert any(e.title == "Celodení akce" for e in all_day)


@pytest.mark.asyncio
@respx.mock
async def test_recurring_events_expanded(sample_config):
    cfg = load_config(sample_config)
    ics_content = (FIXTURES / "recurring.ics").read_bytes()
    respx.get("https://example.com/family.ics").mock(
        return_value=httpx.Response(200, content=ics_content)
    )
    respx.get("https://example.com/work.ics").mock(
        return_value=httpx.Response(200, content=b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
    )
    events = await get_events(cfg)
    standup_events = [e for e in events if e.title == "Standup"]
    # Should have at least 1 occurrence within today + 2 days window
    assert len(standup_events) >= 1


@pytest.mark.asyncio
@respx.mock
async def test_calendar_color_assigned(sample_config):
    cfg = load_config(sample_config)
    ics_content = (FIXTURES / "simple.ics").read_bytes()
    respx.get("https://example.com/family.ics").mock(
        return_value=httpx.Response(200, content=ics_content)
    )
    respx.get("https://example.com/work.ics").mock(
        return_value=httpx.Response(200, content=b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
    )
    events = await get_events(cfg)
    family_events = [e for e in events if e.calendar_name == "Family"]
    assert all(e.color == "#4CAF50" for e in family_events)
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_calendar.py -v
```

Expected: FAIL

- [ ] **Step 4: Create `sources/calendar.py`**

```python
import hashlib
from datetime import datetime, date, timedelta, timezone
from typing import Union

import httpx
from icalendar import Calendar, Event
from dateutil.rrule import rruleset, rrulestr

from models import CalendarEvent
from config import AppConfig


def _to_datetime(val: Union[datetime, date]) -> datetime:
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    # date only
    return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)


def _is_all_day(dtstart) -> bool:
    return isinstance(dtstart, date) and not isinstance(dtstart, datetime)


def _expand_event(
    component: Event,
    window_start: datetime,
    window_end: datetime,
    cal_name: str,
    color: str,
) -> list[CalendarEvent]:
    dtstart_raw = component.get("DTSTART").dt
    dtend_raw = component.get("DTEND", component.get("DURATION"))
    all_day = _is_all_day(dtstart_raw)

    dtstart = _to_datetime(dtstart_raw)
    if hasattr(dtend_raw, "dt"):
        dtend = _to_datetime(dtend_raw.dt)
    else:
        dtend = dtstart + timedelta(hours=1)

    duration = dtend - dtstart
    uid = str(component.get("UID", ""))
    summary = str(component.get("SUMMARY", "(bez názvu)"))
    rrule_prop = component.get("RRULE")

    occurrences: list[datetime] = []

    if rrule_prop:
        rule_str = rrule_prop.to_ical().decode()
        rs = rruleset()
        rs.rrule(rrulestr(f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%SZ')}\nRRULE:{rule_str}"))
        for exdate in component.get("EXDATE", []):
            for ex in (exdate if hasattr(exdate, "__iter__") else [exdate]):
                rs.exdate(_to_datetime(ex.dt))
        occurrences = list(rs.between(window_start, window_end, inc=True))
    else:
        if window_start <= dtstart <= window_end:
            occurrences = [dtstart]

    results = []
    for occ in occurrences:
        event_id = hashlib.md5(f"{uid}{occ.isoformat()}".encode()).hexdigest()
        results.append(CalendarEvent(
            id=event_id,
            title=summary,
            start=occ,
            end=occ + duration,
            all_day=all_day,
            calendar_name=cal_name,
            color=color,
        ))
    return results


async def get_events(cfg: AppConfig) -> list[CalendarEvent]:
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = now + timedelta(days=cfg.display.calendar_days_ahead + 1)

    all_events: list[CalendarEvent] = []

    async with httpx.AsyncClient(timeout=10) as client:
        for cal_cfg in cfg.calendars:
            try:
                resp = await client.get(cal_cfg.url)
                resp.raise_for_status()
                cal = Calendar.from_ical(resp.content)
                for component in cal.walk():
                    if component.name == "VEVENT":
                        all_events.extend(
                            _expand_event(component, now, window_end, cal_cfg.name, cal_cfg.color)
                        )
            except Exception:
                continue  # skip broken feeds, stale cache handles it

    # Sort: all-day first within each day, then by start time
    all_events.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
    return all_events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_calendar.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add sources/calendar.py tests/test_calendar.py tests/fixtures/simple.ics tests/fixtures/recurring.ics
git commit -m "feat: ICS calendar source with recurring event support"
```

---

## Task 8: Weather Source

**Files:**
- Create: `sources/weather.py`
- Create: `tests/test_weather.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_weather.py
import pytest
import respx
import httpx
from sources.weather import get_forecast, ICON_KEYS
from config import load_config

OPEN_METEO_RESPONSE = {
    "daily": {
        "time": ["2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11"],
        "weathercode": [0, 61, 71, 95, 45],
        "temperature_2m_max": [15.2, 12.1, 8.3, 10.0, 13.5],
        "temperature_2m_min": [5.1, 3.2, -1.0, 2.3, 4.0],
        "precipitation_probability_max": [0, 80, 60, 90, 20],
    }
}


@pytest.mark.asyncio
@respx.mock
async def test_openmeteo_returns_5_days(sample_config):
    cfg = load_config(sample_config)
    respx.get(url__startswith="https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=OPEN_METEO_RESPONSE)
    )
    days = await get_forecast(cfg)
    assert len(days) == 5


@pytest.mark.asyncio
@respx.mock
async def test_openmeteo_normalizes_icons(sample_config):
    cfg = load_config(sample_config)
    respx.get(url__startswith="https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=OPEN_METEO_RESPONSE)
    )
    days = await get_forecast(cfg)
    # WMO 0 = sunny, 61 = rainy, 71 = snow, 95 = storm, 45 = fog
    assert days[0].icon == "sunny"
    assert days[1].icon == "rainy"
    assert days[2].icon == "snow"
    assert days[3].icon == "storm"
    assert days[4].icon == "fog"


@pytest.mark.asyncio
@respx.mock
async def test_openmeteo_temps_and_precip(sample_config):
    cfg = load_config(sample_config)
    respx.get(url__startswith="https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=OPEN_METEO_RESPONSE)
    )
    days = await get_forecast(cfg)
    assert days[0].temp_high == 15.2
    assert days[0].temp_low == 5.1
    assert days[0].precip_percent == 0
    assert days[1].precip_percent == 80


def test_all_icon_keys_are_valid():
    valid = {"sunny", "partly-cloudy", "cloudy", "rainy", "heavy-rain", "snow", "storm", "fog"}
    for wmo_code, icon in ICON_KEYS.items():
        assert icon in valid, f"WMO {wmo_code} maps to unknown icon '{icon}'"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_weather.py -v
```

Expected: FAIL

- [ ] **Step 3: Create `sources/weather.py`**

```python
from abc import ABC, abstractmethod
import httpx
from models import WeatherDay
from config import AppConfig

# WMO Weather Interpretation Codes -> normalized icon key
ICON_KEYS: dict[int, str] = {
    0: "sunny",
    1: "sunny", 2: "partly-cloudy", 3: "cloudy",
    45: "fog", 48: "fog",
    51: "rainy", 53: "rainy", 55: "rainy",
    56: "rainy", 57: "rainy",
    61: "rainy", 63: "rainy", 65: "heavy-rain",
    66: "rainy", 67: "heavy-rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "rainy", 81: "rainy", 82: "heavy-rain",
    85: "snow", 86: "snow",
    95: "storm", 96: "storm", 99: "storm",
}

# AccuWeather icon IDs (1-44) -> normalized icon key
_AW_ICON_KEYS: dict[int, str] = {
    **{i: "sunny" for i in [1, 2, 30, 31, 32, 33, 34]},
    **{i: "partly-cloudy" for i in [3, 4, 5, 35, 36]},
    **{i: "cloudy" for i in [6, 7, 8, 37, 38]},
    11: "fog",
    **{i: "rainy" for i in [12, 13, 14, 18, 39, 40]},
    **{i: "storm" for i in [15, 16, 17, 41, 42]},
    **{i: "heavy-rain" for i in [19, 20, 21]},
    **{i: "snow" for i in [22, 23, 24, 25, 26, 29, 43, 44]},
}


class WeatherProvider(ABC):
    @abstractmethod
    async def get_forecast(self, cfg: AppConfig) -> list[WeatherDay]:
        pass


class OpenMeteoProvider(WeatherProvider):
    async def get_forecast(self, cfg: AppConfig) -> list[WeatherDay]:
        params = {
            "latitude": cfg.weather.latitude,
            "longitude": cfg.weather.longitude,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": cfg.display.weather_days,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()["daily"]

        return [
            WeatherDay(
                date=data["time"][i],
                icon=ICON_KEYS.get(data["weathercode"][i], "cloudy"),
                temp_high=data["temperature_2m_max"][i],
                temp_low=data["temperature_2m_min"][i],
                precip_percent=data["precipitation_probability_max"][i],
            )
            for i in range(len(data["time"]))
        ]


class AccuWeatherProvider(WeatherProvider):
    async def get_forecast(self, cfg: AppConfig) -> list[WeatherDay]:
        # Step 1: get location key
        async with httpx.AsyncClient(timeout=10) as client:
            loc_resp = await client.get(
                "https://dataservice.accuweather.com/locations/v1/cities/geoposition/search",
                params={"apikey": cfg.weather.accuweather_api_key, "q": f"{cfg.weather.latitude},{cfg.weather.longitude}"},
            )
            loc_resp.raise_for_status()
            location_key = loc_resp.json()["Key"]

            # Step 2: get 5-day forecast
            fc_resp = await client.get(
                f"https://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}",
                params={"apikey": cfg.weather.accuweather_api_key, "metric": "true"},
            )
            fc_resp.raise_for_status()
            daily = fc_resp.json()["DailyForecasts"]

        return [
            WeatherDay(
                date=d["Date"][:10],
                icon=_AW_ICON_KEYS.get(d["Day"]["Icon"], "cloudy"),
                temp_high=d["Temperature"]["Maximum"]["Value"],
                temp_low=d["Temperature"]["Minimum"]["Value"],
                precip_percent=d["Day"].get("PrecipitationProbability", 0),
            )
            for d in daily
        ]


async def get_forecast(cfg: AppConfig) -> list[WeatherDay]:
    if cfg.weather.provider == "accuweather":
        provider: WeatherProvider = AccuWeatherProvider()
    else:
        provider = OpenMeteoProvider()
    return await provider.get_forecast(cfg)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_weather.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add sources/weather.py tests/test_weather.py
git commit -m "feat: weather source with Open-Meteo and AccuWeather providers"
```

---

## Task 9: Home Assistant Source

**Files:**
- Create: `sources/homeassistant.py`
- Create: `tests/test_homeassistant.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_homeassistant.py
import pytest
import respx
import httpx
from sources.homeassistant import get_entities
from config import load_config


@pytest.mark.asyncio
@respx.mock
async def test_fetches_entity_state(sample_config):
    cfg = load_config(sample_config)
    respx.get("http://ha.local:8123/api/states/sensor.living_room_temperature").mock(
        return_value=httpx.Response(200, json={
            "entity_id": "sensor.living_room_temperature",
            "state": "22.5",
            "attributes": {"unit_of_measurement": "°C", "friendly_name": "Living Room Temp"},
        })
    )
    entities = await get_entities(cfg)
    assert len(entities) == 1
    assert entities[0].state == "22.5"
    assert entities[0].unit == "°C"
    assert entities[0].label == "Obývák"


@pytest.mark.asyncio
@respx.mock
async def test_returns_empty_when_no_entities_configured(sample_config):
    cfg = load_config(sample_config)
    cfg.home_assistant.entities = []
    entities = await get_entities(cfg)
    assert entities == []


@pytest.mark.asyncio
@respx.mock
async def test_skips_unreachable_entity(sample_config):
    cfg = load_config(sample_config)
    respx.get("http://ha.local:8123/api/states/sensor.living_room_temperature").mock(
        return_value=httpx.Response(404)
    )
    entities = await get_entities(cfg)
    assert entities == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_homeassistant.py -v
```

Expected: FAIL

- [ ] **Step 3: Create `sources/homeassistant.py`**

```python
import asyncio
import httpx
from models import HaEntity
from config import AppConfig


async def _fetch_entity(client: httpx.AsyncClient, base_url: str, token: str, entity_id: str, label: str) -> HaEntity | None:
    try:
        resp = await client.get(
            f"{base_url}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        attrs = data.get("attributes", {})
        return HaEntity(
            id=entity_id,
            label=label,
            state=str(data.get("state", "unknown")),
            unit=str(attrs.get("unit_of_measurement", "")),
        )
    except Exception:
        return None


async def get_entities(cfg: AppConfig) -> list[HaEntity]:
    if not cfg.home_assistant.entities:
        return []

    async with httpx.AsyncClient(timeout=5) as client:
        tasks = [
            _fetch_entity(client, cfg.home_assistant.url, cfg.home_assistant.token, e.id, e.label)
            for e in cfg.home_assistant.entities
        ]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_homeassistant.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add sources/homeassistant.py tests/test_homeassistant.py
git commit -m "feat: Home Assistant entity source"
```

---

## Task 10: Wire Sources into `/api/data` with Background Cache

**Files:**
- Modify: `main.py`
- Create: `tests/test_api_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_api_integration.py
import pytest
import respx
import httpx
from pathlib import Path
from httpx import AsyncClient, ASGITransport

FIXTURES = Path(__file__).parent / "fixtures"

OPEN_METEO_RESPONSE = {
    "daily": {
        "time": ["2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11"],
        "weathercode": [0, 61, 71, 95, 45],
        "temperature_2m_max": [15.0, 12.0, 8.0, 10.0, 13.0],
        "temperature_2m_min": [5.0, 3.0, -1.0, 2.0, 4.0],
        "precipitation_probability_max": [0, 80, 60, 90, 20],
    }
}

WEBSTREAM_RESPONSE = {
    "photos": [{"photoGuid": "g1", "derivatives": {"2": {"checksum": "c1"}}}]
}
WEBASSETURLS_RESPONSE = {"items": {"c1": {"url_location": "https://cdn.icloud.com/photo1.jpg"}}}


@pytest.mark.asyncio
@respx.mock
async def test_api_data_returns_real_data(sample_config):
    from main import create_app

    respx.get(url__startswith="https://api.open-meteo.com").mock(
        return_value=httpx.Response(200, json=OPEN_METEO_RESPONSE)
    )
    respx.post(url__contains="sharedstreams/webstream").mock(
        return_value=httpx.Response(200, json=WEBSTREAM_RESPONSE)
    )
    respx.post(url__contains="webasseturls").mock(
        return_value=httpx.Response(200, json=WEBASSETURLS_RESPONSE)
    )
    respx.get("https://example.com/family.ics").mock(
        return_value=httpx.Response(200, content=(FIXTURES / "simple.ics").read_bytes())
    )
    respx.get("https://example.com/work.ics").mock(
        return_value=httpx.Response(200, content=b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
    )
    respx.get(url__startswith="http://ha.local:8123").mock(
        return_value=httpx.Response(200, json={"entity_id": "sensor.x", "state": "21", "attributes": {"unit_of_measurement": "°C"}})
    )

    app = create_app(sample_config)
    await app.router.startup()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/data")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["weather"]) == 5
    assert data["weather"][0]["icon"] == "sunny"
    assert len(data["photos"]) == 1
    assert data["photo_interval_seconds"] == 30
```

- [ ] **Step 2: Run to confirm partial failure** (main.py still returns empty lists)

```bash
pytest tests/test_api_integration.py -v
```

Expected: FAIL on weather/photos assertions

- [ ] **Step 3: Rewrite `main.py` to wire all sources with background cache**

```python
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from cache import Cache
from config import AppConfig, load_config
from models import DashboardData
from sources.icloud import get_photos, get_photo_url
from sources.calendar import get_events
from sources.weather import get_forecast
from sources.homeassistant import get_entities

STATIC_DIR = Path(__file__).parent / "static"

CACHE_TTLS = {
    "photos": 3600,
    "events": 300,
    "weather": 1800,
    "ha_entities": 60,
}


def create_app(config_path: str = "config.json") -> FastAPI:
    cfg = load_config(config_path)
    cache = Cache()
    app = FastAPI()

    async def refresh_source(key: str):
        try:
            if key == "photos":
                cache.set(key, await get_photos(cfg), CACHE_TTLS[key])
            elif key == "events":
                cache.set(key, await get_events(cfg), CACHE_TTLS[key])
            elif key == "weather":
                cache.set(key, await get_forecast(cfg), CACHE_TTLS[key])
            elif key == "ha_entities":
                cache.set(key, await get_entities(cfg), CACHE_TTLS[key])
        except Exception:
            pass  # keep stale value

    async def background_refresh(key: str, ttl: int):
        while True:
            await asyncio.sleep(ttl)
            await refresh_source(key)

    @app.on_event("startup")
    async def startup():
        # Eager load all sources
        await asyncio.gather(
            refresh_source("photos"),
            refresh_source("events"),
            refresh_source("weather"),
            refresh_source("ha_entities"),
        )
        # Start background refresh loops
        for key, ttl in CACHE_TTLS.items():
            asyncio.create_task(background_refresh(key, ttl))

    @app.get("/api/data", response_model=DashboardData)
    async def get_data():
        return DashboardData(
            photos=cache.get("photos", return_stale=True) or [],
            events=cache.get("events", return_stale=True) or [],
            weather=cache.get("weather", return_stale=True) or [],
            ha_entities=cache.get("ha_entities", return_stale=True) or [],
            photo_interval_seconds=cfg.icloud.photo_interval_seconds,
            server_time=datetime.now(timezone.utc),
        )

    @app.get("/api/photo/{photo_id}")
    async def get_photo(photo_id: str):
        url = get_photo_url(photo_id)
        if not url:
            raise HTTPException(status_code=404, detail="Photo not found")
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
        return StreamingResponse(
            content=iter([r.content]),
            media_type=r.headers.get("content-type", "image/jpeg"),
        )

    app.mount("/static/css", StaticFiles(directory=str(STATIC_DIR / "css")), name="css")
    app.mount("/static/js", StaticFiles(directory=str(STATIC_DIR / "js")), name="js")

    @app.get("/{full_path:path}")
    async def serve_index(full_path: str):
        return FileResponse(str(STATIC_DIR / "index.html"))

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=False)
```

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_api_integration.py
git commit -m "feat: wire all sources into /api/data with background TTL cache"
```

---

## Task 11: TypeScript Scaffold, Types, and HTML Shell

**Files:**
- Create: `src/types.ts`
- Create: `src/api.ts`
- Create: `static/index.html`
- Create: `static/css/base.css`

- [ ] **Step 1: Create `src/types.ts`**

```typescript
export interface Photo {
  id: string;
  url: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string; // ISO datetime string
  end: string;
  all_day: boolean;
  calendar_name: string;
  color: string;
}

export interface WeatherDay {
  date: string; // "YYYY-MM-DD"
  icon: string; // sunny|partly-cloudy|cloudy|rainy|heavy-rain|snow|storm|fog
  temp_high: number;
  temp_low: number;
  precip_percent: number;
}

export interface HaEntity {
  id: string;
  label: string;
  state: string;
  unit: string;
}

export interface DashboardData {
  photos: Photo[];
  events: CalendarEvent[];
  weather: WeatherDay[];
  ha_entities: HaEntity[];
  photo_interval_seconds: number;
  server_time: string;
}
```

- [ ] **Step 2: Create `src/api.ts`**

```typescript
import type { DashboardData } from "./types";

export async function fetchData(): Promise<DashboardData> {
  const resp = await fetch("/api/data");
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json() as Promise<DashboardData>;
}
```

- [ ] **Step 3: Create `static/index.html`**

```html
<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>WMD</title>
  <link rel="stylesheet" href="/static/css/base.css" />
  <link rel="stylesheet" href="/static/css/photo.css" />
  <link rel="stylesheet" href="/static/css/calendar.css" />
  <link rel="stylesheet" href="/static/css/clock.css" />
  <link rel="stylesheet" href="/static/css/weather.css" />
  <link rel="stylesheet" href="/static/css/mini-calendar.css" />
</head>
<body>
  <div class="dashboard">
    <div class="photo-area" id="photo-area">
      <img class="photo-img photo-img--active" id="photo-a" src="" alt="" />
      <img class="photo-img" id="photo-b" src="" alt="" />
    </div>
    <div class="calendar-area" id="calendar-area"></div>
    <div class="clock-area" id="clock-area"></div>
    <div class="weather-area" id="weather-area"></div>
    <div class="mini-cal-area" id="mini-cal-area"></div>
    <div class="ha-area" id="ha-area"></div>
  </div>
  <script src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create `static/css/base.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #0a0a0a;
  color: #e8e8e8;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  font-size: 16px;
}

.dashboard {
  display: grid;
  width: 100vw;
  height: 100vh;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 55vh 1fr 1fr 1fr auto;
  grid-template-areas:
    "photo    photo"
    "calendar clock"
    "calendar weather"
    "calendar mini-cal"
    "calendar ha";
}

.photo-area    { grid-area: photo; position: relative; overflow: hidden; }
.calendar-area { grid-area: calendar; overflow: hidden; }
.clock-area    { grid-area: clock; }
.weather-area  { grid-area: weather; }
.mini-cal-area { grid-area: mini-cal; }
.ha-area       { grid-area: ha; display: none; flex-wrap: wrap; gap: 8px; padding: 6px 12px; font-size: 0.8rem; color: #aaa; }
```

- [ ] **Step 5: Create a minimal `src/app.ts`** to verify the build works

```typescript
import { fetchData } from "./api";

async function init() {
  const data = await fetchData();
  console.log("WMD data loaded:", data.server_time);
}

init();
```

- [ ] **Step 6: Build and verify**

```bash
npm run build
```

Expected: `static/js/app.js` created with no errors

- [ ] **Step 7: Commit**

```bash
git add src/types.ts src/api.ts src/app.ts static/index.html static/css/base.css
git commit -m "feat: TypeScript scaffold, shared types, HTML shell, base CSS grid"
```

---

## Task 12: Clock Module

**Files:**
- Create: `src/modules/clock.ts`
- Create: `static/css/clock.css`

- [ ] **Step 1: Create `src/modules/clock.ts`**

```typescript
export function startClock(container: HTMLElement): void {
  function tick() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    container.textContent = `${hh}:${mm}`;
  }
  tick();
  setInterval(tick, 1000);
}
```

- [ ] **Step 2: Create `static/css/clock.css`**

```css
.clock-area {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
}

#clock-area {
  font-size: clamp(3rem, 6vw, 7rem);
  font-weight: 200;
  letter-spacing: 0.05em;
  color: #ffffff;
}
```

- [ ] **Step 3: Wire clock into `src/app.ts`**

```typescript
import { fetchData } from "./api";
import { startClock } from "./modules/clock";

async function init() {
  startClock(document.getElementById("clock-area")!);
  const data = await fetchData();
  console.log("WMD data loaded:", data.server_time);
}

init();
```

- [ ] **Step 4: Build**

```bash
npm run build
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add src/modules/clock.ts static/css/clock.css src/app.ts
git commit -m "feat: clock module"
```

---

## Task 13: Photo Module

**Files:**
- Create: `src/modules/photo.ts`
- Create: `static/css/photo.css`

- [ ] **Step 1: Create `src/modules/photo.ts`**

```typescript
import type { Photo } from "../types";

let photos: Photo[] = [];
let currentIndex = 0;
let intervalMs = 30000;
let rotationTimer: ReturnType<typeof setTimeout> | null = null;

const imgA = document.getElementById("photo-a") as HTMLImageElement;
const imgB = document.getElementById("photo-b") as HTMLImageElement;

function preloadAndSwap(url: string): void {
  const active = imgA.classList.contains("photo-img--active") ? imgA : imgB;
  const next = active === imgA ? imgB : imgA;

  next.onload = () => {
    next.classList.add("photo-img--active");
    active.classList.remove("photo-img--active");
  };
  next.src = url;
}

function advance(): void {
  if (photos.length === 0) return;
  currentIndex = (currentIndex + 1) % photos.length;
  preloadAndSwap(photos[currentIndex].url);
}

export function render(data: Photo[], container: HTMLElement, photoIntervalSeconds: number): void {
  if (data.length === 0) return;

  const newInterval = photoIntervalSeconds * 1000;
  const photosChanged = JSON.stringify(data.map(p => p.id)) !== JSON.stringify(photos.map(p => p.id));

  photos = data;
  intervalMs = newInterval;

  if (photosChanged && imgA.src === "") {
    // First load: set initial photo immediately
    imgA.src = photos[0].url;
    imgA.classList.add("photo-img--active");
    currentIndex = 0;
  }

  // Reset rotation timer if interval changed
  if (rotationTimer) clearInterval(rotationTimer);
  rotationTimer = setInterval(advance, intervalMs);
}
```

- [ ] **Step 2: Create `static/css/photo.css`**

```css
.photo-area {
  background: #000;
}

.photo-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 1s ease-in-out;
}

.photo-img--active {
  opacity: 1;
}
```

- [ ] **Step 3: Update `src/app.ts`**

```typescript
import { fetchData } from "./api";
import { startClock } from "./modules/clock";
import { render as renderPhotos } from "./modules/photo";

async function init() {
  startClock(document.getElementById("clock-area")!);
  const data = await fetchData();
  renderPhotos(data.photos, document.getElementById("photo-area")!, data.photo_interval_seconds);
}

init();
```

- [ ] **Step 4: Build**

```bash
npm run build
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add src/modules/photo.ts static/css/photo.css src/app.ts
git commit -m "feat: photo crossfade rotation module"
```

---

## Task 14: Calendar Module

**Files:**
- Create: `src/modules/calendar.ts`
- Create: `static/css/calendar.css`

- [ ] **Step 1: Create `src/modules/calendar.ts`**

```typescript
import type { CalendarEvent } from "../types";

const DAY_LABELS: Record<number, string> = { 0: "ne", 1: "po", 2: "út", 3: "st", 4: "čt", 5: "pá", 6: "so" };

function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function dayLabel(dateStr: string): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(dateStr);
  d.setHours(0, 0, 0, 0);
  const diff = Math.round((d.getTime() - today.getTime()) / 86400000);
  if (diff === 0) return "dnes";
  if (diff === 1) return "zítra";
  return DAY_LABELS[d.getDay()] ?? "";
}

export function render(events: CalendarEvent[], container: HTMLElement): void {
  container.innerHTML = "";

  // Group by date
  const byDate = new Map<string, CalendarEvent[]>();
  for (const ev of events) {
    const dateKey = ev.start.slice(0, 10);
    if (!byDate.has(dateKey)) byDate.set(dateKey, []);
    byDate.get(dateKey)!.push(ev);
  }

  for (const [dateKey, dayEvents] of byDate) {
    const d = new Date(dateKey);
    const header = document.createElement("div");
    header.className = "cal-date-header";
    header.innerHTML = `<span class="cal-day-num">${d.getDate()}</span><span class="cal-day-label">${dayLabel(dateKey)}</span>`;
    container.appendChild(header);

    for (const ev of dayEvents) {
      const row = document.createElement("div");
      row.className = "cal-event";
      row.style.setProperty("--cal-color", ev.color);

      const time = ev.all_day
        ? `<span class="cal-time">celý den</span>`
        : `<span class="cal-time">${formatTime(ev.start)}<br/>${formatTime(ev.end)}</span>`;

      row.innerHTML = `${time}<span class="cal-title">${ev.title}</span>`;
      container.appendChild(row);
    }
  }
}
```

- [ ] **Step 2: Create `static/css/calendar.css`**

```css
.calendar-area {
  padding: 8px 0;
  overflow-y: auto;
  scrollbar-width: none;
}
.calendar-area::-webkit-scrollbar { display: none; }

.cal-date-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 12px 4px;
}
.cal-day-num {
  font-size: 2rem;
  font-weight: 300;
  color: #fff;
}
.cal-day-label {
  font-size: 0.85rem;
  color: #888;
  text-transform: lowercase;
}

.cal-event {
  display: flex;
  align-items: stretch;
  border-left: 4px solid var(--cal-color, #555);
  margin: 2px 8px;
  background: rgba(255,255,255,0.04);
  border-radius: 0 4px 4px 0;
  min-height: 36px;
}
.cal-time {
  font-size: 0.65rem;
  color: #888;
  padding: 4px 6px;
  min-width: 40px;
  line-height: 1.3;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.cal-title {
  font-size: 0.88rem;
  padding: 6px 8px;
  color: #e8e8e8;
  display: flex;
  align-items: center;
}
```

- [ ] **Step 3: Update `src/app.ts`**

```typescript
import { fetchData } from "./api";
import { startClock } from "./modules/clock";
import { render as renderPhotos } from "./modules/photo";
import { render as renderCalendar } from "./modules/calendar";

async function init() {
  startClock(document.getElementById("clock-area")!);
  const data = await fetchData();
  renderPhotos(data.photos, document.getElementById("photo-area")!, data.photo_interval_seconds);
  renderCalendar(data.events, document.getElementById("calendar-area")!);
}

init();
```

- [ ] **Step 4: Build**

```bash
npm run build
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add src/modules/calendar.ts static/css/calendar.css src/app.ts
git commit -m "feat: calendar module with date grouping and Czech labels"
```

---

## Task 15: Weather Module

**Files:**
- Create: `src/modules/weather.ts`
- Create: `static/css/weather.css`

- [ ] **Step 1: Create `src/modules/weather.ts`**

```typescript
import type { WeatherDay } from "../types";

const ICONS: Record<string, string> = {
  "sunny":         "☀️",
  "partly-cloudy": "⛅",
  "cloudy":        "☁️",
  "rainy":         "🌧",
  "heavy-rain":    "⛈",
  "snow":          "❄️",
  "storm":         "⛈",
  "fog":           "🌫",
};

const CZECH_DAYS = ["ne", "po", "út", "st", "čt", "pá", "so"];

export function render(days: WeatherDay[], container: HTMLElement): void {
  container.innerHTML = "";

  for (const day of days) {
    const d = new Date(day.date);
    const dayName = CZECH_DAYS[d.getDay()];

    const el = document.createElement("div");
    el.className = "weather-day";
    el.innerHTML = `
      <span class="wx-day">${dayName}</span>
      <span class="wx-icon">${ICONS[day.icon] ?? "🌡"}</span>
      <span class="wx-high">${Math.round(day.temp_high)}°</span>
      <span class="wx-low">${Math.round(day.temp_low)}°</span>
      <span class="wx-precip">${day.precip_percent}%</span>
    `;
    container.appendChild(el);
  }
}
```

- [ ] **Step 2: Create `static/css/weather.css`**

```css
.weather-area {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-around;
  padding: 8px 12px;
  gap: 4px;
}

.weather-day {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex: 1;
}

.wx-day    { font-size: 0.7rem; color: #888; text-transform: lowercase; }
.wx-icon   { font-size: 1.4rem; line-height: 1; }
.wx-high   { font-size: 0.85rem; color: #fff; font-weight: 500; }
.wx-low    { font-size: 0.75rem; color: #666; }
.wx-precip { font-size: 0.65rem; color: #5b9bd5; }
```

- [ ] **Step 3: Update `src/app.ts`**

```typescript
import { fetchData } from "./api";
import { startClock } from "./modules/clock";
import { render as renderPhotos } from "./modules/photo";
import { render as renderCalendar } from "./modules/calendar";
import { render as renderWeather } from "./modules/weather";

async function init() {
  startClock(document.getElementById("clock-area")!);
  const data = await fetchData();
  renderPhotos(data.photos, document.getElementById("photo-area")!, data.photo_interval_seconds);
  renderCalendar(data.events, document.getElementById("calendar-area")!);
  renderWeather(data.weather, document.getElementById("weather-area")!);
}

init();
```

- [ ] **Step 4: Build**

```bash
npm run build
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add src/modules/weather.ts static/css/weather.css src/app.ts
git commit -m "feat: weather module with 5-day forecast"
```

---

## Task 16: Mini Calendar Module

**Files:**
- Create: `src/modules/mini-calendar.ts`
- Create: `static/css/mini-calendar.css`

- [ ] **Step 1: Create `src/modules/mini-calendar.ts`**

```typescript
import type { CalendarEvent } from "../types";

const HEADERS = ["po", "út", "st", "čt", "pá", "so", "ne"];

// Returns "YYYY-MM-DD" for a Date
function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function render(events: CalendarEvent[], container: HTMLElement): void {
  container.innerHTML = "";

  const now = new Date();
  const today = toDateKey(now);
  const year = now.getFullYear();
  const month = now.getMonth();

  // Days with events -> set of colors per day
  const eventDays = new Map<string, Set<string>>();
  for (const ev of events) {
    const key = ev.start.slice(0, 10);
    if (!eventDays.has(key)) eventDays.set(key, new Set());
    eventDays.get(key)!.add(ev.color);
  }

  // Header row
  const headerRow = document.createElement("div");
  headerRow.className = "mini-cal-row mini-cal-header";
  for (const h of HEADERS) {
    const cell = document.createElement("span");
    cell.className = "mini-cal-cell";
    cell.textContent = h;
    headerRow.appendChild(cell);
  }
  container.appendChild(headerRow);

  // First day of month (0=Sun..6=Sat), convert to Mon-based (0=Mon..6=Sun)
  const firstDay = new Date(year, month, 1);
  const startOffset = (firstDay.getDay() + 6) % 7; // Mon=0
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  let dayCounter = 1;
  let row = document.createElement("div");
  row.className = "mini-cal-row";

  for (let col = 0; col < startOffset; col++) {
    const cell = document.createElement("span");
    cell.className = "mini-cal-cell mini-cal-empty";
    row.appendChild(cell);
  }

  let col = startOffset;
  while (dayCounter <= daysInMonth) {
    const d = new Date(year, month, dayCounter);
    const key = toDateKey(d);

    const cell = document.createElement("span");
    cell.className = "mini-cal-cell";
    if (key === today) cell.classList.add("mini-cal-today");

    const num = document.createElement("span");
    num.className = "mini-cal-num";
    num.textContent = String(dayCounter);
    cell.appendChild(num);

    const colors = eventDays.get(key);
    if (colors && colors.size > 0) {
      const dots = document.createElement("span");
      dots.className = "mini-cal-dots";
      for (const color of Array.from(colors).slice(0, 3)) {
        const dot = document.createElement("span");
        dot.className = "mini-cal-dot";
        dot.style.background = color;
        dots.appendChild(dot);
      }
      cell.appendChild(dots);
    }

    row.appendChild(cell);
    col++;

    if (col === 7) {
      container.appendChild(row);
      row = document.createElement("div");
      row.className = "mini-cal-row";
      col = 0;
    }
    dayCounter++;
  }

  if (col > 0) container.appendChild(row);
}
```

- [ ] **Step 2: Create `static/css/mini-calendar.css`**

```css
.mini-cal-area {
  padding: 6px 10px;
  overflow: hidden;
}

.mini-cal-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
}

.mini-cal-header .mini-cal-cell {
  font-size: 0.6rem;
  color: #555;
  text-align: center;
  padding: 2px 0;
  text-transform: lowercase;
}

.mini-cal-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1px 0;
}

.mini-cal-num {
  font-size: 0.72rem;
  color: #bbb;
  line-height: 1.4;
}

.mini-cal-today .mini-cal-num {
  background: #e53935;
  color: #fff;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}

.mini-cal-dots {
  display: flex;
  gap: 2px;
  justify-content: center;
  margin-top: 1px;
}

.mini-cal-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
}
```

- [ ] **Step 3: Update `src/app.ts` with polling loop and all modules**

```typescript
import { fetchData } from "./api";
import type { DashboardData } from "./types";
import { startClock } from "./modules/clock";
import { render as renderPhotos } from "./modules/photo";
import { render as renderCalendar } from "./modules/calendar";
import { render as renderWeather } from "./modules/weather";
import { render as renderMiniCal } from "./modules/mini-calendar";

function update(data: DashboardData): void {
  renderPhotos(data.photos, document.getElementById("photo-area")!, data.photo_interval_seconds);
  renderCalendar(data.events, document.getElementById("calendar-area")!);
  renderWeather(data.weather, document.getElementById("weather-area")!);
  renderMiniCal(data.events, document.getElementById("mini-cal-area")!);

  const haArea = document.getElementById("ha-area")!;
  if (data.ha_entities.length > 0) {
    haArea.style.display = "flex";
    haArea.innerHTML = data.ha_entities
      .map(e => `<span class="ha-entity">${e.label}: <strong>${e.state}${e.unit}</strong></span>`)
      .join("");
  } else {
    haArea.style.display = "none";
  }
}

async function init(): Promise<void> {
  startClock(document.getElementById("clock-area")!);

  try {
    const data = await fetchData();
    update(data);
  } catch (e) {
    console.error("Initial data fetch failed:", e);
  }

  setInterval(async () => {
    try {
      const data = await fetchData();
      update(data);
    } catch (e) {
      console.error("Data refresh failed:", e);
    }
  }, 60_000);
}

init();
```

- [ ] **Step 4: Build**

```bash
npm run build
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add src/modules/mini-calendar.ts static/css/mini-calendar.css src/app.ts
git commit -m "feat: mini calendar module with event dots and complete polling loop"
```

---

## Task 17: systemd Services

**Files:**
- Create: `systemd/wmd-server.service`
- Create: `systemd/wmd-browser.service`

- [ ] **Step 1: Create `systemd/wmd-server.service`**

```ini
[Unit]
Description=WMD Dashboard Server
After=network.target
Wants=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/wmd
ExecStart=/home/ubuntu/wmd/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 3000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> Note: Replace `ubuntu` with `pi` if using Raspberry Pi OS instead of Ubuntu Server.

- [ ] **Step 2: Create `systemd/wmd-browser.service`**

```ini
[Unit]
Description=WMD Dashboard Browser (Chromium Kiosk)
After=wmd-server.service graphical-session.target
Wants=graphical-session.target

[Service]
User=ubuntu
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/ubuntu/.Xauthority
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --check-for-update-interval=31536000 \
  --disable-translate \
  --disable-features=Translate \
  --autoplay-policy=no-user-gesture-required \
  http://localhost:3000
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

- [ ] **Step 3: Commit**

```bash
git add systemd/wmd-server.service systemd/wmd-browser.service
git commit -m "feat: systemd service files for server and kiosk browser"
```

---

## Task 18: README and Deployment Guide

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# WMD Dashboard

Self-hosted wall dashboard for Raspberry Pi (Ubuntu Server). Displays iCloud photos, merged calendars, weather, and Home Assistant data in a Chromium kiosk on a wall-mounted TV.

## Requirements

- Raspberry Pi with Ubuntu Server 22.04+
- Desktop environment or Xorg installed
- Python 3.11+
- Node.js 18+ (build only)
- Chromium browser

## Setup

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y chromium-browser unclutter xorg lightdm
```

### 2. Clone and configure

```bash
git clone <repo-url> /home/ubuntu/wmd
cd /home/ubuntu/wmd
cp config.example.json config.json
nano config.json   # fill in your tokens and URLs
```

### 3. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Build frontend

```bash
npm install
npm run build
```

### 5. Install and enable systemd services

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wmd-server wmd-browser
sudo systemctl start wmd-server wmd-browser
```

### 6. Enable auto-login (for kiosk display)

```bash
sudo systemctl set-default graphical.target
sudo nano /etc/lightdm/lightdm.conf
# Set: autologin-user=ubuntu
```

## Updating config

Edit `config.json` and restart the server — no rebuild needed for config changes:

```bash
sudo systemctl restart wmd-server
```

## Updating frontend

After editing TypeScript source files:

```bash
npm run build
sudo systemctl restart wmd-server
```

## Calendar ICS URLs

- **iCloud:** iCloud.com → Calendar → Share → Copy link (replace `webcal://` with `https://`)
- **Google:** Google Calendar → Settings → Calendar → Secret address in iCal format
- **MS365 / Outlook:** Calendar → Share → Publish → ICS link

## iCloud Share Token

From a shared album URL like `https://www.icloud.com/photos/0AbCdEfG123...`, the token is `0AbCdEfG123...`.

## Logs

```bash
journalctl -u wmd-server -f
journalctl -u wmd-browser -f
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: deployment guide and setup README"
```

---

## Final Check

- [ ] Run full test suite

```bash
source .venv/bin/activate
pytest -v
```

Expected: all tests pass

- [ ] Run typecheck

```bash
npx tsc --noEmit
```

Expected: no errors

- [ ] Build production frontend

```bash
npm run build
```

- [ ] Start server and verify manually

```bash
python3 main.py &
curl -s http://localhost:3000/api/data | python3 -m json.tool | head -30
kill %1
```

Expected: JSON response with correct shape

- [ ] Final commit

```bash
git add -A
git commit -m "chore: final verification pass"
```
