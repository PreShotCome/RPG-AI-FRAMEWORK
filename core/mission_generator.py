"""
Mission generator — produces a pool of contextually appropriate missions.

Every generation reads the live profile, world state, and mission history,
so the pool drifts naturally as the player evolves.
"""

import json
import uuid
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.preferences import WorldPreferences
from core.world_state import WorldState
from core.resources import PlayerStats, STAT_KEYS

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MISSION_TYPES = [
    "combat",        # eliminate, defend, assault
    "investigation", # uncover, expose, gather intel
    "social",        # negotiate, manipulate, forge alliances
    "exploration",   # discover, map, recover lost things
    "heist",         # steal, infiltrate, sabotage
    "delivery",      # escort, transport, courier under pressure
]

_SYSTEM = """
You are a mission designer for a living RPG world. You generate a pool of missions
that feel handcrafted for this specific player and world moment.

Return ONLY a valid JSON array of mission objects — no explanation, no markdown fences.

Each mission must:
- Fit naturally into the current world state and faction tensions
- Suit the player's psychological profile (not just their stated preferences)
- Offer at least two meaningfully different approaches
- Have real consequences for factions and regions

Mission schema (generate exactly the count requested):
{
  "id": "<8-char hex string>",
  "title": "<evocative, specific title>",
  "type": "<combat|investigation|social|exploration|heist|delivery>",
  "giver": {
    "name": "<NPC name>",
    "faction": "<faction name or 'independent'>",
    "tone": "<how they speak and why they need this done>"
  },
  "summary": "<one sentence — what the player is asked to do>",
  "description": "<2-3 sentences — full context, what's at stake, the texture of the situation>",
  "location": "<region name from the world>",
  "approaches": [
    {"method": "<approach name>", "description": "<how this works>"},
    {"method": "<approach name>", "description": "<how this works>"}
  ],
  "stakes": {
    "success": "<what changes in the world if this succeeds>",
    "failure": "<what changes if it fails>",
    "moral_weight": "<the ethical tension — what makes this complicated>"
  },
  "faction_impact": {
    "<faction_name>": <float -30 to +30>,
    ...
  },
  "region_tension_impact": {
    "<region_name>": <float -0.2 to +0.2>
  },
  "difficulty": "<low|medium|high>",
  "profile_fit": "<one sentence: why this mission was chosen for this specific player>"
}
"""


def generate_pool(
    archetype: dict,
    profile: PlayerProfile,
    preferences: WorldPreferences,
    world: dict,
    world_state: WorldState,
    history: list[dict],
    pool_size: int = 4,
    stats: PlayerStats | None = None,
) -> list[dict]:
    """Generate a fresh mission pool. Uses extended thinking for coherence."""

    recent_history = history[-6:] if history else []
    completed_types = [m.get("type") for m in recent_history]
    completed_locations = [m.get("location") for m in recent_history]

    focus = preferences.gamer_focus.normalized()
    top_focus = preferences.gamer_focus.top(2)

    prompt = f"""
WORLD
Name: {world.get('name', 'Unknown')}
Setting: {world.get('setting', '')[:400]}
Tone: {world.get('tone', '')}

FACTIONS (current standing)
{_fmt_factions(world_state)}

REGIONS (current tension)
{_fmt_regions(world_state)}

PLAYER ARCHETYPE
{archetype['name']}: {archetype['summary']}
Motifs: {', '.join(archetype['motifs'])}

PLAYER PROFILE (live — evolving throughout the game)
Aggression:     {_fv(profile.aggression)}
Morality:       {_fv(profile.morality)}
Lawfulness:     {_fv(profile.lawfulness)}
Empathy:        {_fv(profile.empathy)}
Deliberateness: {_fv(profile.deliberateness)}
Sociability:    {_fv(profile.sociability)}
Deference:      {_fv(profile.deference)}
Top themes:     {', '.join(profile.top_themes())}

GAMER FOCUS
Primary: {top_focus[0]} ({focus[top_focus[0]]:.0%})
Secondary: {top_focus[1]} ({focus[top_focus[1]]:.0%})
Full weights — story:{focus['story']:.0%} world:{focus['world']:.0%} missions:{focus['missions']:.0%} combat:{focus['combat']:.0%} social:{focus['social']:.0%}

PLAYER STATS (1-10 — what they're actually capable of)
{_fmt_stats(stats, world)}

MISSION HISTORY (last {len(recent_history)} completed)
{_fmt_history(recent_history)}

INSTRUCTIONS
Generate {pool_size} missions.

- Do NOT repeat mission types that dominate the recent history: {completed_types}
- Vary locations — avoid repeating: {completed_locations}
- Weight mission TYPES toward gamer focus:
    combat focus → more combat/heist missions
    story/social focus → more social/investigation missions
    world/exploration focus → more exploration/investigation missions
    missions focus → clear objectives, layered delivery/heist missions
- The player's profile should be visible in WHY each mission was chosen.
  A high-morality player gets missions where helping someone costs them something.
  A high-aggression player gets missions where restraint is the harder path.
  A chaotic player gets missions that let them destabilize entrenched power.
- The archetype motifs ({', '.join(archetype['motifs'])}) should appear subtly
  in at least two missions — as symbols, NPC names, or situation echoes.
- Stats shape what approaches are genuinely viable:
    combat ≥6 → describe combat approaches as effective, not just possible
    stealth ≥6 → infiltration/ghost routes are a real option
    persuasion ≥6 → social approaches can resolve what force cannot
    intellect ≥6 → investigation angles, pattern recognition, information plays
    endurance ≥6 → high-difficulty missions are within reach; attrition works
    luck ≥6 → surface at least one approach that involves opportunism or chance
  Low stats (≤3) in a key area mean that approach carries real risk — say so.
- Match difficulty to stats: if combat=2, don't make all missions high-difficulty
  combat encounters. Surface missions where the player's strengths apply.
- Generate IDs as random 8-char hex strings.
- Use only region and faction names that appear in the world above.
""".strip()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=6000,
        thinking={"type": "enabled", "budget_tokens": 4000},
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            missions = json.loads(block.text.strip())
            for m in missions:
                if "id" not in m or not m["id"]:
                    m["id"] = uuid.uuid4().hex[:8]
            return missions

    raise RuntimeError("Claude returned no text block during mission generation.")


def _fmt_factions(ws: WorldState) -> str:
    if not ws.factions:
        return "  (no factions seeded yet)"
    return "\n".join(
        f"  {name}: {f.label()} ({f.standing:+.0f})"
        for name, f in ws.factions.items()
    )


def _fmt_regions(ws: WorldState) -> str:
    if not ws.regions:
        return "  (no regions seeded yet)"
    return "\n".join(
        f"  {name}: tension {r.tension:.2f}"
        for name, r in ws.regions.items()
    )


def _fmt_history(history: list[dict]) -> str:
    if not history:
        return "  None yet — this is the player's first mission pool."
    lines = []
    for m in history:
        outcome = m.get("outcome", "unknown")
        approach = m.get("approach_used", "unspecified")
        lines.append(f"  [{m.get('type','?')}] {m.get('title','?')} — {outcome} via {approach}")
    return "\n".join(lines)


def _fv(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else "unknown"


def _fmt_stats(stats: PlayerStats | None, world: dict) -> str:
    if stats is None:
        return "  (not yet initialized)"
    flavors = world.get("stat_flavors", {})
    lines = []
    for key in STAT_KEYS:
        level = getattr(stats, key)
        display = flavors.get(key, key.title())
        bar = "█" * level + "░" * (10 - level)
        lines.append(f"  {display:15} {bar} {level}/10")
    return "\n".join(lines)
