"""
On-demand lore generation.

Every call receives the full discovered lore corpus so Claude builds on
what's already been established rather than contradicting it. The framing
matters: lore is revealed, not invented — it always existed in this world.
"""

import json
from core.json_utils import safe_parse
import uuid
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.preferences import WorldPreferences
from core.world_state import WorldState
from core.creative_voice import WONDER_DIRECTIVE

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

LORE_TYPES = [
    "history",    # events that shaped the world before the player arrived
    "myth",       # beliefs, religions, folklore, things people fear or revere
    "secret",     # hidden truth — about a faction, figure, or the central conflict
    "figure",     # a historical or legendary person
    "artifact",   # what a found object means and where it came from
    "place",      # what a region or location's past actually was
    "faction_lore", # origin, founding ideology, internal tensions of a faction
]

TRIGGERS = ["artifact", "location", "book", "npc_conversation", "mission_complete"]

_SYSTEM = f"""
You are the keeper of lore for a unique RPG world. Your role is to reveal
what has always been true about this world — not to invent things on the spot,
but to uncover what was already there.

Consistency is everything. Read the existing discovered lore carefully.
Build on it, reference it, deepen it. Never contradict it.

{WONDER_DIRECTIVE}

Return ONLY valid JSON — no explanation, no markdown fences.

Schema:
{
  "id": "<provided — do not change>",
  "type": "<history|myth|secret|figure|artifact|place|faction_lore>",
  "title": "<evocative, specific — not generic>",
  "content": "<3-5 sentences of actual lore text, written as in-world truth — not a game description>",
  "discovered_via": "<the trigger provided>",
  "region": "<most relevant region, or null>",
  "faction": "<most relevant faction, or null>",
  "tags": ["<2-4 thematic tags>"],
  "reveals_secret": <true if this is significant hidden knowledge, false otherwise>,
  "connections": ["<id of existing lore this connects to, if any>"],
  "player_note": "<one sentence: why this piece of lore resonates specifically for this player>"
}

Write the content as if it appears in a codex — authoritative, atmospheric,
specific to this world. No generic fantasy tropes. No "in a land far away."
Draw on the world's actual tone, factions, and history.
"""


def discover(
    trigger: str,
    context: str,
    world: dict,
    world_state: WorldState,
    profile: PlayerProfile,
    preferences: WorldPreferences,
    archetype: dict,
    lore_discovered: list[dict],
    region: str = "",
    faction: str = "",
) -> dict:
    """Generate one lore entry. Returns the lore dict."""
    lore_id = uuid.uuid4().hex[:8]

    focus = preferences.gamer_focus.normalized()

    # Bias lore type toward what this player cares about
    type_hints = []
    if focus["story"] >= 0.25:
        type_hints += ["history", "figure", "secret"]
    if focus["world"] >= 0.25:
        type_hints += ["myth", "place", "history"]
    if focus["social"] >= 0.25:
        type_hints += ["faction_lore", "secret", "figure"]
    if focus["combat"] >= 0.25:
        type_hints += ["history", "artifact", "figure"]
    if not type_hints:
        type_hints = LORE_TYPES

    # Deduplicate while preserving order preference
    seen = set()
    preferred_types = [t for t in type_hints if not (t in seen or seen.add(t))]

    existing_summary = _fmt_existing(lore_discovered)

    prompt = f"""
WORLD
Name: {world.get('name', 'Unknown')}
Tone: {world.get('tone', '')}
Setting: {world.get('setting', '')[:400]}
Central conflict: {world.get('central_conflict', {}).get('description', '')}

FACTIONS (current state)
{_fmt_factions(world_state)}

REGIONS (current state)
{_fmt_regions(world_state)}

PLAYER
Archetype: {archetype.get('name', '')}: {archetype.get('summary', '')}
Motifs: {', '.join(archetype.get('motifs', []))}
Top themes: {', '.join(profile.top_themes())}
Gamer focus — story:{focus['story']:.0%} world:{focus['world']:.0%} social:{focus['social']:.0%} combat:{focus['combat']:.0%}

DISCOVERY TRIGGER
How it was found: {trigger}
Context: {context}
{f'Region: {region}' if region else ''}
{f'Faction: {faction}' if faction else ''}

ALREADY DISCOVERED LORE (do not contradict — build on this)
{existing_summary}

LORE ENTRY TO GENERATE
ID: {lore_id}
Preferred types (in order): {', '.join(preferred_types[:3])}

Choose the most fitting type given the trigger and context.
The content should feel like it was always part of this world.
Reference specific faction and region names — no vague placeholders.
If the existing lore establishes facts, honour them and deepen them.
The player's archetype motifs ({', '.join(archetype.get('motifs', []))}) should
surface subtly — as a recurring symbol, a name echo, or a thematic resonance.
""".strip()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            entry = safe_parse(block.text, "lore generation")
            entry["id"] = lore_id
            return entry

    raise RuntimeError("Claude returned no text block during lore generation.")


def _fmt_existing(lore: list[dict]) -> str:
    if not lore:
        return "  None yet — this is the first discovery. Establish foundational truths."
    lines = []
    for entry in lore:
        lines.append(
            f"  [{entry['id']}] {entry['title']} ({entry['type']})"
            + (f" — connects to: {entry.get('connections', [])}" if entry.get("connections") else "")
        )
        lines.append(f"    {entry['content'][:200]}...")
    return "\n".join(lines)


def _fmt_factions(ws: WorldState) -> str:
    if not ws.factions:
        return "  (none seeded)"
    return "\n".join(
        f"  {name}: {f.label()} ({f.standing:+.0f})"
        for name, f in ws.factions.items()
    )


def _fmt_regions(ws: WorldState) -> str:
    if not ws.regions:
        return "  (none seeded)"
    return "\n".join(
        f"  {name}: tension {r.tension:.2f}"
        for name, r in ws.regions.items()
    )
