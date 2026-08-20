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
    show_as_busy: bool = False


@dataclass
class WeatherConfig:
    provider: str
    latitude: float
    longitude: float


@dataclass
class HaEntityConfig:
    entity_id: str
    label: str


@dataclass
class HomeAssistantConfig:
    url: str
    token: str
    entities: list[HaEntityConfig]
    outside_temperature_entity_id: str = ""
    glasshouse_entity_id: str = ""
    coop_entity_id: str = ""
    brooder_entity_id: str = ""
    glasshouse_humidity_entity_id: str = ""
    coop_humidity_entity_id: str = ""
    brooder_humidity_entity_id: str = ""


@dataclass
class MiniCalendarConfig:
    url: str
    color: str


@dataclass
class SleepHoursConfig:
    start: str  # "HH:MM"
    end: str    # "HH:MM"


@dataclass
class DisplayConfig:
    calendar_days_ahead: int
    weather_days: int
    sleep_hours: Optional[SleepHoursConfig] = None


@dataclass
class Ms365UserConfig:
    email: str
    name: str
    color: str


@dataclass
class Ms365CalendarConfig:
    """A named calendar inside a mailbox (e.g. a shared or external work calendar).

    Unlike ``Ms365UserConfig`` — which reads the mailbox's default calendar —
    this targets one calendar by its display name. ``show_as_busy`` replaces
    event titles with a neutral label so work items appear on a wall display
    without leaking their subjects.
    """

    email: str
    calendar_name: str
    name: str
    color: str
    exclude_patterns: list[str] = field(default_factory=list)
    show_as_busy: bool = False


@dataclass
class Ms365Config:
    tenant_id: str
    client_id: str
    client_secret: str
    users: list[Ms365UserConfig]
    calendars: list[Ms365CalendarConfig] = field(default_factory=list)


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
    s5_url: Optional[str] = None
    people: list[StravaPersonConfig] = field(default_factory=list)


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
            show_as_busy=c.get("showAsBusy", False),
        )
        for c in data.get("calendars", [])
    ]

    weather_data = data["weather"]
    weather = WeatherConfig(
        provider=weather_data["provider"],
        latitude=weather_data["latitude"],
        longitude=weather_data["longitude"],
    )

    ha_data = data["homeAssistant"]
    home_assistant = HomeAssistantConfig(
        url=ha_data["url"],
        token=ha_data["token"],
        entities=[HaEntityConfig(entity_id=e["id"], label=e.get("label", "")) for e in ha_data.get("entities", [])],
        outside_temperature_entity_id=ha_data.get("outsideTemperature", ""),
        glasshouse_entity_id=ha_data.get("glasshouseEntityId", ""),
        coop_entity_id=ha_data.get("coopEntityId", ""),
        brooder_entity_id=ha_data.get("brooderEntityId", ""),
        glasshouse_humidity_entity_id=ha_data.get("glasshouseHumidityEntityId", ""),
        coop_humidity_entity_id=ha_data.get("coopHumidityEntityId", ""),
        brooder_humidity_entity_id=ha_data.get("brooderHumidityEntityId", ""),
    )

    display_data = data["display"]
    sleep_hours = None
    if "sleepHours" in display_data:
        sh = display_data["sleepHours"]
        sleep_hours = SleepHoursConfig(start=sh["start"], end=sh["end"])
    display = DisplayConfig(
        calendar_days_ahead=display_data["calendarDaysAhead"],
        weather_days=display_data["weatherDays"],
        sleep_hours=sleep_hours,
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
            calendars=[
                Ms365CalendarConfig(
                    email=c["email"],
                    calendar_name=c["calendarName"],
                    name=c["name"],
                    color=c["color"],
                    exclude_patterns=c.get("excludePatterns", []),
                    show_as_busy=c.get("showAsBusy", False),
                )
                for c in m.get("calendars", [])
            ],
        )

    strava = None
    if "strava" in data:
        s = data["strava"]
        strava = StravaConfig(
            email=s["email"],
            password=s["password"],
            canteen_number=s.get("canteenNumber", "1019"),
            breaking_time=s.get("breakingTime", "12:30"),
            s5_url=s.get("s5Url"),
            people=[
                StravaPersonConfig(
                    name=p["name"],
                    accounts=list(p["accounts"]),
                    color=p.get("color"),
                )
                for p in s.get("people", [])
            ],
        )

    return AppConfig(
        icloud=icloud,
        calendars=calendars,
        weather=weather,
        home_assistant=home_assistant,
        display=display,
        mini_calendar=mini_calendar,
        ms365=ms365,
        strava=strava,
    )
