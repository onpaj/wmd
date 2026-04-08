import pytest
import respx
import httpx

from config import AppConfig, ICloudConfig, CalendarConfig, WeatherConfig, HomeAssistantConfig, HaEntityConfig, DisplayConfig
from sources.homeassistant import get_entities


def make_cfg(entities: list[HaEntityConfig]) -> AppConfig:
    return AppConfig(
        icloud=ICloudConfig(share_token="x", photo_interval_seconds=30),
        calendars=[],
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
        home_assistant=HomeAssistantConfig(
            url="http://homeassistant.local:8123",
            token="test-token",
            entities=entities,
        ),
        display=DisplayConfig(calendar_days_ahead=2, weather_days=5),
    )


@respx.mock
async def test_fetches_entity_state():
    cfg = make_cfg([HaEntityConfig(entity_id="sensor.living_room_temp", label="Obývák")])
    respx.get("http://homeassistant.local:8123/api/states/sensor.living_room_temp").mock(
        return_value=httpx.Response(200, json={
            "state": "22.5",
            "attributes": {"unit_of_measurement": "°C"},
        })
    )
    result = await get_entities(cfg)
    assert len(result) == 1
    assert result[0].state == "22.5"
    assert result[0].unit == "°C"
    assert result[0].label == "Obývák"


async def test_returns_empty_when_no_entities_configured():
    cfg = make_cfg([])
    result = await get_entities(cfg)
    assert result == []


@respx.mock
async def test_skips_unreachable_entity():
    cfg = make_cfg([HaEntityConfig(entity_id="sensor.missing", label="Missing")])
    respx.get("http://homeassistant.local:8123/api/states/sensor.missing").mock(
        return_value=httpx.Response(404)
    )
    result = await get_entities(cfg)
    assert result == []
