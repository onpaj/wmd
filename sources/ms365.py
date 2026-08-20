import asyncio
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from config import AppConfig, Ms365CalendarConfig
from models import CalendarEvent

logger = logging.getLogger(__name__)

# Shown instead of the real subject when a calendar is configured with
# ``showAsBusy`` — work items appear on the wall display as a time block
# without revealing what they are.
BUSY_LABEL = "Zaneprázdněn"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_graph_datetime(dt_str: str, tz_str: str = "UTC") -> datetime:
    from zoneinfo import ZoneInfo
    dot = dt_str.find(".")
    if dot != -1:
        dt_str = dt_str[:dot + 7]  # keep up to 6 fractional digits
        naive = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f")
    else:
        naive = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")

    if tz_str.upper() == "UTC":
        return naive.replace(tzinfo=timezone.utc)
    return naive.replace(tzinfo=ZoneInfo(tz_str)).astimezone(timezone.utc)


async def _get_token(client: httpx.AsyncClient, tenant_id: str, client_id: str, client_secret: str) -> str:
    resp = await client.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _fetch_user_events(
    client: httpx.AsyncClient,
    token: str,
    email: str,
    name: str,
    color: str,
    window_start: datetime,
    window_end: datetime,
) -> list[CalendarEvent]:
    try:
        resp = await client.get(
            f"https://graph.microsoft.com/v1.0/users/{email}/calendarView",
            params={
                "startDateTime": window_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "endDateTime": window_end.strftime("%Y-%m-%dT%H:%M:%S"),
                "$top": "100",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Prefer": 'outlook.timezone="UTC"',
            },
        )
        resp.raise_for_status()
        events = []
        for item in resp.json().get("value", []):
            start = _parse_graph_datetime(item["start"]["dateTime"], item["start"].get("timeZone", "UTC"))
            end = _parse_graph_datetime(item["end"]["dateTime"], item["end"].get("timeZone", "UTC"))
            event_id = hashlib.md5(f"{email}-{item['id']}".encode()).hexdigest()
            events.append(CalendarEvent(
                id=event_id,
                title=item.get("subject", ""),
                start=start,
                end=end,
                all_day=item.get("isAllDay", False),
                calendar_name=name,
                color=color,
            ))
        return events
    except Exception:
        return []


async def _resolve_calendar_id(
    client: httpx.AsyncClient, token: str, email: str, calendar_name: str
) -> str | None:
    resp = await client.get(
        f"https://graph.microsoft.com/v1.0/users/{email}/calendars",
        params={"$select": "id,name", "$top": "100"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    for item in resp.json().get("value", []):
        if item.get("name") == calendar_name:
            return item.get("id")
    return None


async def _fetch_named_calendar_events(
    client: httpx.AsyncClient,
    token: str,
    cal_cfg: Ms365CalendarConfig,
    window_start: datetime,
    window_end: datetime,
) -> list[CalendarEvent]:
    """Read one named calendar from a mailbox. Never raises — a failure here
    must not drop the other calendars from the dashboard."""
    try:
        calendar_id = await _resolve_calendar_id(client, token, cal_cfg.email, cal_cfg.calendar_name)
        if calendar_id is None:
            logger.warning(
                "MS365 calendar %r not found in mailbox %s", cal_cfg.calendar_name, cal_cfg.email
            )
            return []

        resp = await client.get(
            f"https://graph.microsoft.com/v1.0/users/{cal_cfg.email}/calendars/{calendar_id}/calendarView",
            params={
                "startDateTime": window_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "endDateTime": window_end.strftime("%Y-%m-%dT%H:%M:%S"),
                "$top": "100",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Prefer": 'outlook.timezone="UTC"',
            },
        )
        resp.raise_for_status()

        compiled = [re.compile(p, re.IGNORECASE) for p in cal_cfg.exclude_patterns]
        events = []
        for item in resp.json().get("value", []):
            subject = item.get("subject", "")
            # Filter on the real subject — masking happens afterwards, so
            # exclude patterns keep working when show_as_busy is set.
            if compiled and any(rx.search(subject) for rx in compiled):
                continue
            start = _parse_graph_datetime(item["start"]["dateTime"], item["start"].get("timeZone", "UTC"))
            end = _parse_graph_datetime(item["end"]["dateTime"], item["end"].get("timeZone", "UTC"))
            event_id = hashlib.md5(f"{cal_cfg.email}-{cal_cfg.calendar_name}-{item['id']}".encode()).hexdigest()
            events.append(CalendarEvent(
                id=event_id,
                title=BUSY_LABEL if cal_cfg.show_as_busy else subject,
                start=start,
                end=end,
                all_day=item.get("isAllDay", False),
                calendar_name=cal_cfg.name,
                color=cal_cfg.color,
            ))
        return events
    except Exception as exc:
        logger.warning(
            "MS365 calendar '%s' (%s) fetch failed: %r", cal_cfg.name, cal_cfg.calendar_name, exc
        )
        return []


async def get_ms365_events(cfg: AppConfig) -> list[CalendarEvent]:
    if cfg.ms365 is None:
        return []

    now = _now_utc()
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=cfg.display.calendar_days_ahead + 1)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            token = await _get_token(client, cfg.ms365.tenant_id, cfg.ms365.client_id, cfg.ms365.client_secret)
        except Exception:
            return []

        results = await asyncio.gather(*[
            _fetch_user_events(client, token, u.email, u.name, u.color, window_start, window_end)
            for u in cfg.ms365.users
        ] + [
            _fetch_named_calendar_events(client, token, c, window_start, window_end)
            for c in cfg.ms365.calendars
        ])

    all_events: list[CalendarEvent] = []
    for events in results:
        all_events.extend(events)

    all_events.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
    return all_events
