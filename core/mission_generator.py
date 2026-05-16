import json
import random
import anthropic
from pathlib import Path
from config import MODEL
from core.player_profile import PlayerProfile

_mission_templates: dict | None = None

def _load_templates() -> dict:
    global _mission_templates
    if _mission_templates is None:
        with open(Path("data/mission_templates.json")) as f:
            _mission_templates = json.load(f)
    return _mission_templates

def get_training_missions() -> list[dict]:
    with open(Path("data/training_world.json")) as f:
        world = json.load(f)
    return world.get("campaign_missions", [])

async def generate_npc_mission(
    npc_id: str,
    npc_role: str,
    profile: PlayerProfile,
    world_context: str,
    client: anthropic.AsyncAnthropic,
) -> dict:
    """Generate a side mission from an NPC, tailored to the player's profile."""

    templates = _load_templates()
    role_missions = templates["npc_role_mission_map"].get(npc_role, ["investigation"])

    # Pick mission types that align with player profile
    top_themes = profile.get_top_themes(2)
    playstyle = profile.get_dominant_playstyle()

    # Score mission types
    scored = []
    for mission_type in role_missions:
        mt = templates["mission_types"].get(mission_type, {})
        score = 0
        for theme in top_themes:
            if theme in mt.get("preferred_by", []):
                score += 2
        if playstyle in mt.get("playstyle_fit", []):
            score += 3
        scored.append((mission_type, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    chosen_type = scored[0][0] if scored else "investigation"

    moral = profile.get_moral_label()
    law = profile.get_law_label()

    prompt = f"""Generate a short RPG side mission for a player with this profile:
- Playstyle: {playstyle}
- Alignment: {moral}/{law}
- Top themes: {", ".join(top_themes)}
- Mission type: {chosen_type}
- Mission giver role: {npc_role} (NPC id: {npc_id})

World context:
{world_context}

Return ONLY valid JSON:
{{
  "id": "mission_{npc_id}_{chosen_type}",
  "title": "short evocative title",
  "description": "2-3 sentence description written to the player",
  "type": "{chosen_type}",
  "giver_npc": "{npc_id}",
  "objective": "clear one-sentence goal",
  "reward_hint": "vague hint at reward (not specific numbers)",
  "complication": "one twist that makes this harder or morally interesting",
  "xp_value": 50,
  "is_campaign": false
}}"""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]

    try:
        return json.loads(text)
    except Exception:
        return {
            "id": f"mission_{npc_id}_fallback",
            "title": "A Small Favor",
            "description": "Someone needs help. They haven't said with what yet.",
            "type": chosen_type,
            "giver_npc": npc_id,
            "objective": "Find out what's needed and decide whether to help.",
            "reward_hint": "Gratitude, at least.",
            "complication": "Nothing is ever as simple as it seems.",
            "xp_value": 25,
            "is_campaign": False
        }

async def generate_campaign_mission(
    act: int,
    mission_number: int,
    profile: PlayerProfile,
    world_data: dict,
    client: anthropic.AsyncAnthropic,
) -> dict:
    """Generate a main campaign mission tailored to the player and world."""

    profile_summary = profile.get_summary_for_ai()
    world_name = world_data.get("name", "The World")
    conflict = world_data.get("central_conflict", "an ancient conflict")
    hook = world_data.get("campaign_hook", "something pulls you forward")

    prompt = f"""Generate Act {act + 1}, Mission {mission_number + 1} of the main campaign.

World: {world_name}
Central conflict: {conflict}
Campaign hook: {hook}

Player profile:
{profile_summary}

This is mission {mission_number + 1} of 3 in Act {act + 1}.
{"First mission: introduction, establish stakes." if mission_number == 0 else ""}
{"Second mission: complication, raise the cost." if mission_number == 1 else ""}
{"Third mission: climax of this act, significant consequence." if mission_number == 2 else ""}

Return ONLY valid JSON:
{{
  "id": "campaign_act{act}_m{mission_number}",
  "title": "title",
  "description": "2-3 sentences to the player",
  "type": "mission type",
  "objective": "clear goal",
  "stakes": "what happens if they fail",
  "reward_hint": "vague reward hint",
  "xp_value": {150 + act * 50 + mission_number * 25},
  "is_campaign": true,
  "act": {act},
  "mission_number": {mission_number}
}}"""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]

    try:
        return json.loads(text)
    except Exception:
        return {
            "id": f"campaign_act{act}_m{mission_number}",
            "title": f"Act {act + 1}: The Path Ahead",
            "description": "The road continues. What you find depends on what you carry.",
            "type": "investigation",
            "objective": "Advance the story.",
            "stakes": "The world changes without you if you wait.",
            "reward_hint": "Something you didn't expect.",
            "xp_value": 150 + act * 50,
            "is_campaign": True,
            "act": act,
            "mission_number": mission_number
        }
