import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ICloudConfig:
    share_token: str
    photo_interval_seconds: int


@dataclass
class CalendarConfig:
    name: str
    url: str
    color: str
    exclude_patterns: list[str] = field(default_factory=list)


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
    lunch_today_entity_id: str = ""
    lunch_tomorrow_entity_id: str = ""
    soup_today_entity_id: str = ""
    soup_tomorrow_entity_id: str = ""
    outside_temperature_entity_id: str = ""


@dataclass
class MiniCalendarConfig:
    url: str
    color: str


@dataclass
class DisplayConfig:
    calendar_days_ahead: int
    weather_days: int


@dataclass
class Ms365UserConfig:
    email: str
    name: str
    color: str


@dataclass
class Ms365Config:
    tenant_id: str
    client_id: str
    client_secret: str
    users: list[Ms365UserConfig]


@dataclass
class AppConfig:
    icloud: ICloudConfig
    calendars: list[CalendarConfig]
    weather: WeatherConfig
    home_assistant: HomeAssistantConfig
    display: DisplayConfig
    mini_calendar: MiniCalendarConfig = field(default_factory=lambda: MiniCalendarConfig(url="", color="#FFC107"))
    ms365: Optional[Ms365Config] = None


def load_config(path: str = "config.json") -> AppConfig:
    with open(path) as f:
        data = json.load(f)

    icloud_data = data["icloud"]
    icloud = ICloudConfig(
        share_token=icloud_data["shareToken"],
        photo_interval_seconds=icloud_data["photoIntervalSeconds"],
    )

    calendars = [
        CalendarConfig(
            name=c["name"],
            url=c["url"],
            color=c["color"],
            exclude_patterns=c.get("excludePatterns", []),
        )
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
        entities=[HaEntityConfig(entity_id=e["id"], label=e.get("label", "")) for e in ha_data.get("entities", [])],
        lunch_today_entity_id=ha_data.get("lunchTodayEntityId", ""),
        lunch_tomorrow_entity_id=ha_data.get("lunchTomorrowEntityId", ""),
        soup_today_entity_id=ha_data.get("soupTodayEntityId", ""),
        soup_tomorrow_entity_id=ha_data.get("soupTomorrowEntityId", ""),
        outside_temperature_entity_id=ha_data.get("outsideTemperature", ""),
    )

    display_data = data["display"]
    display = DisplayConfig(
        calendar_days_ahead=display_data["calendarDaysAhead"],
        weather_days=display_data["weatherDays"],
    )

    mini_cal_data = data.get("miniCalendar", {})
    mini_calendar = MiniCalendarConfig(
        url=mini_cal_data.get("url", ""),
        color=mini_cal_data.get("color", "#FFC107"),
    )

    ms365 = None
    if "ms365" in data:
        m = data["ms365"]
        ms365 = Ms365Config(
            tenant_id=m["tenantId"],
            client_id=m["clientId"],
            client_secret=m["clientSecret"],
            users=[Ms365UserConfig(email=u["email"], name=u["name"], color=u["color"]) for u in m.get("users", [])],
        )

    return AppConfig(
        icloud=icloud,
        calendars=calendars,
        weather=weather,
        home_assistant=home_assistant,
        display=display,
        mini_calendar=mini_calendar,
        ms365=ms365,
    )
