import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import httpx
import pytest
import respx
from httpx import ASGITransport

from config import AppConfig, CalendarConfig, DisplayConfig, HomeAssistantConfig, ICloudConfig, WeatherConfig
from sources.calendar import get_events
from sources.calendar_uploads import InvalidCalendarUpload, read_upload, save_upload

FIXTURES = Path(__file__).parent / "fixtures"
SIMPLE_ICS = (FIXTURES / "simple.ics").read_bytes()
FIXED_NOW = datetime(2026, 4, 7, 0, 0, 0, tzinfo=timezone.utc)
TOKEN = "s3cret-upload-token"
FEED_URL = "http://test.example.com/busy.ics"
FEED_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:feed@test
DTSTART:20260407T120000Z
DTEND:20260407T130000Z
SUMMARY:From the feed
END:VEVENT
END:VCALENDAR"""


# ── storage ────────────────────────────────────────────────────────────────

def test_save_then_read_roundtrips_content(tmp_path):
    save_upload(str(tmp_path), "Blue", SIMPLE_ICS)

    assert read_upload(str(tmp_path), "Blue") == SIMPLE_ICS


def test_read_returns_none_when_nothing_uploaded(tmp_path):
    assert read_upload(str(tmp_path), "Blue") is None


def test_save_rejects_content_that_is_not_a_calendar(tmp_path):
    with pytest.raises(InvalidCalendarUpload):
        save_upload(str(tmp_path), "Blue", b"<html>not a calendar</html>")

    assert read_upload(str(tmp_path), "Blue") is None


def test_save_rejects_empty_content(tmp_path):
    with pytest.raises(InvalidCalendarUpload):
        save_upload(str(tmp_path), "Blue", b"")


def test_save_keeps_file_inside_upload_dir_for_hostile_names(tmp_path):
    upload_dir = tmp_path / "uploads"

    save_upload(str(upload_dir), "../../etc/passwd", SIMPLE_ICS)

    assert [p.parent for p in tmp_path.rglob("*.ics")] == [upload_dir]


# ── calendar source ────────────────────────────────────────────────────────

def _config_with(cal: CalendarConfig, upload_dir: str) -> AppConfig:
    return AppConfig(
        icloud=ICloudConfig(share_token="x", photo_interval_seconds=30),
        calendars=[cal],
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
        home_assistant=HomeAssistantConfig(url="http://ha.local", token="tok", entities=[]),
        display=DisplayConfig(calendar_days_ahead=2, weather_days=5),
        upload_dir=upload_dir,
    )


@respx.mock
async def test_uploaded_file_replaces_url_feed(tmp_path):
    feed = respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=FEED_ICS))
    save_upload(str(tmp_path), "Blue", SIMPLE_ICS)
    cal = CalendarConfig(name="Blue", url=FEED_URL, color="#2196F3", upload_token=TOKEN)

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(_config_with(cal, str(tmp_path)))

    assert {e.title for e in events} == {"Trh Dka", "Celodení akce"}
    assert not feed.called


@respx.mock
async def test_url_feed_used_until_first_upload(tmp_path):
    respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=FEED_ICS))
    cal = CalendarConfig(name="Blue", url=FEED_URL, color="#2196F3", upload_token=TOKEN)

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(_config_with(cal, str(tmp_path)))

    assert {e.title for e in events} == {"From the feed"}


async def test_upload_only_calendar_is_empty_before_first_upload(tmp_path):
    cal = CalendarConfig(name="Blue", url="", color="#2196F3", upload_token=TOKEN)

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(_config_with(cal, str(tmp_path)))

    assert events == []


@respx.mock
async def test_upload_ignored_for_calendars_without_upload_token(tmp_path):
    respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=FEED_ICS))
    save_upload(str(tmp_path), "Blue", SIMPLE_ICS)
    cal = CalendarConfig(name="Blue", url=FEED_URL, color="#2196F3")

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(_config_with(cal, str(tmp_path)))

    assert {e.title for e in events} == {"From the feed"}


# ── endpoint ───────────────────────────────────────────────────────────────

@pytest.fixture
def upload_app(tmp_path):
    config = {
        "icloud": {"shareToken": "", "photoIntervalSeconds": 30},
        "calendars": [
            {"name": "Blue", "color": "#2196F3", "uploadToken": TOKEN, "showAsBusy": True},
            {"name": "Green", "url": FEED_URL, "color": "#4CAF50"},
        ],
        "weather": {"provider": "openmeteo", "latitude": 50.07, "longitude": 14.43},
        "homeAssistant": {"url": "http://homeassistant.local:8123", "token": "", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
        "uploadDir": str(tmp_path / "uploads"),
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    from main import create_app
    return create_app(config_path=str(path)), str(tmp_path / "uploads")


async def _put(app, name: str, body: bytes, token: str | None = TOKEN) -> httpx.Response:
    headers = {"Content-Type": "text/calendar"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.put(f"/api/calendars/{name}/ics", content=body, headers=headers)


async def test_put_stores_upload_and_returns_event_count(upload_app):
    app, upload_dir = upload_app

    response = await _put(app, "Blue", SIMPLE_ICS)

    assert response.status_code == 200
    assert response.json() == {"calendar": "Blue", "events": 2}
    assert read_upload(upload_dir, "Blue") == SIMPLE_ICS


async def test_put_rejects_missing_token(upload_app):
    app, upload_dir = upload_app

    response = await _put(app, "Blue", SIMPLE_ICS, token=None)

    assert response.status_code == 401
    assert read_upload(upload_dir, "Blue") is None


async def test_put_rejects_wrong_token(upload_app):
    app, upload_dir = upload_app

    response = await _put(app, "Blue", SIMPLE_ICS, token="nope")

    assert response.status_code == 401
    assert read_upload(upload_dir, "Blue") is None


async def test_put_404_for_calendar_without_upload_enabled(upload_app):
    app, _ = upload_app

    response = await _put(app, "Green", SIMPLE_ICS)

    assert response.status_code == 404


async def test_put_404_for_unknown_calendar(upload_app):
    app, _ = upload_app

    response = await _put(app, "Nope", SIMPLE_ICS)

    assert response.status_code == 404


async def test_put_400_for_invalid_ics(upload_app):
    app, upload_dir = upload_app

    response = await _put(app, "Blue", b"garbage")

    assert response.status_code == 400
    assert read_upload(upload_dir, "Blue") is None


async def test_put_413_for_oversized_body(upload_app):
    app, _ = upload_app

    with mock.patch("main.MAX_CALENDAR_UPLOAD_BYTES", 10):
        response = await _put(app, "Blue", SIMPLE_ICS)

    assert response.status_code == 413


async def test_post_is_accepted_like_put(upload_app):
    app, upload_dir = upload_app
    headers = {"Content-Type": "text/calendar", "Authorization": f"Bearer {TOKEN}"}

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/calendars/Blue/ics", content=SIMPLE_ICS, headers=headers)

    assert response.status_code == 200
    assert read_upload(upload_dir, "Blue") == SIMPLE_ICS
