from datetime import datetime, timezone
from unittest import mock

import httpx
import pytest
import respx

from config import AppConfig, ICloudConfig, WeatherConfig, HomeAssistantConfig, DisplayConfig, Ms365Config, Ms365UserConfig

TENANT_ID = "test-tenant"
CLIENT_ID = "test-client"
CLIENT_SECRET = "test-secret"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_CAL = "https://graph.microsoft.com/v1.0/users/user@test.com/calendarView"

FIXED_NOW = datetime(2026, 4, 7, 0, 0, 0, tzinfo=timezone.utc)
ACCESS_TOKEN = "test-access-token"


def make_config(users=None) -> AppConfig:
    if users is None:
        users = [Ms365UserConfig(email="user@test.com", name="User", color="#FF0000")]
    return AppConfig(
        icloud=ICloudConfig(share_token="x", photo_interval_seconds=30),
        calendars=[],
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0, accuweather_api_key=""),
        home_assistant=HomeAssistantConfig(url="http://ha.local", token="tok", entities=[]),
        display=DisplayConfig(calendar_days_ahead=2, weather_days=5),
        ms365=Ms365Config(tenant_id=TENANT_ID, client_id=CLIENT_ID, client_secret=CLIENT_SECRET, users=users),
    )


def _token_mock():
    return httpx.Response(200, json={"access_token": ACCESS_TOKEN, "expires_in": 3600})


def _events_mock(events: list) -> httpx.Response:
    return httpx.Response(200, json={"value": events})


def _graph_event(subject: str, start: str, end: str, is_all_day: bool = False, eid: str = "e1") -> dict:
    return {
        "id": eid,
        "subject": subject,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
        "isAllDay": is_all_day,
    }


@respx.mock
async def test_fetches_token_and_returns_events():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(GRAPH_CAL).mock(return_value=_events_mock([
        _graph_event("Team Meeting", "2026-04-07T10:00:00.0000000", "2026-04-07T11:00:00.0000000"),
    ]))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config())

    assert len(events) == 1
    assert events[0].title == "Team Meeting"


@respx.mock
async def test_all_day_event_flagged():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(GRAPH_CAL).mock(return_value=_events_mock([
        _graph_event("Holiday", "2026-04-07T00:00:00.0000000", "2026-04-08T00:00:00.0000000", is_all_day=True),
    ]))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config())

    assert events[0].all_day is True


@respx.mock
async def test_timed_event_not_all_day():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(GRAPH_CAL).mock(return_value=_events_mock([
        _graph_event("Standup", "2026-04-07T09:00:00.0000000", "2026-04-07T09:30:00.0000000", is_all_day=False),
    ]))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config())

    assert events[0].all_day is False


@respx.mock
async def test_user_color_assigned():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(GRAPH_CAL).mock(return_value=_events_mock([
        _graph_event("Event", "2026-04-07T10:00:00.0000000", "2026-04-07T11:00:00.0000000"),
    ]))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config())

    assert events[0].color == "#FF0000"


@respx.mock
async def test_fetches_multiple_users():
    from sources.ms365 import get_ms365_events
    users = [
        Ms365UserConfig(email="user1@test.com", name="User1", color="#F44336"),
        Ms365UserConfig(email="user2@test.com", name="User2", color="#FF9800"),
    ]
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get("https://graph.microsoft.com/v1.0/users/user1@test.com/calendarView").mock(
        return_value=_events_mock([_graph_event("User1 Event", "2026-04-07T09:00:00.0000000", "2026-04-07T10:00:00.0000000", eid="e1")])
    )
    respx.get("https://graph.microsoft.com/v1.0/users/user2@test.com/calendarView").mock(
        return_value=_events_mock([_graph_event("User2 Event", "2026-04-07T11:00:00.0000000", "2026-04-07T12:00:00.0000000", eid="e2")])
    )

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config(users=users))

    titles = {e.title for e in events}
    assert "User1 Event" in titles
    assert "User2 Event" in titles


async def test_returns_empty_when_ms365_not_configured():
    from sources.ms365 import get_ms365_events
    cfg = AppConfig(
        icloud=ICloudConfig(share_token="x", photo_interval_seconds=30),
        calendars=[],
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0, accuweather_api_key=""),
        home_assistant=HomeAssistantConfig(url="http://ha.local", token="tok", entities=[]),
        display=DisplayConfig(calendar_days_ahead=2, weather_days=5),
    )

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(cfg)

    assert events == []


@respx.mock
async def test_returns_empty_on_auth_failure():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized_client"}))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config())

    assert events == []


@respx.mock
async def test_returns_empty_on_graph_failure():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(GRAPH_CAL).mock(return_value=httpx.Response(403, json={"error": {"code": "Forbidden"}}))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config())

    assert events == []
