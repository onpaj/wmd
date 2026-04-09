import json
from datetime import date

import httpx
import pytest
import respx

from config import (
    AppConfig, ICloudConfig, WeatherConfig,
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
    """Person Bob has two accounts; bob1 not ordered, bob2 ordered → Bob is ordered (OR logic)."""
    today = date(2026, 4, 9)
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
    """If one account's canteen login fails, that person's ordered is None (unknown)."""
    today = date(2026, 4, 9)

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
