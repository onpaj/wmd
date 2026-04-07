import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

import httpx

from config import AppConfig
from models import CalendarEvent


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_graph_datetime(dt_str: str) -> datetime:
    # Strip sub-second precision beyond microseconds then parse as UTC
    dot = dt_str.find(".")
    if dot != -1:
        dt_str = dt_str[:dot + 7]  # keep up to 6 fractional digits
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
    return datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


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
            start = _parse_graph_datetime(item["start"]["dateTime"])
            end = _parse_graph_datetime(item["end"]["dateTime"])
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


async def get_ms365_events(cfg: AppConfig) -> list[CalendarEvent]:
    if cfg.ms365 is None:
        return []

    now = _now_utc()
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=cfg.display.calendar_days_ahead + 1)

    async with httpx.AsyncClient() as client:
        try:
            token = await _get_token(client, cfg.ms365.tenant_id, cfg.ms365.client_id, cfg.ms365.client_secret)
        except Exception:
            return []

        results = await asyncio.gather(*[
            _fetch_user_events(client, token, u.email, u.name, u.color, window_start, window_end)
            for u in cfg.ms365.users
        ])

    all_events: list[CalendarEvent] = []
    for events in results:
        all_events.extend(events)

    all_events.sort(key=lambda e: (e.start.date(), not e.all_day, e.start))
    return all_events
