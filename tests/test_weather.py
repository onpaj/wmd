import pytest
import respx
import httpx

from config import AppConfig, WeatherConfig, DisplayConfig, ICloudConfig, CalendarConfig, HomeAssistantConfig
from sources.weather import get_forecast, ICON_KEYS


def _make_cfg(provider: str = "openmeteo", weather_days: int = 5) -> AppConfig:
    return AppConfig(
        icloud=ICloudConfig(share_token="tok", photo_interval_seconds=30),
        calendars=[],
        weather=WeatherConfig(
            provider=provider,
            latitude=50.07,
            longitude=14.43,
            accuweather_api_key="",
        ),
        home_assistant=HomeAssistantConfig(url="http://ha", token="t", entities=[]),
        display=DisplayConfig(calendar_days_ahead=2, weather_days=weather_days),
    )


_OPEN_METEO_RESPONSE = {
    "daily": {
        "time": ["2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11"],
        "weathercode": [0, 61, 71, 95, 45],
        "temperature_2m_max": [15.0, 12.5, 8.0, 10.0, 14.0],
        "temperature_2m_min": [5.0, 4.5, 1.0, 2.0, 6.0],
        "precipitation_probability_max": [0, 70, 90, 80, 10],
    }
}


@pytest.mark.asyncio
@respx.mock
async def test_openmeteo_returns_5_days():
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=_OPEN_METEO_RESPONSE)
    )
    days = await get_forecast(_make_cfg())
    assert len(days) == 5


@pytest.mark.asyncio
@respx.mock
async def test_openmeteo_normalizes_icons():
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=_OPEN_METEO_RESPONSE)
    )
    days = await get_forecast(_make_cfg())
    # weathercodes: 0=sunny, 61=rainy, 71=snow, 95=storm, 45=fog
    assert days[0].icon == "sunny"
    assert days[1].icon == "rainy"
    assert days[2].icon == "snow"
    assert days[3].icon == "storm"
    assert days[4].icon == "fog"


@pytest.mark.asyncio
@respx.mock
async def test_openmeteo_temps_and_precip():
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(200, json=_OPEN_METEO_RESPONSE)
    )
    days = await get_forecast(_make_cfg())
    day = days[0]
    assert day.date == "2026-04-07"
    assert day.temp_high == 15.0
    assert day.temp_low == 5.0
    assert day.precip_percent == 0

    day2 = days[1]
    assert day2.temp_high == 12.5
    assert day2.temp_low == 4.5
    assert day2.precip_percent == 70


def test_all_icon_keys_are_valid():
    valid = {"sunny", "partly-cloudy", "cloudy", "rainy", "heavy-rain", "snow", "storm", "fog"}
    for wmo, icon in ICON_KEYS.items():
        assert icon in valid, f"WMO {wmo} maps to invalid icon '{icon}'"
