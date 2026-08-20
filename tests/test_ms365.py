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
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
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
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
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
async def test_event_with_prague_timezone_is_converted_to_utc():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    # 10:00 Prague CEST (UTC+2) should become 08:00 UTC
    event = {
        "id": "e1",
        "subject": "Prague Meeting",
        "start": {"dateTime": "2026-05-24T10:00:00.0000000", "timeZone": "Europe/Prague"},
        "end":   {"dateTime": "2026-05-24T11:00:00.0000000", "timeZone": "Europe/Prague"},
        "isAllDay": False,
    }
    respx.get(GRAPH_CAL).mock(return_value=_events_mock([event]))

    fixed_now = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
    with mock.patch("sources.ms365._now_utc", return_value=fixed_now):
        events = await get_ms365_events(make_config())

    assert len(events) == 1
    assert events[0].start == datetime(2026, 5, 24, 8, 0, 0, tzinfo=timezone.utc)


@respx.mock
async def test_returns_empty_on_graph_failure():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(GRAPH_CAL).mock(return_value=httpx.Response(403, json={"error": {"code": "Forbidden"}}))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_config())

    assert events == []


# --- Named mailbox calendars (e.g. a shared/external work calendar) -----------

CAL_LIST_URL = "https://graph.microsoft.com/v1.0/users/user@test.com/calendars"
NAMED_CAL_ID = "AAMk-ext-cal-id"
NAMED_CAL_VIEW = f"https://graph.microsoft.com/v1.0/users/user@test.com/calendars/{NAMED_CAL_ID}/calendarView"


def make_named_cal_config(**overrides) -> AppConfig:
    from config import Ms365CalendarConfig

    defaults = dict(
        email="user@test.com",
        calendar_name="Work EXT",
        name="Blue",
        color="#2196F3",
    )
    defaults.update(overrides)
    cfg = make_config(users=[])
    cfg.ms365.calendars = [Ms365CalendarConfig(**defaults)]
    return cfg


def _cal_list_mock(names_to_ids: dict) -> httpx.Response:
    return httpx.Response(200, json={"value": [{"id": v, "name": k} for k, v in names_to_ids.items()]})


@respx.mock
async def test_named_calendar_events_are_fetched():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(CAL_LIST_URL).mock(return_value=_cal_list_mock({"Calendar": "default-id", "Work EXT": NAMED_CAL_ID}))
    respx.get(NAMED_CAL_VIEW).mock(return_value=_events_mock([
        _graph_event("DevOps status", "2026-04-07T11:00:00.0000000", "2026-04-07T12:00:00.0000000"),
    ]))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_named_cal_config())

    assert len(events) == 1
    assert events[0].title == "DevOps status"
    assert events[0].calendar_name == "Blue"
    assert events[0].color == "#2196F3"


@respx.mock
async def test_show_as_busy_masks_event_titles():
    from sources.ms365 import BUSY_LABEL, get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(CAL_LIST_URL).mock(return_value=_cal_list_mock({"Work EXT": NAMED_CAL_ID}))
    respx.get(NAMED_CAL_VIEW).mock(return_value=_events_mock([
        _graph_event("Confidential client call", "2026-04-07T11:00:00.0000000", "2026-04-07T12:00:00.0000000"),
    ]))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_named_cal_config(show_as_busy=True))

    assert len(events) == 1
    assert events[0].title == BUSY_LABEL
    assert "Confidential" not in events[0].title


@respx.mock
async def test_exclude_patterns_applied_before_busy_masking():
    """Excludes must match the real subject even when titles are masked."""
    from sources.ms365 import BUSY_LABEL, get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(CAL_LIST_URL).mock(return_value=_cal_list_mock({"Work EXT": NAMED_CAL_ID}))
    respx.get(NAMED_CAL_VIEW).mock(return_value=_events_mock([
        _graph_event("Timeblock", "2026-04-07T09:00:00.0000000", "2026-04-07T10:00:00.0000000", eid="e1"),
        _graph_event("Time block", "2026-04-07T10:00:00.0000000", "2026-04-07T11:00:00.0000000", eid="e2"),
        _graph_event("Real meeting", "2026-04-07T11:00:00.0000000", "2026-04-07T12:00:00.0000000", eid="e3"),
    ]))

    cfg = make_named_cal_config(show_as_busy=True, exclude_patterns=["Time[\\s]?block"])
    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(cfg)

    assert len(events) == 1, "both Timeblock variants should be excluded"
    assert events[0].title == BUSY_LABEL


@respx.mock
async def test_unknown_named_calendar_is_non_fatal():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(CAL_LIST_URL).mock(return_value=_cal_list_mock({"Calendar": "default-id"}))

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(make_named_cal_config())

    assert events == []


@respx.mock
async def test_named_calendar_failure_does_not_drop_user_events():
    from sources.ms365 import get_ms365_events
    respx.post(TOKEN_URL).mock(return_value=_token_mock())
    respx.get(GRAPH_CAL).mock(return_value=_events_mock([
        _graph_event("Team Meeting", "2026-04-07T10:00:00.0000000", "2026-04-07T11:00:00.0000000"),
    ]))
    respx.get(CAL_LIST_URL).mock(return_value=httpx.Response(500))

    cfg = make_config()
    from config import Ms365CalendarConfig
    cfg.ms365.calendars = [Ms365CalendarConfig(email="user@test.com", calendar_name="Work EXT", name="Blue", color="#2196F3")]

    with mock.patch("sources.ms365._now_utc", return_value=FIXED_NOW):
        events = await get_ms365_events(cfg)

    assert [e.title for e in events] == ["Team Meeting"]
