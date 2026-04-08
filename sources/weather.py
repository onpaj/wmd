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
        async with httpx.AsyncClient(timeout=30.0) as client:
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



_METNO_SYMBOL_ICON: dict[str, str] = {
    "clearsky": "sunny",
    "fair": "sunny",
    "partlycloudy": "partly-cloudy",
    "cloudy": "cloudy",
    "fog": "fog",
    "lightrain": "rainy",
    "rain": "rainy",
    "heavyrain": "heavy-rain",
    "lightsleet": "rainy",
    "sleet": "rainy",
    "heavysleet": "heavy-rain",
    "lightsnow": "snow",
    "snow": "snow",
    "heavysnow": "snow",
    "snowshowers": "snow",
    "lightsnowshowers": "snow",
    "rainshowers": "rainy",
    "heavyrainshowers": "heavy-rain",
    "sleetshowers": "rainy",
    "thunder": "storm",
    "rainandthunder": "storm",
    "heavyrainandthunder": "storm",
    "snowandthunder": "storm",
    "sleetandthunder": "storm",
}


class METNorwayProvider(WeatherProvider):
    _BASE = "https://api.met.no/weatherapi/locationforecast/2.0/compact"

    def _symbol_to_icon(self, symbol_code: str) -> str:
        base = symbol_code.split("_")[0]
        return _METNO_SYMBOL_ICON.get(base, "cloudy")

    async def get_forecast(self, cfg: AppConfig) -> list[WeatherDay]:
        from collections import defaultdict

        headers = {"User-Agent": "WMD-Dashboard/1.0 self-hosted-wall-dashboard"}
        params = {"lat": cfg.weather.latitude, "lon": cfg.weather.longitude}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(self._BASE, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        by_date: dict[str, list] = defaultdict(list)
        for entry in data["properties"]["timeseries"]:
            by_date[entry["time"][:10]].append(entry)

        days: list[WeatherDay] = []
        for date_str in sorted(by_date.keys())[: cfg.display.weather_days]:
            entries = by_date[date_str]

            temps = [
                e["data"]["instant"]["details"]["air_temperature"]
                for e in entries
                if "air_temperature" in e["data"]["instant"]["details"]
            ]
            temp_high = max(temps) if temps else 0.0
            temp_low = min(temps) if temps else 0.0

            icon = "cloudy"
            for e in entries:
                if "next_12_hours" in e["data"]:
                    icon = self._symbol_to_icon(e["data"]["next_12_hours"]["summary"]["symbol_code"])
                    break

            precip_entries = [
                e["data"]["next_1_hours"]["details"].get("precipitation_amount", 0)
                for e in entries
                if "next_1_hours" in e["data"]
            ]
            if precip_entries:
                wet = sum(1 for p in precip_entries if p > 0)
                precip_percent = int(wet / len(precip_entries) * 100)
            else:
                precip_percent = 0

            days.append(WeatherDay(
                date=date_str,
                icon=icon,
                temp_high=temp_high,
                temp_low=temp_low,
                precip_percent=precip_percent,
            ))

        return days


async def get_forecast(cfg: AppConfig) -> list[WeatherDay]:
    if cfg.weather.provider == "metno":
        return await METNorwayProvider().get_forecast(cfg)
    return await OpenMeteoProvider().get_forecast(cfg)
