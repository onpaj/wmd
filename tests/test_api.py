import json
import pytest
import httpx
from httpx import ASGITransport
from main import _backoff_delay


@pytest.fixture
def config_file(tmp_path):
    config = {
        "icloud": {"shareToken": "", "photoIntervalSeconds": 30},
        "calendars": [],
        "weather": {"provider": "openmeteo", "latitude": 50.07, "longitude": 14.43},
        "homeAssistant": {"url": "http://homeassistant.local:8123", "token": "", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))
    return str(p)


@pytest.fixture
def app(config_file):
    from main import create_app
    return create_app(config_path=config_file)


async def test_api_data_returns_200(app):
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/data")
    assert response.status_code == 200
    data = response.json()
    assert "photos" in data
    assert "events" in data
    assert "weather" in data
    assert "ha_entities" in data
    assert "photo_interval_seconds" in data
    assert "server_time" in data


async def test_static_index_served(app):
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200


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
