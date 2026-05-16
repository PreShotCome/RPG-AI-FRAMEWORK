import json
import random
import anthropic
from pathlib import Path
from config import MODEL
from core.player_profile import PlayerProfile

_training_world: dict | None = None

def _load_training_world() -> dict:
    global _training_world
    if _training_world is None:
        with open(Path("data/training_world.json")) as f:
            _training_world = json.load(f)
    return _training_world

def get_training_world() -> dict:
    return _load_training_world()

def get_area_info(area_id: str, seed: int) -> dict:
    world = _load_training_world()
    for area in world["areas"]:
        if area["id"] == area_id:
            return area
    return {}

async def generate_real_world(profile: PlayerProfile, seed: int, client: anthropic.AsyncAnthropic) -> dict:
    """Generate a full world based on player profile. Called at checkpoint."""

    rng = random.Random(seed)
    world_id = f"world_{seed}"

    profile_summary = profile.get_summary_for_ai()
    moral = profile.get_moral_label()
    law = profile.get_law_label()
    themes = profile.get_top_themes(3)
    playstyle = profile.get_dominant_playstyle()

    prompt = f"""You are generating a unique fantasy RPG world for a specific player.

PLAYER PROFILE:
{profile_summary}

WORLD GENERATION RULES:
1. The world's central conflict reflects the player's moral/law alignment:
   - Moral: {moral} (good=oppression/injustice to fight, evil=power to seize, neutral=balance/survival)
   - Law: {law} (lawful=corrupt institutions, chaotic=dangerous freedom, neutral=fractured order)
2. The primary gameplay hooks match the playstyle: {playstyle}
3. The tone and aesthetic reflect these themes: {", ".join(themes)}
4. Make everything feel personal to THIS player — not generic fantasy

Generate a world in this EXACT JSON structure (no markdown, just JSON):
{{
  "name": "world name",
  "tagline": "one evocative sentence",
  "description": "2-3 paragraph world overview written for a player, not a narrator",
  "central_conflict": "the core tension driving the world",
  "tone": "the emotional register of this world",
  "regions": [
    {{
      "id": "region_id",
      "name": "region name",
      "description": "what it feels like to be here",
      "dominant_faction": "who controls this",
      "primary_hook": "why the player would care",
      "unlocked_at_act": 0
    }}
  ],
  "factions": [
    {{
      "id": "faction_id",
      "name": "faction name",
      "description": "what they want and how they operate",
      "alignment": "good/evil/neutral",
      "player_can_join": true
    }}
  ],
  "world_secrets": [
    "a secret the world holds that only exploration will reveal"
  ],
  "campaign_hook": "the inciting incident that pulls the player into the main story"
}}

Generate 3 regions and 3 factions. Make them feel organic, specific, and surprising — not generic."""

    async with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        text = await stream.get_final_text()

    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]

    try:
        world_data = json.loads(text)
    except Exception:
        # Fallback world
        world_data = _fallback_world(profile, seed)

    world_data["world_id"] = world_id
    world_data["seed"] = seed
    world_data["generated_for_archetype"] = profile.archetype
    return world_data

def _fallback_world(profile: PlayerProfile, seed: int) -> dict:
    """Minimal fallback if generation fails."""
    return {
        "name": "The Unnamed World",
        "tagline": "A world built from your choices.",
        "description": "A world that feels strangely familiar, as if it was made for you.",
        "central_conflict": "Order against the chaos that freedom brings.",
        "tone": "uncertain but full of possibility",
        "regions": [
            {
                "id": "starting_region",
                "name": "The First Roads",
                "description": "Where your story truly begins.",
                "dominant_faction": "The Keepers",
                "primary_hook": "Someone knows your name. You've never met them.",
                "unlocked_at_act": 0
            }
        ],
        "factions": [
            {
                "id": "keepers",
                "name": "The Keepers",
                "description": "They maintain what exists. Change frightens them.",
                "alignment": "neutral",
                "player_can_join": True
            }
        ],
        "world_secrets": ["The world was built, not born."],
        "campaign_hook": "A message arrives — addressed to you — dated three years from now."
    }
