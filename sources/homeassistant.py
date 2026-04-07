import asyncio

import httpx

from config import AppConfig
from models import HaEntity


async def _fetch_entity(client: httpx.AsyncClient, ha_url: str, token: str, entity_id: str, label: str) -> HaEntity | None:
    try:
        resp = await client.get(
            f"{ha_url}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        unit = data.get("attributes", {}).get("unit_of_measurement", "") or ""
        return HaEntity(id=entity_id, label=label, state=data["state"], unit=unit)
    except Exception:
        return None


async def get_entities(cfg: AppConfig) -> list[HaEntity]:
    if not cfg.home_assistant.entities:
        return []

    ha_url = cfg.home_assistant.url.rstrip("/")
    token = cfg.home_assistant.token

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[
                _fetch_entity(client, ha_url, token, e.entity_id, e.label)
                for e in cfg.home_assistant.entities
            ]
        )

    return [r for r in results if r is not None]
