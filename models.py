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


class Meals(BaseModel):
    soup_today: str
    soup_tomorrow: str
    lunch_today: str
    lunch_tomorrow: str


class DashboardData(BaseModel):
    photos: list[Photo]
    events: list[CalendarEvent]
    mini_cal_events: list[CalendarEvent]
    weather: list[WeatherDay]
    ha_entities: list[HaEntity]
    meals: Meals | None
    outdoor_temp: float | None
    photo_interval_seconds: int
    server_time: datetime
