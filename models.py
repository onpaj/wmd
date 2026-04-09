from datetime import datetime

from pydantic import BaseModel


class Photo(BaseModel):
    id: str
    url: str


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    calendar_name: str
    color: str
    location: str | None = None


class WeatherDay(BaseModel):
    date: str
    icon: str
    temp_high: float
    temp_low: float
    precip_percent: int


class HaEntity(BaseModel):
    id: str
    label: str
    state: str
    unit: str


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


class GardenTemps(BaseModel):
    glasshouse: float | None = None
    coop: float | None = None
    brooder: float | None = None
    glasshouse_humidity: float | None = None
    coop_humidity: float | None = None
    brooder_humidity: float | None = None


class DashboardData(BaseModel):
    photos: list[Photo]
    events: list[CalendarEvent]
    mini_cal_events: list[CalendarEvent]
    weather: list[WeatherDay]
    ha_entities: list[HaEntity]
    meals: StravaMeals | None
    outdoor_temp: float | None
    garden_temps: GardenTemps | None = None
    photo_interval_seconds: int
    server_time: datetime
