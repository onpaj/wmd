import asyncio
import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from dateutil.rrule import rrulestr
from icalendar import Calendar

from config import AppConfig, CalendarConfig
from models import CalendarEvent


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_datetime(dt: Any) -> datetime:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    # date (all-day)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def _parse_ics(
    content: bytes,
    cal_cfg: CalendarConfig,
    window_start: datetime,
    window_end: datetime,
) -> list[CalendarEvent]:
    cal = Calendar.from_ical(content)
    events: list[CalendarEvent] = []
    compiled = [re.compile(p, re.IGNORECASE) for p in cal_cfg.exclude_patterns]

    # First pass: collect RECURRENCE-ID overrides per UID, stored as calendar dates.
    # These are modified (or deleted) occurrences; their original date must be
    # skipped when expanding the master RRULE to avoid showing both the original
    # and the rescheduled version.  We match by date rather than exact UTC time
    # because RRULE expansion uses ignoretz=True (naive UTC from winter DTSTART)
    # while RECURRENCE-ID datetimes carry summer/winter offsets — the two can
    # differ by an hour across DST transitions.
    recurrence_overrides: dict[str, set[date]] = {}
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        recurrence_id_prop = component.get("RECURRENCE-ID")
        if recurrence_id_prop is None:
            continue
        uid = str(component.get("UID", ""))
        rid = recurrence_id_prop.dt
        rid_date = rid if isinstance(rid, date) and not isinstance(rid, datetime) else _to_utc_datetime(rid).date()
        recurrence_overrides.setdefault(uid, set()).add(rid_date)

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart_prop = component.get("DTSTART")
        if dtstart_prop is None:
            continue
        raw_start = dtstart_prop.dt

        dtend_prop = component.get("DTEND") or component.get("DUE")
        raw_end = dtend_prop.dt if dtend_prop else raw_start

        all_day = isinstance(raw_start, date) and not isinstance(raw_start, datetime)

        uid = str(component.get("UID", ""))
        summary = str(component.get("SUMMARY", ""))
        location_raw = component.get("LOCATION")
        location = str(location_raw) if location_raw else None

        if compiled and any(rx.search(summary) for rx in compiled):
            continue

        if "RRULE" in component:
            # Expand recurring events
            rrule_str = component["RRULE"].to_ical().decode()
            dtstart_dt = _to_utc_datetime(raw_start)

            # For timezone-aware events, expand in the original timezone so that
            # wall-clock time is preserved across DST transitions (e.g. a 09:00
            # CET event should still show as 09:00 CEST in summer, not 10:00).
            # For floating/naive datetimes there is no timezone to preserve, so
            # we fall back to treating them as UTC.
            has_tz = isinstance(raw_start, datetime) and raw_start.tzinfo is not None
            if has_tz:
                rule = rrulestr(rrule_str, dtstart=raw_start, ignoretz=False)
            else:
                dtstart_naive = dtstart_dt.replace(tzinfo=None)
                rule = rrulestr(rrule_str, dtstart=dtstart_naive, ignoretz=True)

            # Collect EXDATE values (naive UTC)
            exdates: set[datetime] = set()
            exdate_prop = component.get("EXDATE")
            if exdate_prop is not None:
                props = exdate_prop if isinstance(exdate_prop, list) else [exdate_prop]
                for prop in props:
                    for exdt in prop.dts:
                        exdates.add(_to_utc_datetime(exdt.dt).replace(tzinfo=None))

            # Also skip occurrences that have a RECURRENCE-ID override (those
            # VEVENTs are processed separately as standalone events below).
            # Match by date only — exact UTC times differ across DST transitions.
            override_dates = recurrence_overrides.get(uid, set())

            duration = _to_utc_datetime(raw_end) - dtstart_dt

            if has_tz:
                for occurrence in rule.between(window_start, window_end, inc=True):
                    occ_start = occurrence.astimezone(timezone.utc)
                    if occ_start.replace(tzinfo=None) in exdates or occ_start.date() in override_dates:
                        continue
                    occ_end = occ_start + duration
                    event_id = hashlib.md5(f"{uid}-{occ_start.isoformat()}".encode()).hexdigest()
                    events.append(
                        CalendarEvent(
                            id=event_id,
                            title=summary,
                            start=occ_start,
                            end=occ_end,
                            all_day=all_day,
                            calendar_name=cal_cfg.name,
                            color=cal_cfg.color,
                            location=location,
                        )
                    )
            else:
                for occurrence in rule.between(
                    window_start.replace(tzinfo=None),
                    window_end.replace(tzinfo=None),
                    inc=True,
                ):
                    if occurrence in exdates or occurrence.date() in override_dates:
                        continue
                    occ_start = occurrence.replace(tzinfo=timezone.utc)
                    occ_end = occ_start + duration
                    event_id = hashlib.md5(f"{uid}-{occ_start.isoformat()}".encode()).hexdigest()
                    events.append(
                        CalendarEvent(
                            id=event_id,
                            title=summary,
                            start=occ_start,
                            end=occ_end,
                            all_day=all_day,
                            calendar_name=cal_cfg.name,
                            color=cal_cfg.color,
                            location=location,
                        )
                    )
        else:
            start_dt = _to_utc_datetime(raw_start)
            end_dt = _to_utc_datetime(raw_end)

            if start_dt >= window_end or end_dt <= window_start:
                continue

            event_id = hashlib.md5(f"{uid}-{start_dt.isoformat()}".encode()).hexdigest()
            events.append(
                CalendarEvent(
                    id=event_id,
                    title=summary,
                    start=start_dt,
                    end=end_dt,
                    all_day=all_day,
                    calendar_name=cal_cfg.name,
                    color=cal_cfg.color,
                    location=location,
                )
            )

    return events


async def _fetch_calendar(
    client: httpx.AsyncClient,
    cal_cfg: CalendarConfig,
    window_start: datetime,
    window_end: datetime,
) -> list[CalendarEvent]:
    try:
        resp = await client.get(cal_cfg.url)
        resp.raise_for_status()
        return _parse_ics(resp.content, cal_cfg, window_start, window_end)
    except Exception:
        return []


async def get_mini_cal_events(cfg: AppConfig) -> list[CalendarEvent]:
    if not cfg.mini_calendar.url:
        return []
    now = _now_utc()
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(weeks=3)

    cal_cfg = CalendarConfig(name="mini", url=cfg.mini_calendar.url, color=cfg.mini_calendar.color)
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await _fetch_calendar(client, cal_cfg, window_start, window_end)


async def get_events(cfg: AppConfig) -> list[CalendarEvent]:
    now = _now_utc()
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=cfg.display.calendar_days_ahead + 1)

    async with httpx.AsyncClient(timeout=20.0) as client:
        results = await asyncio.gather(
            *[_fetch_calendar(client, cal, window_start, window_end) for cal in cfg.calendars]
        )

    all_events: list[CalendarEvent] = []
    for events in results:
        all_events.extend(events)

    # Clamp start to today for events that began before today but are still ongoing
    # (e.g. multi-day all-day events) so they appear under today, not a past date.
    clamped: list[CalendarEvent] = []
    for ev in all_events:
        if ev.start < window_start < ev.end:
            ev = ev.model_copy(update={"start": window_start})
        clamped.append(ev)

    clamped.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
    return clamped
