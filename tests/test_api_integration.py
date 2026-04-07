import json

import httpx
import pytest
import respx
from httpx import ASGITransport

_SIMPLE_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260407T090000Z
DTEND:20260407T100000Z
SUMMARY:Test Event
UID:test-uid-001
END:VEVENT
END:VCALENDAR"""

_OPEN_METEO_RESPONSE = {
    "daily": {
        "time": ["2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11"],
        "weathercode": [0, 61, 71, 95, 45],
        "temperature_2m_max": [15.0, 12.5, 8.0, 10.0, 14.0],
        "temperature_2m_min": [5.0, 4.5, 1.0, 2.0, 6.0],
        "precipitation_probability_max": [0, 70, 90, 80, 10],
    }
}


@pytest.fixture
def config_file(tmp_path):
    config = {
        "icloud": {"shareToken": "testtoken", "photoIntervalSeconds": 30},
        "calendars": [
            {"name": "Family", "url": "http://cal1.test/feed.ics", "color": "#4CAF50"},
            {"name": "Work", "url": "http://cal2.test/feed.ics", "color": "#2196F3"},
        ],
        "weather": {"provider": "openmeteo", "latitude": 50.07, "longitude": 14.43, "accuweatherApiKey": ""},
        "homeAssistant": {
            "url": "http://homeassistant.local:8123",
            "token": "ha_token",
            "entities": [{"id": "sensor.temperature", "label": "Temperature"}],
        },
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))
    return str(p)


@respx.mock
async def test_api_data_returns_real_data(config_file):
    token = "testtoken"
    base = f"https://p01-sharedstreams.icloud.com/{token}/sharedstreams"

    # Mock iCloud
    respx.post(f"{base}/webstream").mock(
        return_value=httpx.Response(
            200,
            json={"photos": [{"photoGuid": "guid1", "derivatives": {"2000": {"checksum": "chk1"}}}]},
        )
    )
    respx.post(f"{base}/webasseturls").mock(
        return_value=httpx.Response(
            200,
            json={"items": {"chk1": {"url_location": "photos.icloud.com", "url_path": "/photo1.jpg"}}},
        )
    )

    # Mock ICS feeds
    respx.get("http://cal1.test/feed.ics").mock(return_value=httpx.Response(200, content=_SIMPLE_ICS))
    respx.get("http://cal2.test/feed.ics").mock(return_value=httpx.Response(200, content=_SIMPLE_ICS))

    # Mock Open-Meteo
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=_OPEN_METEO_RESPONSE)
    )

    # Mock Home Assistant
    respx.get("http://homeassistant.local:8123/api/states/sensor.temperature").mock(
        return_value=httpx.Response(
            200,
            json={"state": "22.5", "attributes": {"unit_of_measurement": "°C"}},
        )
    )

    from main import create_app
    app = create_app(config_path=config_file)
    await app.state.populate_cache()

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/data")

    assert response.status_code == 200
    data = response.json()

    assert len(data["weather"]) == 5
    assert data["weather"][0]["icon"] == "sunny"
    assert len(data["photos"]) == 1
    assert data["photo_interval_seconds"] == 30
