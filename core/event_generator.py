"""
Event generator — produces world events when the tick says pressure is high enough.

Events are consequences of what the player has done and what the world has become,
not random noise.
"""

import json
import uuid
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.preferences import WorldPreferences
from core.world_state import WorldState

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """
You are a world event designer for a living RPG. Generate world events that feel
like natural consequences of the current tensions, player actions, and faction dynamics.

Events should feel inevitable in hindsight — "of course that happened given everything."

Return ONLY a valid JSON array of event objects — no explanation, no markdown fences.

Event schema:
{
  "id": "<8-char hex>",
  "type": "<faction_conflict|uprising|political_shift|assassination|power_vacuum|criminal_surge|discovery|treaty>",
  "scope": "<local|global>",
  "urgency": "<background|slow_burn|immediate>",
  "title": "<specific, evocative — not generic>",
  "description": "<2-3 sentences: what happened, why now, what it means>",
  "affected_regions": ["<region name>"],
  "affected_factions": ["<faction name>"],
  "immediate_world_impact": {
    "faction_impacts": {"<faction_name>": <float -20 to +20>},
    "region_tension_impacts": {"<region_name>": <float -0.15 to +0.15>}
  },
  "player_options": [
    {
      "id": "<3-char id>",
      "label": "<short action label>",
      "description": "<what the player actually does>",
      "faction_alignment": "<which factions this helps or hurts>",
      "world_impact": {
        "faction_impacts": {"<faction_name>": <float -25 to +25>},
        "region_tension_impacts": {"<region_name>": <float -0.2 to +0.2>}
      }
    }
  ],
  "narrative_hook": "<one sentence — what makes this moment personally meaningful for this player>"
}

Rules:
- background urgency events have 0 player_options (they just happen)
- slow_burn and immediate events must have 2-3 player_options with meaningfully different consequences
- Use only faction and region names from the world provided
- Events must feel CAUSED — reference the tensions and recent actions that led here
- The narrative_hook should connect to the player's archetype and themes, not be generic
"""


def generate(
    count: int,
    world: dict,
    world_state: WorldState,
    profile: PlayerProfile,
    preferences: WorldPreferences,
    archetype: dict,
    mission_history: list[dict],
    event_log: list[dict],
    suggested_types: list[str],
) -> list[dict]:
    recent_missions = mission_history[-5:]
    recent_events = event_log[-4:]

    prompt = f"""
WORLD
Name: {world.get('name', 'Unknown')}
Tone: {world.get('tone', '')}
Central conflict: {world.get('central_conflict', {}).get('description', '')}

CURRENT WORLD STATE
Global tension: {world_state.global_tension:.2f}

Factions:
{_fmt_factions(world_state)}

Regions:
{_fmt_regions(world_state)}

PLAYER
Archetype: {archetype.get('name', '')}: {archetype.get('summary', '')}
Themes: {', '.join(archetype.get('motifs', []))}
Aggression: {_fv(profile.aggression)} | Lawfulness: {_fv(profile.lawfulness)} | Morality: {_fv(profile.morality)}

RECENT MISSIONS (what the player has been doing)
{_fmt_missions(recent_missions)}

RECENT EVENTS (what has already happened — do not repeat)
{_fmt_events(recent_events)}

SUGGESTED EVENT TYPES (bias toward these, but use your judgment)
{', '.join(suggested_types)}

Generate exactly {count} event(s).

The event(s) should feel like a direct consequence of the tensions above.
If a faction has been taking hits, they react. If a region is at high tension, it breaks.
If the player has been working for one side, the other side notices.
Reference specifics — faction names, region names, recent events — not abstractions.
""".strip()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=3000,
        thinking={"type": "enabled", "budget_tokens": 3000},
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            events = json.loads(block.text.strip())
            for e in events:
                if "id" not in e or not e["id"]:
                    e["id"] = uuid.uuid4().hex[:8]
                e.setdefault("resolved", False)
                e.setdefault("player_options", [])
            return events

    raise RuntimeError("Claude returned no text block during event generation.")


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


def _fmt_missions(missions: list[dict]) -> str:
    if not missions:
        return "  None yet."
    return "\n".join(
        f"  [{m.get('type','?')}] {m.get('title','?')} — {m.get('outcome','?')} via {m.get('approach_used','?')}"
        for m in missions
    )


def _fmt_events(events: list[dict]) -> str:
    if not events:
        return "  None yet."
    return "\n".join(f"  {e.get('title','?')} ({e.get('type','?')})" for e in events)


def _fv(val) -> str:
    return f"{val:.2f}" if val is not None else "unknown"
