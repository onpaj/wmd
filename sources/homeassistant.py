import asyncio

import httpx

from config import AppConfig
from models import GardenTemps, HaEntity


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


async def get_outdoor_temp(cfg: AppConfig) -> float | None:
    entity_id = cfg.home_assistant.outside_temperature_entity_id
    if not entity_id:
        return None
    ha_url = cfg.home_assistant.url.rstrip("/")
    token = cfg.home_assistant.token
    async with httpx.AsyncClient(timeout=10.0) as client:
        entity = await _fetch_entity(client, ha_url, token, entity_id, "")
    if entity is None:
        return None
    try:
        return float(entity.state)
    except (ValueError, TypeError):
        return None


async def get_garden_temps(cfg: AppConfig) -> GardenTemps:
    ha = cfg.home_assistant
    ha_url = ha.url.rstrip("/")
    token = ha.token

    async def _fetch_temp(entity_id: str) -> float | None:
        if not entity_id:
            return None
        async with httpx.AsyncClient(timeout=10.0) as client:
            entity = await _fetch_entity(client, ha_url, token, entity_id, "")
        if entity is None:
            return None
        try:
            return float(entity.state)
        except (ValueError, TypeError):
            return None

    glasshouse, coop, brooder, glasshouse_hum, coop_hum, brooder_hum = await asyncio.gather(
        _fetch_temp(ha.glasshouse_entity_id),
        _fetch_temp(ha.coop_entity_id),
        _fetch_temp(ha.brooder_entity_id),
        _fetch_temp(ha.glasshouse_humidity_entity_id),
        _fetch_temp(ha.coop_humidity_entity_id),
        _fetch_temp(ha.brooder_humidity_entity_id),
        return_exceptions=True,
    )
    return GardenTemps(
        glasshouse=glasshouse if isinstance(glasshouse, float) else None,
        coop=coop if isinstance(coop, float) else None,
        brooder=brooder if isinstance(brooder, float) else None,
        glasshouse_humidity=glasshouse_hum if isinstance(glasshouse_hum, float) else None,
        coop_humidity=coop_hum if isinstance(coop_hum, float) else None,
        brooder_humidity=brooder_hum if isinstance(brooder_hum, float) else None,
    )


async def get_entities(cfg: AppConfig) -> list[HaEntity]:
    if not cfg.home_assistant.entities:
        return []

    ha_url = cfg.home_assistant.url.rstrip("/")
    token = cfg.home_assistant.token

    async with httpx.AsyncClient(timeout=10.0) as client:
        results = await asyncio.gather(
            *[
                _fetch_entity(client, ha_url, token, e.entity_id, e.label)
                for e in cfg.home_assistant.entities
            ]
        )

    return [r for r in results if r is not None]
