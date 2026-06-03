import httpx

from app.core.config import settings


async def fetch_pokemon_context(pokemon_name: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{settings.pokeapi_base_url}/pokemon/{pokemon_name.lower().strip()}")
        resp.raise_for_status()
        payload = resp.json()

    return {
        "name": payload["name"],
        "height": payload.get("height"),
        "weight": payload.get("weight"),
        "types": [t["type"]["name"] for t in payload.get("types", [])],
        "abilities": [a["ability"]["name"] for a in payload.get("abilities", [])],
    }
