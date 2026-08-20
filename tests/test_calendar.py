from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

import respx
import httpx
import pytest

from config import AppConfig, ICloudConfig, CalendarConfig, WeatherConfig, HomeAssistantConfig, DisplayConfig
from sources.calendar import get_events

FIXTURES = Path(__file__).parent / "fixtures"
SIMPLE_ICS = (FIXTURES / "simple.ics").read_bytes()
RECURRING_ICS = (FIXTURES / "recurring.ics").read_bytes()
RECURRING_OVERRIDE_ICS = (FIXTURES / "recurring_override.ics").read_bytes()

CAL_URL = "http://test.example.com/cal.ics"
RECURRING_URL = "http://test.example.com/recurring.ics"
RECURRING_OVERRIDE_URL = "http://test.example.com/recurring_override.ics"


def make_config(url: str = CAL_URL, color: str = "#FF0000", calendar_days_ahead: int = 2) -> AppConfig:
    return AppConfig(
        icloud=ICloudConfig(share_token="x", photo_interval_seconds=30),
        calendars=[CalendarConfig(name="Test Cal", url=url, color=color)],
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
        home_assistant=HomeAssistantConfig(url="http://ha.local", token="tok", entities=[]),
        display=DisplayConfig(calendar_days_ahead=calendar_days_ahead, weather_days=5),
    )


FIXED_NOW = datetime(2026, 4, 7, 0, 0, 0, tzinfo=timezone.utc)


@respx.mock
async def test_parses_simple_events():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    titles = {e.title for e in events}
    assert "Trh Dka" in titles
    assert "Celodení akce" in titles


@respx.mock
async def test_all_day_events_flagged():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    timed = next(e for e in events if e.title == "Trh Dka")
    all_day = next(e for e in events if e.title == "Celodení akce")

    assert timed.all_day is False
    assert all_day.all_day is True


@respx.mock
async def test_recurring_events_expanded():
    respx.get(RECURRING_URL).mock(return_value=httpx.Response(200, content=RECURRING_ICS))
    cfg = make_config(url=RECURRING_URL, calendar_days_ahead=2)

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    standup_events = [e for e in events if e.title == "Standup"]
    # Window: 2026-04-07 through 2026-04-09 inclusive (calendarDaysAhead+1=3 days)
    assert len(standup_events) == 3
    dates = sorted(e.start.date() for e in standup_events)
    assert dates == [date(2026, 4, 7), date(2026, 4, 8), date(2026, 4, 9)]


@respx.mock
async def test_calendar_color_assigned():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config(color="#4CAF50")

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    assert all(e.color == "#4CAF50" for e in events)


@respx.mock
async def test_exclude_patterns_removes_matching_event():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=CAL_URL, color="#FF0000", exclude_patterns=["trh"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    titles = {e.title for e in events}
    assert "Trh Dka" not in titles
    assert "Celodení akce" in titles


@respx.mock
async def test_exclude_patterns_case_insensitive():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=CAL_URL, color="#FF0000", exclude_patterns=["TRH"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    titles = {e.title for e in events}
    assert "Trh Dka" not in titles
    assert "Celodení akce" in titles


@respx.mock
async def test_exclude_patterns_multiple_patterns():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=CAL_URL, color="#FF0000", exclude_patterns=["trh", "celodení"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    assert events == []


@respx.mock
async def test_exclude_patterns_no_patterns_keeps_all_events():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    # exclude_patterns defaults to [] — no filtering

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    assert len(events) == 2


@respx.mock
async def test_exclude_patterns_filters_recurring_events():
    respx.get(RECURRING_URL).mock(return_value=httpx.Response(200, content=RECURRING_ICS))
    cfg = make_config(url=RECURRING_URL, calendar_days_ahead=2)
    cfg.calendars[0] = CalendarConfig(name="Test Cal", url=RECURRING_URL, color="#FF0000", exclude_patterns=["standup"])

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    assert events == []


@respx.mock
async def test_recurrence_id_override_no_duplicate():
    """A modified occurrence (RECURRENCE-ID) must not produce a duplicate event.

    The fixture has a weekly-Thursday series starting 2026-03-12 14:30 CET.
    The 2026-04-09 occurrence has a RECURRENCE-ID override at 14:30 CEST (+02:00),
    which is 12:30 UTC — one hour earlier than the naïve UTC from the master RRULE
    (13:30 UTC).  Both must collapse to exactly one event on 2026-04-09.
    """
    respx.get(RECURRING_OVERRIDE_URL).mock(return_value=httpx.Response(200, content=RECURRING_OVERRIDE_ICS))
    # calendar_days_ahead=2 puts 2026-04-09 inside the window (FIXED_NOW = 2026-04-07)
    cfg = make_config(url=RECURRING_OVERRIDE_URL, calendar_days_ahead=2)

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    mm_events = [e for e in events if e.title == "MM Sync"]
    assert len(mm_events) == 1, f"Expected 1 MM Sync event, got {len(mm_events)}: {[(e.start, e.title) for e in mm_events]}"
    assert mm_events[0].start.date().isoformat() == "2026-04-09"


@respx.mock
async def test_parse_runs_off_the_event_loop_thread():
    """ICS parsing is CPU-heavy (10-20s for real feeds); it must not run on the event loop."""
    import threading
    from sources import calendar as calendar_module

    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()
    real_parse = calendar_module._parse_ics
    parse_threads: list[int] = []

    def recording_parse(*args, **kwargs):
        parse_threads.append(threading.get_ident())
        return real_parse(*args, **kwargs)

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW), \
            mock.patch("sources.calendar._parse_ics", side_effect=recording_parse):
        await get_events(cfg)

    assert parse_threads, "_parse_ics was never called"
    assert threading.get_ident() not in parse_threads, (
        "_parse_ics ran on the event loop thread and would block sibling fetches"
    )


@respx.mock
async def test_slow_parse_does_not_stall_the_event_loop():
    """A slow parse must not starve other coroutines (the cause of bogus ConnectTimeouts)."""
    import asyncio
    import time as _time

    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=SIMPLE_ICS))
    cfg = make_config()

    def slow_parse(*args, **kwargs):
        _time.sleep(0.4)
        return []

    ticks = 0

    async def heartbeat() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW), \
            mock.patch("sources.calendar._parse_ics", side_effect=slow_parse):
        await get_events(cfg)
    beat.cancel()

    assert ticks >= 10, f"event loop was blocked during parse (only {ticks} ticks in 0.4s)"


# --- Busy masking for ICS calendars (published work feeds) -------------------

BUSY_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260407T090000Z
DTEND:20260407T100000Z
SUMMARY:Confidential client call
LOCATION:Board room
UID:busy-1
END:VEVENT
BEGIN:VEVENT
DTSTART:20260407T110000Z
DTEND:20260407T120000Z
SUMMARY:Timeblock
UID:busy-2
END:VEVENT
END:VCALENDAR"""


def make_busy_config(show_as_busy: bool, exclude=None) -> AppConfig:
    cfg = make_config()
    cfg.calendars = [CalendarConfig(
        name="Blue", url=CAL_URL, color="#2196F3",
        exclude_patterns=exclude or [], show_as_busy=show_as_busy,
    )]
    return cfg


@respx.mock
async def test_ics_show_as_busy_masks_titles_and_location():
    from models import BUSY_LABEL
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=BUSY_ICS))

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(make_busy_config(show_as_busy=True))

    assert len(events) == 2
    assert {e.title for e in events} == {BUSY_LABEL}
    assert all(e.location is None for e in events), "location must not leak when masked"


@respx.mock
async def test_ics_show_as_busy_off_keeps_real_titles():
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=BUSY_ICS))

    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(make_busy_config(show_as_busy=False))

    assert "Confidential client call" in {e.title for e in events}


@respx.mock
async def test_ics_exclude_patterns_match_real_summary_when_masked():
    """Timeblocks must still be filtered even though titles render as busy."""
    from models import BUSY_LABEL
    respx.get(CAL_URL).mock(return_value=httpx.Response(200, content=BUSY_ICS))

    cfg = make_busy_config(show_as_busy=True, exclude=["Time[\\s]?block"])
    with mock.patch("sources.calendar._now_utc", return_value=FIXED_NOW):
        events = await get_events(cfg)

    assert len(events) == 1
    assert events[0].title == BUSY_LABEL
