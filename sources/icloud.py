import httpx

from config import AppConfig
from models import Photo

_photo_url_map: dict[str, str] = {}

_BASE_URL = "https://p00-sharedstreams.icloud.com/{token}/sharedstreams"


async def get_photos(cfg: AppConfig) -> list[Photo]:
    token = cfg.icloud.share_token
    base_url = _BASE_URL.format(token=token)

    async with httpx.AsyncClient() as client:
        # Step 1: get stream
        resp = await client.post(
            f"{base_url}/webstream",
            json={"streamCtag": None},
            headers={"Content-Type": "application/json"},
        )

        # Handle redirect host
        if "X-Apple-MMe-Host" in resp.headers:
            new_host = resp.headers["X-Apple-MMe-Host"]
            base_url = f"https://{new_host}/{token}/sharedstreams"
            resp = await client.post(
                f"{base_url}/webstream",
                json={"streamCtag": None},
                headers={"Content-Type": "application/json"},
            )

        stream_data = resp.json()
        items = stream_data.get("photos", [])
        if not items:
            return []

        guids = [p["photoGuid"] for p in items]

        # Step 2: get download URLs
        asset_resp = await client.post(
            f"{base_url}/webasseturls",
            json={"photoGuids": guids},
            headers={"Content-Type": "application/json"},
        )
        asset_data = asset_resp.json()
        items_map = asset_data.get("items", {})

    photos: list[Photo] = []
    _photo_url_map.clear()

    for guid in guids:
        if guid not in items_map:
            continue
        item = items_map[guid]
        # Build real URL from url_location + url_path
        url_location = item.get("url_location", "")
        url_path = item.get("url_path", "")
        real_url = f"https://{url_location}{url_path}" if url_location and url_path else ""
        if not real_url:
            continue
        _photo_url_map[guid] = real_url
        photos.append(Photo(id=guid, url=f"/api/photo/{guid}"))

    return photos


def get_photo_url(photo_id: str) -> str | None:
    return _photo_url_map.get(photo_id)
