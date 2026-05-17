"""
One-shot NPC identity generation.

Godot provides a role, faction, region, and optional context hint.
Claude generates a full character that fits the world and will
behave consistently in dialogue.
"""

import json
from core.json_utils import safe_parse
import uuid
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.world_state import WorldState

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

NPC_ROLES = [
    "quest_giver",
    "merchant",
    "ally",
    "antagonist",
    "informant",
    "neutral",
    "authority",  # guard, official, faction leader
    "civilian",
]

_SYSTEM = """
You are a character designer for a living RPG world. Generate a single NPC
that feels like they belong in this specific world — not a generic archetype.

Return ONLY valid JSON — no explanation, no markdown fences.

Schema:
{
  "id": "<provided — do not change>",
  "name": "<full name>",
  "role": "<provided role>",
  "faction": "<provided faction>",
  "region": "<provided region>",
  "appearance": "<2 sentences — distinctive, specific, memorable>",
  "personality": ["<trait 1>", "<trait 2>", "<trait 3>"],
  "speech_style": "<how they talk — cadence, vocabulary, habits, tells>",
  "backstory": "<2 sentences — who they were before the current moment>",
  "current_situation": "<1-2 sentences — what they're dealing with right now>",
  "wants_from_player": "<what they hope to get from this interaction>",
  "secrets": ["<something they know but won't volunteer>", "<something they're hiding about themselves>"],
  "hooks": ["<plot thread this NPC could open>", "<another one>"]
}
"""


def spawn(
    role: str,
    faction: str,
    region: str,
    world: dict,
    world_state: WorldState,
    context_hint: str = "",
    npc_id: str | None = None,
) -> dict:
    """Generate a new NPC identity. Returns the NPC dict."""
    if npc_id is None:
        npc_id = uuid.uuid4().hex[:10]

    faction_info = ""
    if faction != "independent" and faction in world_state.factions:
        f = world_state.factions[faction]
        faction_info = f"Current standing: {f.label()} ({f.standing:+.0f}). {f.description}"

    region_info = ""
    if region in world_state.regions:
        r = world_state.regions[region]
        region_info = f"Regional tension: {r.tension:.2f}. Controlling faction: {r.controlling_faction or 'contested'}."

    prompt = f"""
WORLD
Name: {world.get('name', 'Unknown')}
Tone: {world.get('tone', '')}
Setting summary: {world.get('setting', '')[:300]}

NPC TO GENERATE
ID: {npc_id}
Role: {role}
Faction: {faction}
Region: {region}
{f'Context hint: {context_hint}' if context_hint else ''}

FACTION CONTEXT
{faction_info or 'Independent — no faction affiliation.'}

REGION CONTEXT
{region_info or 'No regional data available.'}

Generate an NPC who fits naturally into this specific world moment.
Their current_situation should reflect the faction and regional state above.
Their wants_from_player should make sense for their role.
Their secrets should be genuinely interesting — things that could matter.
""".strip()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            npc = safe_parse(block.text, "NPC generation")
            npc["id"] = npc_id  # enforce the ID we assigned
            return npc

    raise RuntimeError("Claude returned no text block during NPC generation.")
