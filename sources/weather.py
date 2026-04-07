from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from config import AppConfig

ICON_KEYS: dict[int, str] = {
    0: "sunny",
    1: "sunny",
    2: "partly-cloudy",
    3: "cloudy",
    45: "fog",
    48: "fog",
    51: "rainy",
    53: "rainy",
    55: "rainy",
    56: "rainy",
    57: "rainy",
    61: "rainy",
    63: "rainy",
    64: "rainy",
    65: "heavy-rain",
    66: "rainy",
    67: "heavy-rain",
    71: "snow",
    73: "snow",
    75: "snow",
    77: "snow",
    80: "rainy",
    81: "rainy",
    82: "heavy-rain",
    85: "snow",
    86: "snow",
    95: "storm",
    96: "storm",
    99: "storm",
}

_AW_ICON_KEYS: dict[int, str] = {
    1: "sunny",
    2: "sunny",
    3: "partly-cloudy",
    4: "partly-cloudy",
    5: "partly-cloudy",
    6: "partly-cloudy",
    7: "cloudy",
    8: "cloudy",
    11: "fog",
    12: "rainy",
    13: "rainy",
    14: "rainy",
    15: "storm",
    16: "storm",
    17: "storm",
    18: "rainy",
    19: "snow",
    20: "snow",
    21: "snow",
    22: "snow",
    23: "snow",
    24: "snow",
    25: "rainy",
    26: "rainy",
    29: "rainy",
    30: "sunny",
    31: "sunny",
    32: "sunny",
    33: "partly-cloudy",
    34: "partly-cloudy",
    35: "partly-cloudy",
    36: "cloudy",
    37: "cloudy",
    38: "cloudy",
    39: "rainy",
    40: "rainy",
    41: "storm",
    42: "storm",
    43: "snow",
    44: "snow",
}


@dataclass
class WeatherDay:
    date: str
    icon: str
    temp_high: float
    temp_low: float
    precip_percent: int


class WeatherProvider(ABC):
    @abstractmethod
    async def get_forecast(self, cfg: AppConfig) -> list[WeatherDay]:
        ...


class OpenMeteoProvider(WeatherProvider):
    async def get_forecast(self, cfg: AppConfig) -> list[WeatherDay]:
        params = {
            "latitude": cfg.weather.latitude,
            "longitude": cfg.weather.longitude,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": cfg.display.weather_days,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data["daily"]
        days: list[WeatherDay] = []
        for i, date_str in enumerate(daily["time"]):
            wmo = daily["weathercode"][i]
            days.append(
                WeatherDay(
                    date=date_str,
                    icon=ICON_KEYS.get(wmo, "cloudy"),
                    temp_high=daily["temperature_2m_max"][i],
                    temp_low=daily["temperature_2m_min"][i],
                    precip_percent=daily["precipitation_probability_max"][i],
                )
            )
        return days


class AccuWeatherProvider(WeatherProvider):
    _BASE = "http://dataservice.accuweather.com"

    async def get_forecast(self, cfg: AppConfig) -> list[WeatherDay]:
        api_key = cfg.weather.accuweather_api_key
        async with httpx.AsyncClient() as client:
            # Step 1: geoposition search for location key
            geo_resp = await client.get(
                f"{self._BASE}/locations/v1/cities/geoposition/search",
                params={
                    "apikey": api_key,
                    "q": f"{cfg.weather.latitude},{cfg.weather.longitude}",
                },
            )
            geo_resp.raise_for_status()
            location_key = geo_resp.json()["Key"]

            # Step 2: 5-day daily forecast
            forecast_resp = await client.get(
                f"{self._BASE}/forecasts/v1/daily/5day/{location_key}",
                params={"apikey": api_key, "metric": "true"},
            )
            forecast_resp.raise_for_status()
            forecast_data = forecast_resp.json()

        days: list[WeatherDay] = []
        for day in forecast_data["DailyForecasts"]:
            date_str = day["Date"][:10]
            aw_icon = day["Day"]["Icon"]
            temp_high = day["Temperature"]["Maximum"]["Value"]
            temp_low = day["Temperature"]["Minimum"]["Value"]
            precip = day["Day"].get("PrecipitationProbability", 0)
            days.append(
                WeatherDay(
                    date=date_str,
                    icon=_AW_ICON_KEYS.get(aw_icon, "cloudy"),
                    temp_high=temp_high,
                    temp_low=temp_low,
                    precip_percent=precip,
                )
            )
        return days


async def get_forecast(cfg: AppConfig) -> list[WeatherDay]:
    if cfg.weather.provider == "accuweather":
        return await AccuWeatherProvider().get_forecast(cfg)
    return await OpenMeteoProvider().get_forecast(cfg)
