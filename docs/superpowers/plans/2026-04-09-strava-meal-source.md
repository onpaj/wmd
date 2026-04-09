# Strava Meal Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace WMD's Home Assistant meal sensor integration with a native Python source that fetches meal schedules directly from `app.strava.cz`, adding per-person ordered status shown as colored dots under the meal text.

**Architecture:** A new `sources/strava.py` follows the existing source pattern — async function, Pydantic models, registered in the background refresh loop with stale-while-revalidate. Config groups Strava sub-accounts under named people (e.g. "Ondra" owns two accounts); a person is "ordered" if any of their accounts has `pocet > 0` (OR aggregation). The breaking time (today vs tomorrow switch, previously hardcoded 12:30) becomes configurable in `config.json` and flows through to the frontend via the `StravaMeals` model.

**Tech Stack:** Python 3.11+, httpx (already in requirements), Pydantic v2, respx (already used in tests), TypeScript (frontend), esbuild (already used for bundling)

---

## File Map

**Create:**
- `sources/strava.py` — async login + order fetch + person-level aggregation
- `tests/test_strava.py` — unit tests for `get_strava_meals`

**Modify:**
- `config.py:33-86` — add `StravaPersonConfig`, `StravaConfig` dataclasses; add `strava` field to `AppConfig`; add parsing in `load_config`
- `models.py:37-63` — replace `Meals` with `StravaPersonStatus`, `StravaDay`, `StravaMeals`; update `DashboardData.meals`
- `sources/homeassistant.py:1-7,25-47` — remove `Meals` import, delete `get_meals` function
- `main.py:16,22-31,63-96,129-137` — swap `get_meals` → `get_strava_meals`; TTL 300 → 1800
- `src/types.ts:32-54` — replace `Meals` interface with `StravaPersonStatus`, `StravaDay`, `StravaMeals`
- `src/modules/clock.ts` — replace `isBefore1230` + rendering with configurable breaking time + dots
- `static/css/clock.css:41+` — append marks styles
- `config.json` — remove 4 meal entity ID keys; add `strava` block
- `config.example.json` — add `strava` stub

**Reference only (do not modify):**
- `/Users/pajgrtondrej/Work/GitHub/Strava/fetch_orders.js` — original Node port reference

---

### Task 1: Strava config model

**Files:**
- Modify: `config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing config test**

Add to the bottom of `tests/test_config.py`:

```python
def test_load_config_parses_strava_block(tmp_path):
    data = {
        "icloud": {"shareToken": "t", "photoIntervalSeconds": 30},
        "calendars": [],
        "weather": {"provider": "openmeteo", "latitude": 50.0, "longitude": 14.0},
        "homeAssistant": {"url": "http://ha.local", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
        "strava": {
            "email": "test@example.com",
            "password": "secret",
            "canteenNumber": "1019",
            "breakingTime": "13:00",
            "people": [
                {"name": "Alice", "color": "#4CAF50", "accounts": ["alice.test"]},
                {"name": "Bob",   "color": "#2196F3", "accounts": ["bob.test1", "bob.test2"]},
            ],
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))

    cfg = load_config(str(config_file))

    assert cfg.strava is not None
    assert cfg.strava.email == "test@example.com"
    assert cfg.strava.canteen_number == "1019"
    assert cfg.strava.breaking_time == "13:00"
    assert len(cfg.strava.people) == 2
    assert cfg.strava.people[0].name == "Alice"
    assert cfg.strava.people[0].accounts == ["alice.test"]
    assert cfg.strava.people[1].name == "Bob"
    assert cfg.strava.people[1].accounts == ["bob.test1", "bob.test2"]


def test_load_config_strava_absent_when_not_configured(sample_config):
    cfg = load_config(sample_config)
    assert cfg.strava is None


def test_load_config_strava_breaking_time_defaults_to_1230(tmp_path):
    data = {
        "icloud": {"shareToken": "t", "photoIntervalSeconds": 30},
        "calendars": [],
        "weather": {"provider": "openmeteo", "latitude": 50.0, "longitude": 14.0},
        "homeAssistant": {"url": "http://ha.local", "token": "tok", "entities": []},
        "display": {"calendarDaysAhead": 2, "weatherDays": 5},
        "strava": {
            "email": "t@e.com",
            "password": "p",
            "people": [],
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))

    cfg = load_config(str(config_file))

    assert cfg.strava.breaking_time == "12:30"
    assert cfg.strava.canteen_number == "1019"
```

Also add `StravaConfig, StravaPersonConfig` to the import line at the top of the test file (currently `from config import load_config`):

```python
from config import load_config, StravaConfig, StravaPersonConfig
```

- [ ] **Step 2: Run test to confirm it fails**

```
cd /Users/pajgrtondrej/Work/GitHub/WMD
pytest tests/test_config.py::test_load_config_parses_strava_block -v
```

Expected: `ImportError` or `AttributeError` — `StravaConfig` not defined yet.

- [ ] **Step 3: Add the dataclasses to `config.py`**

Add after the `Ms365Config` class (after line 75, before `AppConfig`):

```python
@dataclass
class StravaPersonConfig:
    name: str
    accounts: list[str]
    color: Optional[str] = None


@dataclass
class StravaConfig:
    email: str
    password: str
    canteen_number: str = "1019"
    breaking_time: str = "12:30"
    people: list[StravaPersonConfig] = field(default_factory=list)
```

Add `strava: Optional[StravaConfig] = None` to `AppConfig` (after `ms365`):

```python
@dataclass
class AppConfig:
    icloud: ICloudConfig
    calendars: list[CalendarConfig]
    weather: WeatherConfig
    home_assistant: HomeAssistantConfig
    display: DisplayConfig
    mini_calendar: MiniCalendarConfig = field(default_factory=lambda: MiniCalendarConfig(url="", color="#FFC107"))
    ms365: Optional[Ms365Config] = None
    strava: Optional[StravaConfig] = None
```

Add parsing at the bottom of `load_config`, just before the `return AppConfig(...)` call:

```python
    strava = None
    if "strava" in data:
        s = data["strava"]
        strava = StravaConfig(
            email=s["email"],
            password=s["password"],
            canteen_number=s.get("canteenNumber", "1019"),
            breaking_time=s.get("breakingTime", "12:30"),
            people=[
                StravaPersonConfig(
                    name=p["name"],
                    accounts=list(p["accounts"]),
                    color=p.get("color"),
                )
                for p in s.get("people", [])
            ],
        )
```

Also pass `strava=strava` in the final `return AppConfig(...)` call.

- [ ] **Step 4: Run all config tests**

```
pytest tests/test_config.py -v
```

Expected: all pass. Output ends with something like `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add StravaConfig to config model"
```

---

### Task 2: Replace Meals with StravaMeals + remove HA meal code

This task is atomic: `Meals` is removed from `models.py`, its import in `homeassistant.py` is removed, and its usage in `main.py` is temporarily set to `None`. All existing tests must continue to pass after this task.

**Files:**
- Modify: `models.py`
- Modify: `sources/homeassistant.py`
- Modify: `main.py`

- [ ] **Step 1: Replace `Meals` in `models.py`**

Replace the `Meals` class (lines 37-41) with:

```python
class StravaPersonStatus(BaseModel):
    name: str
    color: str | None = None
    ordered: bool | None = None   # None = fetch failed for all of this person's accounts


class StravaDay(BaseModel):
    date: str                      # "YYYY-MM-DD"
    soup: str | None
    meal: str | None
    people: list[StravaPersonStatus]


class StravaMeals(BaseModel):
    today: StravaDay | None
    tomorrow: StravaDay | None
    breaking_time: str             # "HH:MM" — before this show today, at/after show tomorrow
```

In `DashboardData` (around line 59), change:

```python
    meals: Meals | None
```

to:

```python
    meals: StravaMeals | None
```

- [ ] **Step 2: Remove `Meals` from `sources/homeassistant.py`**

Change the import at line 6 from:

```python
from models import GardenTemps, HaEntity, Meals
```

to:

```python
from models import GardenTemps, HaEntity
```

Delete the entire `get_meals` function (lines 25-47 inclusive):

```python
async def get_meals(cfg: AppConfig) -> Meals | None:
    ha = cfg.home_assistant
    ids = [ha.soup_today_entity_id, ha.soup_tomorrow_entity_id, ha.lunch_today_entity_id, ha.lunch_tomorrow_entity_id]
    if not all(ids):
        return None

    ha_url = ha.url.rstrip("/")
    token = ha.token
    async with httpx.AsyncClient(timeout=10.0) as client:
        results = await asyncio.gather(
            *[_fetch_entity(client, ha_url, token, eid, "") for eid in ids],
            return_exceptions=True,
        )

    def _state(r: object) -> str:
        return r.state if isinstance(r, HaEntity) else ""

    return Meals(
        soup_today=_state(results[0]),
        soup_tomorrow=_state(results[1]),
        lunch_today=_state(results[2]),
        lunch_tomorrow=_state(results[3]),
    )
```

- [ ] **Step 3: Remove meal entity ID fields from `HomeAssistantConfig` in `config.py`**

In `HomeAssistantConfig`, delete these four lines (38-41):

```python
    lunch_today_entity_id: str = ""
    lunch_tomorrow_entity_id: str = ""
    soup_today_entity_id: str = ""
    soup_tomorrow_entity_id: str = ""
```

In `load_config`, delete these four lines (~121-124):

```python
        lunch_today_entity_id=ha_data.get("lunchTodayEntityId", ""),
        lunch_tomorrow_entity_id=ha_data.get("lunchTomorrowEntityId", ""),
        soup_today_entity_id=ha_data.get("soupTodayEntityId", ""),
        soup_tomorrow_entity_id=ha_data.get("soupTomorrowEntityId", ""),
```

- [ ] **Step 4: Update `main.py` to remove `get_meals` references**

Change the import at line 16 from:

```python
from sources.homeassistant import get_entities, get_garden_temps, get_meals, get_outdoor_temp
```

to:

```python
from sources.homeassistant import get_entities, get_garden_temps, get_outdoor_temp
```

In `_populate_cache`, the `asyncio.gather` call includes `get_meals(config)` as one of the arguments. Remove it. The gather call currently destructures to `photos, ics_events, ms365_events, mini_cal, forecast, ha, meals, outdoor_temp, garden_temps`. After removing `get_meals(config)`:

```python
        photos, ics_events, ms365_events, mini_cal, forecast, ha, outdoor_temp, garden_temps = await asyncio.gather(
            get_photos(config),
            get_events(config),
            get_ms365_events(config),
            get_mini_cal_events(config),
            get_forecast(config),
            get_entities(config),
            get_outdoor_temp(config),
            get_garden_temps(config),
            return_exceptions=True,
        )
```

Also delete the meals cache line that follows:

```python
        if not isinstance(meals, BaseException):
            cache.set("meals", meals, _TTLS["meals"])
```

In `startup`, delete this line (~135):

```python
        asyncio.create_task(_refresh_loop("meals", lambda: get_meals(config), _TTLS["meals"]))
```

- [ ] **Step 5: Run all tests to confirm nothing broke**

```
pytest -v
```

Expected: all tests pass. The `meals` field in `/api/data` now always returns `null` (that's expected — the Strava source isn't wired yet).

- [ ] **Step 6: Commit**

```bash
git add models.py sources/homeassistant.py config.py main.py
git commit -m "refactor: replace Meals model with StravaMeals, remove HA meal source"
```

---

### Task 3: Implement `sources/strava.py`

**Files:**
- Create: `sources/strava.py`
- Create: `tests/test_strava.py`

#### Strava API contract (ported from `Strava/fetch_orders.js`)

All calls: `POST https://app.strava.cz/api/{endpoint}`, headers `Content-Type: text/plain;charset=UTF-8`, `User-Agent: Mozilla/5.0`, `Referer: https://app.strava.cz/en`, body is `json.dumps(payload)`.

- `loginPA {email, heslo, zustatPrihlasen:false, lang:"EN"}` → JSON object with key `SID` (uppercase)
- `canteenLoginPA {sid:parentSid, cislo, id:accountId, environment:"W", lang:"EN"}` → JSON string (e.g. `"account-sid-456"`)
- `nactiVlastnostiPA {sid:accountSid, url:s5url, cislo, lang:"EN", ignoreCert:false, getText:true, checkVersion:true, frontendFunction:"loginCanteenUsingPA"}` → JSON object (response ignored; call required to initialize server-side session)
- `objednavky {cislo, sid:accountSid, s5url, lang:"EN", konto:0, podminka:"", ignoreCert:"false"}` → `{"table0":[...], "table1":[...], ...}`

Table format: each `table{i}` is one day's rows. Find row with `druh=="PO"` (soup, optional) and `druh=="OB"` (main meal). If meal row exists: `date=meal["datum"]` (DD.MM.YYYY), `soup=soup_row["nazev"]` or None, `meal=meal_row["nazev"]`, `ordered = meal_row.get("pocet", 0) > 0`.

`s5url = "https://wss52.strava.cz/WSStravne5_13/WSStravne5.svc"`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_strava.py`:

```python
import json
from datetime import date

import httpx
import pytest
import respx

from config import (
    AppConfig, ICloudConfig, CalendarConfig, WeatherConfig,
    HomeAssistantConfig, DisplayConfig, StravaConfig, StravaPersonConfig,
)
from sources.strava import get_strava_meals


def make_cfg(people: list[StravaPersonConfig]) -> AppConfig:
    return AppConfig(
        icloud=ICloudConfig(share_token="x", photo_interval_seconds=30),
        calendars=[],
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
        home_assistant=HomeAssistantConfig(url="http://ha.local", token="tok", entities=[]),
        display=DisplayConfig(calendar_days_ahead=2, weather_days=5),
        strava=StravaConfig(
            email="test@example.com",
            password="secret",
            canteen_number="1019",
            breaking_time="12:30",
            people=people,
        ),
    )


def _make_orders(today_str: str, tomorrow_str: str, today_ordered: bool, tomorrow_ordered: bool) -> dict:
    """Build a minimal objednavky response with two days."""
    return {
        "table0": [
            {"druh": "PO", "datum": today_str, "nazev": "Beef broth", "pocet": 0},
            {"druh": "OB", "datum": today_str, "nazev": "Chicken schnitzel", "pocet": 1 if today_ordered else 0},
        ],
        "table1": [
            {"druh": "OB", "datum": tomorrow_str, "nazev": "Pork roast", "pocet": 1 if tomorrow_ordered else 0},
        ],
    }


@respx.mock
async def test_happy_path_single_account():
    """One person with one account; meal ordered today, not tomorrow."""
    today = date(2026, 4, 9)
    tomorrow = date(2026, 4, 10)
    today_str = "09.04.2026"
    tomorrow_str = "10.04.2026"

    respx.post("https://app.strava.cz/api/loginPA").mock(
        return_value=httpx.Response(200, json={"SID": "parent-sid"})
    )
    respx.post("https://app.strava.cz/api/canteenLoginPA").mock(
        return_value=httpx.Response(200, text='"alice-account-sid"')
    )
    respx.post("https://app.strava.cz/api/nactiVlastnostiPA").mock(
        return_value=httpx.Response(200, json={"jmeno": "Alice"})
    )
    respx.post("https://app.strava.cz/api/objednavky").mock(
        return_value=httpx.Response(200, json=_make_orders(today_str, tomorrow_str, True, False))
    )

    cfg = make_cfg([StravaPersonConfig(name="Alice", accounts=["alice.test"], color="#4CAF50")])
    result = await get_strava_meals(cfg, _today=today)

    assert result is not None
    assert result.breaking_time == "12:30"

    assert result.today is not None
    assert result.today.date == "2026-04-09"
    assert result.today.soup == "Beef broth"
    assert result.today.meal == "Chicken schnitzel"
    assert len(result.today.people) == 1
    assert result.today.people[0].name == "Alice"
    assert result.today.people[0].ordered is True

    assert result.tomorrow is not None
    assert result.tomorrow.date == "2026-04-10"
    assert result.tomorrow.meal == "Pork roast"
    assert result.tomorrow.soup is None
    assert result.tomorrow.people[0].ordered is False


@respx.mock
async def test_or_aggregation_for_person_with_two_accounts():
    """Person Bob has two accounts; bob1 not ordered, bob2 ordered → Bob is ordered."""
    today = date(2026, 4, 9)
    tomorrow = date(2026, 4, 10)
    today_str = "09.04.2026"
    tomorrow_str = "10.04.2026"

    respx.post("https://app.strava.cz/api/loginPA").mock(
        return_value=httpx.Response(200, json={"SID": "parent-sid"})
    )

    def canteen_login_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sid = "bob1-sid" if body.get("id") == "bob.test1" else "bob2-sid"
        return httpx.Response(200, text=f'"{sid}"')

    respx.post("https://app.strava.cz/api/canteenLoginPA").mock(side_effect=canteen_login_response)
    respx.post("https://app.strava.cz/api/nactiVlastnostiPA").mock(
        return_value=httpx.Response(200, json={})
    )

    def objednavky_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("sid") == "bob1-sid":
            return httpx.Response(200, json=_make_orders(today_str, tomorrow_str, False, False))
        else:  # bob2-sid
            return httpx.Response(200, json=_make_orders(today_str, tomorrow_str, True, True))

    respx.post("https://app.strava.cz/api/objednavky").mock(side_effect=objednavky_response)

    cfg = make_cfg([StravaPersonConfig(name="Bob", accounts=["bob.test1", "bob.test2"], color="#2196F3")])
    result = await get_strava_meals(cfg, _today=today)

    assert result is not None
    assert result.today is not None
    assert result.today.people[0].name == "Bob"
    assert result.today.people[0].ordered is True   # OR: bob2 was ordered


@respx.mock
async def test_one_account_fetch_failure_shows_unknown():
    """If one account's fetch fails, that person's ordered is None (unknown)."""
    today = date(2026, 4, 9)
    tomorrow = date(2026, 4, 10)

    respx.post("https://app.strava.cz/api/loginPA").mock(
        return_value=httpx.Response(200, json={"SID": "parent-sid"})
    )

    def canteen_login_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("id") == "alice.test":
            return httpx.Response(200, text='"alice-sid"')
        return httpx.Response(500)  # bob's canteen login fails

    respx.post("https://app.strava.cz/api/canteenLoginPA").mock(side_effect=canteen_login_response)
    respx.post("https://app.strava.cz/api/nactiVlastnostiPA").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.post("https://app.strava.cz/api/objednavky").mock(
        return_value=httpx.Response(200, json=_make_orders("09.04.2026", "10.04.2026", True, False))
    )

    cfg = make_cfg([
        StravaPersonConfig(name="Alice", accounts=["alice.test"]),
        StravaPersonConfig(name="Bob",   accounts=["bob.test"]),
    ])
    result = await get_strava_meals(cfg, _today=today)

    assert result is not None
    assert result.today is not None
    assert result.today.people[0].name == "Alice"
    assert result.today.people[0].ordered is True
    assert result.today.people[1].name == "Bob"
    assert result.today.people[1].ordered is None   # all of Bob's accounts failed


@respx.mock
async def test_parent_login_failure_raises():
    """If the parent login fails, get_strava_meals raises (triggering backoff in main.py)."""
    respx.post("https://app.strava.cz/api/loginPA").mock(
        return_value=httpx.Response(401)
    )
    cfg = make_cfg([StravaPersonConfig(name="Alice", accounts=["alice.test"])])

    with pytest.raises(Exception):
        await get_strava_meals(cfg)


async def test_returns_none_when_strava_not_configured():
    cfg = make_cfg([])
    cfg.strava = None
    result = await get_strava_meals(cfg)
    assert result is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_strava.py -v
```

Expected: `ModuleNotFoundError: No module named 'sources.strava'`.

- [ ] **Step 3: Implement `sources/strava.py`**

Create `sources/strava.py`:

```python
import asyncio
import json
import logging
from datetime import date, datetime, timedelta

import httpx

from config import AppConfig
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
    """Login to canteen as one sub-account, fetch its order schedule, return {date: (soup, meal, ordered)}."""
    account_sid = await _post(client, "canteenLoginPA", {
        "sid": parent_sid,
        "cislo": cislo,
        "id": account_id,
        "environment": "W",
        "lang": "EN",
    })
    # nactiVlastnostiPA is required to initialize the S5 server session before objednavky
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

    _today is injectable for testing; in production it defaults to date.today().
    Raises on parent login failure (so the refresh loop can backoff).
    Per-account failures are isolated: that account contributes nothing to person ordering.
    """
    if cfg.strava is None or not cfg.strava.people:
        return None

    s = cfg.strava
    today = _today or date.today()
    tomorrow = today + timedelta(days=1)

    # Collect unique account ids across all people (avoid duplicate fetches).
    all_account_ids: list[str] = []
    seen: set[str] = set()
    for person in s.people:
        for aid in person.accounts:
            if aid not in seen:
                all_account_ids.append(aid)
                seen.add(aid)

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Parent login raises on failure → propagates to _refresh_loop for backoff.
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

    def _aggregate_ordered(person, day: date) -> bool | None:
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
```

- [ ] **Step 4: Run strava tests**

```
pytest tests/test_strava.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Run full test suite**

```
pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add sources/strava.py tests/test_strava.py
git commit -m "feat: implement Strava meal source"
```

---

### Task 4: Wire Strava source into `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add import**

Add to `main.py` imports (near line 16):

```python
from sources.strava import get_strava_meals
```

- [ ] **Step 2: Update TTL**

In `_TTLS`, change `"meals": 300` to `"meals": 1800`.

- [ ] **Step 3: Add meals back to `_populate_cache`**

In `_populate_cache`, add `get_strava_meals(config)` to the `asyncio.gather` call and add `meals` back to the destructuring:

```python
        photos, ics_events, ms365_events, mini_cal, forecast, ha, meals, outdoor_temp, garden_temps = await asyncio.gather(
            get_photos(config),
            get_events(config),
            get_ms365_events(config),
            get_mini_cal_events(config),
            get_forecast(config),
            get_entities(config),
            get_strava_meals(config),
            get_outdoor_temp(config),
            get_garden_temps(config),
            return_exceptions=True,
        )
```

Add the meals cache line back after the `ha_entities` cache line:

```python
        if not isinstance(meals, BaseException):
            cache.set("meals", meals, _TTLS["meals"])
```

- [ ] **Step 4: Add refresh loop in `startup`**

Add to the `startup` function (after the `ha_entities` refresh loop):

```python
        asyncio.create_task(_refresh_loop("meals", lambda: get_strava_meals(config), _TTLS["meals"]))
```

- [ ] **Step 5: Run all tests**

```
pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: wire Strava meal source into refresh pipeline (TTL 30min)"
```

---

### Task 5: Update frontend types

**Files:**
- Modify: `src/types.ts`

- [ ] **Step 1: Replace the `Meals` interface**

In `src/types.ts`, replace lines 32-37:

```ts
export interface Meals {
  soup_today: string;
  soup_tomorrow: string;
  lunch_today: string;
  lunch_tomorrow: string;
}
```

with:

```ts
export interface StravaPersonStatus {
  name: string;
  color: string | null;
  ordered: boolean | null;   // null = all of this person's accounts failed to fetch
}

export interface StravaDay {
  date: string;              // "YYYY-MM-DD"
  soup: string | null;
  meal: string | null;
  people: StravaPersonStatus[];
}

export interface StravaMeals {
  today: StravaDay | null;
  tomorrow: StravaDay | null;
  breaking_time: string;     // "HH:MM"
}
```

On line 54 (inside `DashboardData`), change:

```ts
  meals: Meals | null;
```

to:

```ts
  meals: StravaMeals | null;
```

- [ ] **Step 2: Commit**

```bash
git add src/types.ts
git commit -m "feat: update frontend types for StravaMeals"
```

---

### Task 6: Update clock module

**Files:**
- Modify: `src/modules/clock.ts`

- [ ] **Step 1: Replace the meals logic**

Replace the entire contents of `src/modules/clock.ts` with:

```ts
import { StravaMeals, StravaDay, StravaPersonStatus } from '../types';

let _soupEl: HTMLElement | null = null;
let _lunchEl: HTMLElement | null = null;
let _marksEl: HTMLElement | null = null;
let _tempEl: HTMLElement | null = null;
let _meals: StravaMeals | null = null;

function isBeforeBreakingTime(breakingTime: string): boolean {
  const [h, m] = breakingTime.split(':').map(Number);
  const now = new Date();
  return now.getHours() < h || (now.getHours() === h && now.getMinutes() < m);
}

function renderMarks(day: StravaDay | null): void {
  if (!_marksEl) return;
  _marksEl.innerHTML = '';
  if (!day) return;
  for (const p of day.people) {
    const dot = document.createElement('span');
    dot.className = 'meal-mark';
    dot.title = p.name;
    if (p.ordered === true) {
      dot.classList.add('ordered');
      if (p.color) dot.style.background = p.color;
    } else if (p.ordered === false) {
      dot.classList.add('not-ordered');
    } else {
      dot.classList.add('unknown');
    }
    _marksEl.appendChild(dot);
  }
}

function renderMeals(): void {
  if (!_soupEl || !_lunchEl || !_marksEl) return;
  if (!_meals) {
    _soupEl.textContent = '';
    _lunchEl.textContent = '';
    _marksEl.innerHTML = '';
    return;
  }
  const day = isBeforeBreakingTime(_meals.breaking_time) ? _meals.today : _meals.tomorrow;
  _soupEl.textContent  = day?.soup  ?? '';
  _lunchEl.textContent = day?.meal  ?? '';
  renderMarks(day ?? null);
}

export function updateMeals(meals: StravaMeals | null): void {
  _meals = meals;
  renderMeals();
}

export function updateTemperature(temp: number | null): void {
  if (!_tempEl) return;
  _tempEl.textContent = temp !== null ? `${temp}°` : '';
}

export function startClock(container: HTMLElement): void {
  const topRowEl = document.createElement('div');
  topRowEl.id = 'clock-top-row';

  _tempEl = document.createElement('div');
  _tempEl.id = 'clock-temp';

  const timeEl = document.createElement('div');
  timeEl.id = 'clock-time';

  topRowEl.append(_tempEl, timeEl);

  const mealsEl = document.createElement('div');
  mealsEl.id = 'clock-meals';

  _soupEl = document.createElement('div');
  _soupEl.id = 'clock-soup';

  _lunchEl = document.createElement('div');
  _lunchEl.id = 'clock-lunch';

  _marksEl = document.createElement('div');
  _marksEl.id = 'clock-meal-marks';

  mealsEl.append(_soupEl, _lunchEl, _marksEl);
  container.append(topRowEl, mealsEl);

  function tick(): void {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    timeEl.textContent = `${hh}:${mm}`;
    renderMeals();
  }
  tick();
  setInterval(tick, 1000);
}
```

- [ ] **Step 2: Commit**

```bash
git add src/modules/clock.ts
git commit -m "feat: update clock module for per-person meal marks and configurable breaking time"
```

---

### Task 7: Add CSS for meal marks

**Files:**
- Modify: `static/css/clock.css`

- [ ] **Step 1: Append marks styles**

Add to the end of `static/css/clock.css` (after line 40):

```css
#clock-meal-marks {
  display: flex;
  flex-direction: row;
  gap: 0.4rem;
  margin-top: 0.3rem;
  justify-content: flex-end;
}

.meal-mark {
  width: 0.9rem;
  height: 0.9rem;
  border-radius: 50%;
  display: inline-block;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

/* ordered: green fill (overridden per-person with inline style if color set in config) */
.meal-mark.ordered {
  background: #4CAF50;
}

/* not ordered: transparent with red border */
.meal-mark.not-ordered {
  background: transparent;
  border-color: #F44336;
}

/* unknown: all accounts failed to fetch */
.meal-mark.unknown {
  background: #9E9E9E;
  opacity: 0.5;
}
```

Final layout on screen (right-aligned, below the meal text):

```
                  18°   14:32
         Hovezí vývar s nudlemi
 Kuřecí řízek s bramborovou kaší
                      [●][●][○]
```

`[●]` green (optionally tinted per-person) = ordered. `[○]` empty red ring = not ordered. `[●]` grey at 50% opacity = fetch failed for that person.

- [ ] **Step 2: Commit**

```bash
git add static/css/clock.css
git commit -m "feat: add meal-mark dot styles"
```

---

### Task 8: Build frontend and verify compilation

**Files:**
- Read: `package.json` to confirm the build command

- [ ] **Step 1: Build the frontend**

```
cd /Users/pajgrtondrej/Work/GitHub/WMD
npm run build
```

Expected: exits with code 0, no TypeScript errors.

- [ ] **Step 2: Commit the built bundle if it's tracked**

Check if `static/js/app.js` is in the repo (not gitignored):

```bash
git status static/js/app.js
```

If it is tracked: `git add static/js/app.js && git commit -m "build: rebuild frontend with Strava meal support"`.

---

### Task 9: Update `config.json` and `config.example.json`

> **Prerequisites:** Rotate the Strava password before this step.
> The current password is committed in plaintext at `/Users/pajgrtondrej/Work/GitHub/Strava/fetch_orders.js:5`.
> Log in to `app.strava.cz` → Account settings → change the password first.
> Then use the new password in `config.json` below.

**Files:**
- Modify: `config.json`
- Modify: `config.example.json`

- [ ] **Step 1: Update `config.json`**

Remove these four keys from the `homeAssistant` block (they may be under `homeAssistant` in the JSON):

```
"lunchTodayEntityId", "lunchTomorrowEntityId", "soupTodayEntityId", "soupTomorrowEntityId"
```

Add a new top-level `"strava"` block (add after the `"ms365"` block if present):

```json
"strava": {
  "email": "pajgrt.ondrej@gmail.com",
  "password": "<YOUR-NEW-PASSWORD>",
  "canteenNumber": "1019",
  "breakingTime": "12:30",
  "people": [
    {
      "name": "Terka",
      "color": "#E91E63",
      "accounts": ["tereza.pajgrtova"]
    },
    {
      "name": "Ondra",
      "color": "#2196F3",
      "accounts": ["ondrej.pajgrt", "ondrej.pajgrt.2"]
    },
    {
      "name": "Andrea",
      "color": "#F44336",
      "accounts": ["andrea.pajgrt.bartosova"]
    }
  ]
}
```

Note: "Ondra" has two accounts with OR aggregation — if either is ordered, Ondra's dot is green.

- [ ] **Step 2: Update `config.example.json`**

Add a `"strava"` stub (after the `"homeAssistant"` block):

```json
"strava": {
  "email": "",
  "password": "",
  "canteenNumber": "1019",
  "breakingTime": "12:30",
  "people": [
    {"name": "Child", "color": "#4CAF50", "accounts": ["child.strava.login"]}
  ]
}
```

- [ ] **Step 3: Verify config loads cleanly**

```bash
cd /Users/pajgrtondrej/Work/GitHub/WMD
source .venv/bin/activate
python -c "from config import load_config; c = load_config(); print(c.strava.people)"
```

Expected: list of `StravaPersonConfig` objects printed without errors.

- [ ] **Step 4: Smoke-test the full source**

```bash
python -c "
import asyncio
from config import load_config
from sources.strava import get_strava_meals
result = asyncio.run(get_strava_meals(load_config()))
print(result)
"
```

Expected: `StravaMeals(today=StravaDay(...), tomorrow=StravaDay(...), breaking_time='12:30')` with `people` showing `ordered=True/False` for each person.

- [ ] **Step 5: Commit `config.example.json` only** (never commit `config.json`)

```bash
git add config.example.json
git commit -m "docs: add strava stub to config.example.json"
```

---

### Task 10: End-to-end deploy

- [ ] **Step 1: Run full local server + verify `/api/data` shape**

```bash
cd /Users/pajgrtondrej/Work/GitHub/WMD
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 3000 &
sleep 4
curl -s http://127.0.0.1:3000/api/data | python -m json.tool | python -c "
import sys, json
data = json.load(sys.stdin)
meals = data.get('meals')
if meals is None:
    print('WARNING: meals is null (strava may not be configured or fetch failed)')
else:
    print('breaking_time:', meals['breaking_time'])
    today = meals.get('today')
    if today:
        print('today meal:', today['meal'])
        print('people:', [(p['name'], p['ordered']) for p in today['people']])
    else:
        print('today: null (no school today)')
"
kill %1
```

Expected: `breaking_time: 12:30`, meal text, and a list of `(name, True/False)` tuples for each person.

- [ ] **Step 2: Deploy to device**

```bash
./update.sh app
```

- [ ] **Step 3: Check service logs on device**

```bash
ssh rem@192.168.10.66 'sudo journalctl -u wmd-server -n 50 --no-pager'
```

Expected: startup lines, then background refresh logs with `Strava` source completing without errors.

- [ ] **Step 4: Visual check on the display**

Open a browser to `http://192.168.10.66:3000`. Verify:
- Meal text appears as before.
- Colored dots appear below the meal text, one per configured person.
- Dots are green (ordered) or empty red rings (not ordered) or grey (if fetch failed).
- After 12:30 the display switches to tomorrow's meal + tomorrow's dots.

---

## Checklist against spec

| Requirement | Covered in |
|---|---|
| Fetch meal data from app.strava.cz directly | Task 3 (`sources/strava.py`) |
| Show whether meal is ordered or not | Task 3 (`ordered` field), Task 6+7 (dots) |
| People-based config (name + multiple accounts) | Task 1 (`StravaPersonConfig`) |
| OR aggregation across person's accounts | Task 3 (`_aggregate_ordered`) |
| Configurable breaking time | Task 1 (`breaking_time`), Task 6 (`isBeforeBreakingTime`) |
| Replace HA meal source | Task 2 |
| Colored marks per person | Task 6 (render), Task 7 (CSS) |
| Single service, single deploy | Task 4 (wired into existing refresh pipeline) |
| Credentials in gitignored config.json | Task 9 |
