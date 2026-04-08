import asyncio

import httpx

from config import AppConfig
from models import GardenTemps, HaEntity, Meals


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


async def get_meals(cfg: AppConfig) -> Meals | None:
    ha = cfg.home_assistant
    ids = [ha.soup_today_entity_id, ha.soup_tomorrow_entity_id, ha.lunch_today_entity_id, ha.lunch_tomorrow_entity_id]
    if not all(ids):
        return None

    ha_url = ha.url.rstrip("/")
    token = ha.token
    async with httpx.AsyncClient(timeout=10.0) as client:
        results = await asyncio.gather(
            *[_fetch_entity(client, ha_url, token, eid, "") for eid in ids],
            return_exceptions=True,
        )

    def _state(r: object) -> str:
        return r.state if isinstance(r, HaEntity) else ""

    return Meals(
        soup_today=_state(results[0]),
        soup_tomorrow=_state(results[1]),
        lunch_today=_state(results[2]),
        lunch_tomorrow=_state(results[3]),
    )


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

    glasshouse, coop, brooder = await asyncio.gather(
        _fetch_temp(ha.glasshouse_entity_id),
        _fetch_temp(ha.coop_entity_id),
        _fetch_temp(ha.brooder_entity_id),
        return_exceptions=True,
    )
    return GardenTemps(
        glasshouse=glasshouse if isinstance(glasshouse, float) else None,
        coop=coop if isinstance(coop, float) else None,
        brooder=brooder if isinstance(brooder, float) else None,
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
