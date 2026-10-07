import pytest
import respx
import httpx

from config import AppConfig, ICloudConfig, CalendarConfig, WeatherConfig, HomeAssistantConfig, HaEntityConfig, DisplayConfig
from sources.homeassistant import CarStatusUnavailable, get_car_status, get_entities


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


HA = "http://homeassistant.local:8123/api/states"


def make_car_cfg(battery: str = "sensor.car_battery", range_: str = "sensor.car_range") -> AppConfig:
    cfg = make_cfg([])
    cfg.home_assistant.car_battery_entity_id = battery
    cfg.home_assistant.car_range_entity_id = range_
    return cfg


@respx.mock
async def test_car_status_reads_battery_and_range():
    respx.get(f"{HA}/sensor.car_battery").mock(return_value=httpx.Response(200, json={"state": "52", "attributes": {"unit_of_measurement": "%"}}))
    respx.get(f"{HA}/sensor.car_range").mock(return_value=httpx.Response(200, json={"state": "290.29347072", "attributes": {"unit_of_measurement": "km"}}))

    result = await get_car_status(make_car_cfg())

    assert result is not None
    assert result.battery_percent == 52.0
    assert result.range_km == 290.29347072


async def test_car_status_is_none_when_battery_not_configured():
    result = await get_car_status(make_car_cfg(battery="", range_=""))

    assert result is None


@respx.mock
async def test_car_status_raises_when_battery_unavailable_so_cache_keeps_last_value():
    respx.get(f"{HA}/sensor.car_battery").mock(return_value=httpx.Response(200, json={"state": "unavailable", "attributes": {}}))
    respx.get(f"{HA}/sensor.car_range").mock(return_value=httpx.Response(200, json={"state": "290", "attributes": {}}))

    with pytest.raises(CarStatusUnavailable):
        await get_car_status(make_car_cfg())


@respx.mock
async def test_car_status_treats_non_finite_states_as_unknown():
    respx.get(f"{HA}/sensor.car_battery").mock(return_value=httpx.Response(200, json={"state": "75", "attributes": {}}))
    respx.get(f"{HA}/sensor.car_range").mock(return_value=httpx.Response(200, json={"state": "nan", "attributes": {}}))

    result = await get_car_status(make_car_cfg())

    assert result is not None
    assert result.range_km is None


@respx.mock
async def test_car_status_keeps_battery_when_range_unavailable():
    respx.get(f"{HA}/sensor.car_battery").mock(return_value=httpx.Response(200, json={"state": "80", "attributes": {}}))
    respx.get(f"{HA}/sensor.car_range").mock(return_value=httpx.Response(500))

    result = await get_car_status(make_car_cfg())

    assert result is not None
    assert result.battery_percent == 80.0
    assert result.range_km is None


async def test_car_status_skips_range_when_not_configured():
    with respx.mock:
        respx.get(f"{HA}/sensor.car_battery").mock(return_value=httpx.Response(200, json={"state": "40", "attributes": {}}))

        result = await get_car_status(make_car_cfg(range_=""))

    assert result is not None
    assert result.range_km is None
