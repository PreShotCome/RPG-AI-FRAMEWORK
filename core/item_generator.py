"""
Generates loot items from mission outcomes and NPC interactions.
Items are narrative-grounded — Claude decides what was found based on context.
"""

import uuid
from datetime import datetime, timezone
import random
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.json_utils import safe_parse

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_LOOT_ODDS = {"success": 0.55, "partial": 0.20, "failure": 0.0}


def maybe_generate_item(
    mission: dict,
    outcome: str,
    world: dict,
    archetype: dict,
) -> dict | None:
    """
    Roll for loot and generate an item if the roll hits.
    Returns item dict or None. Never raises — returns None on any error.
    """
    if random.random() > _LOOT_ODDS.get(outcome, 0.0):
        return None

    world_name = world.get("name", "Unknown")
    world_tone = world.get("tone", "")
    arch_name = archetype.get("name", "") if archetype else ""

    prompt = (
        f"Mission: {mission.get('title', '?')} ({mission.get('type', '?')}, {outcome})\n"
        f"World: {world_name} — {world_tone}\n"
        f"Player archetype: {arch_name}\n\n"
        "Generate ONE item the player found or received as a result of this mission. "
        "Make it specific to the mission context and world tone — not generic.\n\n"
        'Return ONLY valid JSON:\n'
        '{"name": "<item name>", '
        '"type": "<equipment|artifact|data|consumable|key_item>", '
        '"description": "<1-2 sentences: what it is and how it was obtained>"}'
    )

    try:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        data = safe_parse(response.content[0].text, "item generation")
        data["id"] = str(uuid.uuid4())
        data["acquired_at"] = datetime.now(timezone.utc).isoformat()
        data["acquired_from"] = mission.get("title", "unknown mission")
        return data
    except Exception:
        return None
