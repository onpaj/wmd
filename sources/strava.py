import asyncio
import json
import logging
from datetime import date, datetime, timedelta

import httpx

from config import AppConfig, StravaPersonConfig
from models import StravaDay, StravaMeals, StravaPersonStatus

logger = logging.getLogger(__name__)

_BASE = "https://app.strava.cz/api"
_S5URL = "https://wss52.strava.cz/WSStravne5_13/WSStravne5.svc"
_HEADERS = {
    "Content-Type": "text/plain;charset=UTF-8",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://app.strava.cz/en",
}


async def _post(client: httpx.AsyncClient, endpoint: str, body: dict) -> object:
    resp = await client.post(
        f"{_BASE}/{endpoint}",
        content=json.dumps(body),
        headers=_HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


async def _fetch_account_days(
    client: httpx.AsyncClient,
    parent_sid: str,
    cislo: str,
    account_id: str,
) -> dict[date, tuple[str | None, str | None, bool]]:
    """Login to one canteen sub-account, fetch its order schedule.
    Returns {date: (soup, meal, ordered)}.
    """
    account_sid: str = await _post(client, "canteenLoginPA", {  # type: ignore[assignment]
        "sid": parent_sid,
        "cislo": cislo,
        "id": account_id,
        "environment": "W",
        "lang": "EN",
    })
    if not isinstance(account_sid, str):
        raise ValueError(f"canteenLoginPA returned unexpected type {type(account_sid)!r}, expected str")
    # nactiVlastnostiPA is required to initialize the S5 server session
    await _post(client, "nactiVlastnostiPA", {
        "sid": account_sid,
        "url": _S5URL,
        "cislo": cislo,
        "lang": "EN",
        "ignoreCert": False,
        "getText": True,
        "checkVersion": True,
        "frontendFunction": "loginCanteenUsingPA",
    })
    orders = await _post(client, "objednavky", {
        "cislo": cislo,
        "sid": account_sid,
        "s5url": _S5URL,
        "lang": "EN",
        "konto": 0,
        "podminka": "",
        "ignoreCert": "false",
    })

    result: dict[date, tuple[str | None, str | None, bool]] = {}
    i = 0
    while f"table{i}" in orders:
        rows = orders[f"table{i}"]
        soup_row = next((r for r in rows if r.get("druh") == "PO"), None)
        meal_row = next((r for r in rows if r.get("druh") == "OB"), None)
        if meal_row:
            d = datetime.strptime(meal_row["datum"], "%d.%m.%Y").date()
            result[d] = (
                soup_row["nazev"] if soup_row else None,
                meal_row.get("nazev"),
                (meal_row.get("pocet") or 0) > 0,
            )
        i += 1
    return result


async def get_strava_meals(cfg: AppConfig, _today: date | None = None) -> StravaMeals | None:
    """Fetch today's and tomorrow's meal schedule per configured person.

    _today is injectable for testing; defaults to date.today() in production.
    Raises on parent login failure so the refresh loop can back off.
    Per-account failures are isolated: that account contributes nothing to person ordering.
    """
    if cfg.strava is None or not cfg.strava.people:
        return None

    s = cfg.strava
    today = _today or date.today()
    tomorrow = today + timedelta(days=1)

    # Collect unique account ids across all people (avoid duplicate fetches)
    all_account_ids: list[str] = []
    seen: set[str] = set()
    for person in s.people:
        for aid in person.accounts:
            if aid not in seen:
                all_account_ids.append(aid)
                seen.add(aid)

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Parent login raises on failure → propagates to _refresh_loop for backoff
        login_data = await _post(client, "loginPA", {
            "email": s.email,
            "heslo": s.password,
            "zustatPrihlasen": False,
            "lang": "EN",
        })
        parent_sid: str = login_data["SID"]

        async def _one(account_id: str) -> tuple[str, dict[date, tuple] | None]:
            try:
                days = await _fetch_account_days(client, parent_sid, s.canteen_number, account_id)
                return account_id, days
            except Exception:
                logger.exception("Strava fetch failed for account %s", account_id)
                return account_id, None

        results = dict(await asyncio.gather(*[_one(aid) for aid in all_account_ids]))

    def _canonical_text(day: date) -> tuple[str | None, str | None] | None:
        """Take meal text from the first account that has data for this day."""
        for aid in all_account_ids:
            days_map = results.get(aid)
            if days_map and day in days_map:
                soup, meal, _ = days_map[day]
                return soup, meal
        return None

    def _aggregate_ordered(person: StravaPersonConfig, day: date) -> bool | None:
        """OR over person's accounts. None if all accounts failed or have no data for this day."""
        saw_data = False
        for aid in person.accounts:
            days_map = results.get(aid)
            if days_map is None:
                continue
            entry = days_map.get(day)
            if entry is None:
                continue
            saw_data = True
            if entry[2]:
                return True
        return False if saw_data else None

    def _build_day(day: date) -> StravaDay | None:
        text = _canonical_text(day)
        if text is None:
            return None
        soup, meal = text
        return StravaDay(
            date=day.isoformat(),
            soup=soup,
            meal=meal,
            people=[
                StravaPersonStatus(
                    name=p.name,
                    color=p.color,
                    ordered=_aggregate_ordered(p, day),
                )
                for p in s.people
            ],
        )

    return StravaMeals(
        today=_build_day(today),
        tomorrow=_build_day(tomorrow),
        breaking_time=s.breaking_time,
    )
