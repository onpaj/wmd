import pytest
import respx
import httpx

from config import AppConfig, ICloudConfig, CalendarConfig, WeatherConfig, HomeAssistantConfig, DisplayConfig
from sources.icloud import get_photos


def make_config(token: str = "testtoken") -> AppConfig:
    return AppConfig(
        icloud=ICloudConfig(share_token=token, photo_interval_seconds=30),
        calendars=[],
        weather=WeatherConfig(provider="openmeteo", latitude=50.0, longitude=14.0),
        home_assistant=HomeAssistantConfig(url="http://ha.local", token="", entities=[]),
        display=DisplayConfig(calendar_days_ahead=2, weather_days=5),
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_photos_returns_photo_list():
    token = "testtoken"
    base = f"https://p01-sharedstreams.icloud.com/{token}/sharedstreams"

    respx.post(f"{base}/webstream").mock(
        return_value=httpx.Response(
            200,
            json={
                "photos": [
                    {"photoGuid": "guid1", "dateCreated": "2021-06-12T18:13:54Z", "derivatives": {"2000": {"checksum": "chk1"}, "400": {"checksum": "chk1s"}}},
                    {"photoGuid": "guid2", "derivatives": {"1500": {"checksum": "chk2"}}},
                ]
            },
        )
    )
    respx.post(f"{base}/webasseturls").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": {
                    "chk1": {"url_location": "photos.icloud.com", "url_path": "/photo1.jpg"},
                    "chk1s": {"url_location": "photos.icloud.com", "url_path": "/photo1s.jpg"},
                    "chk2": {"url_location": "photos.icloud.com", "url_path": "/photo2.jpg"},
                }
            },
        )
    )

    cfg = make_config(token)
    photos = await get_photos(cfg)

    assert len(photos) == 2
    assert photos[0].id == "guid1"
    assert photos[0].url == "/api/photo/guid1"
    assert photos[0].date == "2021-06-12T18:13:54Z"
    assert photos[1].id == "guid2"
    assert photos[1].url == "/api/photo/guid2"
    assert photos[1].date is None


@respx.mock
@pytest.mark.asyncio
async def test_get_photos_falls_back_to_batch_date():
    token = "testtoken"
    base = f"https://p01-sharedstreams.icloud.com/{token}/sharedstreams"

    respx.post(f"{base}/webstream").mock(
        return_value=httpx.Response(
            200,
            json={
                "photos": [
                    {"photoGuid": "guid1", "batchDateCreated": "2020-01-02T09:00:00Z", "derivatives": {"2000": {"checksum": "chk1"}}},
                ]
            },
        )
    )
    respx.post(f"{base}/webasseturls").mock(
        return_value=httpx.Response(
            200,
            json={"items": {"chk1": {"url_location": "photos.icloud.com", "url_path": "/photo1.jpg"}}},
        )
    )

    cfg = make_config(token)
    photos = await get_photos(cfg)

    assert len(photos) == 1
    assert photos[0].date == "2020-01-02T09:00:00Z"


@respx.mock
@pytest.mark.asyncio
async def test_get_photos_handles_empty_album():
    token = "testtoken"
    base = f"https://p01-sharedstreams.icloud.com/{token}/sharedstreams"

    respx.post(f"{base}/webstream").mock(
        return_value=httpx.Response(200, json={"photos": []})
    )

    cfg = make_config(token)
    photos = await get_photos(cfg)

    assert photos == []
