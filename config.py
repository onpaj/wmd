import json
from dataclasses import dataclass, field


@dataclass
class ICloudConfig:
    share_token: str
    photo_interval_seconds: int


@dataclass
class CalendarConfig:
    name: str
    url: str
    color: str


@dataclass
class WeatherConfig:
    provider: str
    latitude: float
    longitude: float
    accuweather_api_key: str


@dataclass
class HaEntityConfig:
    entity_id: str
    label: str


@dataclass
class HomeAssistantConfig:
    url: str
    token: str
    entities: list[HaEntityConfig]


@dataclass
class DisplayConfig:
    calendar_days_ahead: int
    weather_days: int


@dataclass
class AppConfig:
    icloud: ICloudConfig
    calendars: list[CalendarConfig]
    weather: WeatherConfig
    home_assistant: HomeAssistantConfig
    display: DisplayConfig


def load_config(path: str = "config.json") -> AppConfig:
    with open(path) as f:
        data = json.load(f)

    icloud_data = data["icloud"]
    icloud = ICloudConfig(
        share_token=icloud_data["shareToken"],
        photo_interval_seconds=icloud_data["photoIntervalSeconds"],
    )

    calendars = [
        CalendarConfig(name=c["name"], url=c["url"], color=c["color"])
        for c in data.get("calendars", [])
    ]

    weather_data = data["weather"]
    weather = WeatherConfig(
        provider=weather_data["provider"],
        latitude=weather_data["latitude"],
        longitude=weather_data["longitude"],
        accuweather_api_key=weather_data.get("accuweatherApiKey", ""),
    )

    ha_data = data["homeAssistant"]
    home_assistant = HomeAssistantConfig(
        url=ha_data["url"],
        token=ha_data["token"],
        entities=[HaEntityConfig(entity_id=e["entityId"], label=e.get("label", "")) for e in ha_data.get("entities", [])],
    )

    display_data = data["display"]
    display = DisplayConfig(
        calendar_days_ahead=display_data["calendarDaysAhead"],
        weather_days=display_data["weatherDays"],
    )

    return AppConfig(
        icloud=icloud,
        calendars=calendars,
        weather=weather,
        home_assistant=home_assistant,
        display=display,
    )
