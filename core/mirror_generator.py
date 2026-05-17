"""
Player Mirror — a narrative portrait of who the player has become.

Uses everything the system knows: psychological profile, archetype,
mission history, faction relationships, lore discovered, stat investment,
resets. Writes in second person. Literary prose, not a stats summary.

The contradictions in the profile are the most interesting things to
surface — high aggression + high morality is someone who fights and
hates that they do. Those tensions make a character.
"""

import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.preferences import WorldPreferences
from core.world_state import WorldState
from core.resources import PlayerStats, STAT_KEYS
from core.creative_voice import WONDER_DIRECTIVE

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = f"""
You are a literary narrator who sees everything about a player and their
journey through a unique world. Your task is to write a Player Mirror —
a second-person narrative portrait of who this person has become.

{WONDER_DIRECTIVE}

WHAT THE MIRROR IS
- Literary prose. Second person ("You arrived...", "You've learned...", "You are...").
- 3-5 paragraphs. Each one earns its place.
- Specific: reference actual mission titles, faction names, world locations,
  lore discovered. Generalities are worthless. Specifics are everything.
- Emotionally true: the player should read this and feel seen, not summarized.
- Not a report. Not a stats breakdown. A portrait.

WHAT THE MIRROR IS NOT
- Not a recap of events ("You completed these missions...")
- Not mechanical ("Your aggression score is 0.7...")
- Not congratulatory ("Great job, you've...")
- Not a list of anything

STRUCTURE (internal guide — do not label paragraphs)
1. An opening observation about who they were when they arrived —
   their bearing, their way of moving through a world. Atmospheric.
2. What the world has revealed about them. The pattern in their choices.
   The thing they reach for first. What they avoid.
3. The contradiction at their core — if one exists. The tension between
   what they intend and what they do. This is where character lives.
4. What the world looks like from where they stand now. Factions,
   relationships, the shape of things. Specific. Earned.
5. (Optional — only if it's true) Something forward. Not a prediction.
   An honest observation about where this is all heading.

TONE
Write with the quiet authority of someone who has been watching carefully
and is now telling the truth without flinching. Not cruel. Not kind.
Honest. The mirror shows what is actually there.

Return ONLY the mirror text — no JSON, no headers, no formatting.
Plain prose. Nothing else.
"""


def generate(
    profile: PlayerProfile,
    archetype: dict,
    world: dict,
    world_state: WorldState,
    preferences: WorldPreferences,
    mission_history: list[dict],
    lore_discovered: list[dict],
    stats: PlayerStats | None,
    reset_history: list[dict],
    in_game_day: int,
) -> str:
    prompt = f"""
THE WORLD
Name: {world.get('name', 'Unknown')}
Tone: {world.get('tone', '')}
Setting: {world.get('setting', '')[:300]}

WHO THEY WERE
Archetype: {archetype.get('name', '')}: {archetype.get('summary', '')}
World tone the archetype suggested: {archetype.get('world_tone', '')}
Motifs that define them: {', '.join(archetype.get('motifs', []))}

WHO THEY ARE NOW — PSYCHOLOGICAL PROFILE
(Do not recite these numbers. Read them. Write from what they mean.)
Aggression:     {_fv(profile.aggression)}   (0=avoidant/diplomatic, 1=combative)
Morality:       {_fv(profile.morality)}   (0=self-serving, 1=altruistic)
Lawfulness:     {_fv(profile.lawfulness)}   (0=chaotic/defiant, 1=lawful/institutional)
Empathy:        {_fv(profile.empathy)}   (0=blunt/transactional, 1=warm/perceptive)
Deliberateness: {_fv(profile.deliberateness)}   (0=impulsive, 1=cautious)
Sociability:    {_fv(profile.sociability)}   (0=lone wolf, 1=coalition-builder)
Deference:      {_fv(profile.deference)}   (0=openly defiant, 1=deferential)
Immersion:      {_fv(profile.immersion)}   (0=treats it as a game, 1=fully inhabits)
Top themes:     {', '.join(profile.top_themes())}
Total observations: {profile.observation_count}

PROFILE CONTRADICTIONS TO SURFACE
{_fmt_contradictions(profile)}

WHAT THEY'VE DONE — MISSION HISTORY ({len(mission_history)} missions)
{_fmt_missions(mission_history)}

HOW THE WORLD HAS CHANGED AROUND THEM
{_fmt_world_state(world_state)}

WHAT THEY'VE DISCOVERED
{_fmt_lore(lore_discovered)}

WHAT THEY'VE INVESTED IN
{_fmt_stats(stats, world)}

{_fmt_resets(reset_history)}

In-game days passed: {in_game_day}

---

Write the mirror now. 3-5 paragraphs. Second person. Specific to this
player in this world. Make it true.
""".strip()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=1200,
        thinking={"type": "enabled", "budget_tokens": 3000},
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            return block.text.strip()

    raise RuntimeError("Claude returned no text block for mirror generation.")


def _fmt_contradictions(profile: PlayerProfile) -> str:
    contradictions = []

    def _v(val):
        return val if val is not None else 0.5

    agg = _v(profile.aggression)
    mor = _v(profile.morality)
    law = _v(profile.lawfulness)
    emp = _v(profile.empathy)
    deli = _v(profile.deliberateness)
    soc = _v(profile.sociability)
    def_ = _v(profile.deference)

    if agg > 0.65 and mor > 0.65:
        contradictions.append("Fights often, cares deeply — someone who uses violence and resents needing to.")
    if agg < 0.35 and mor < 0.35:
        contradictions.append("Avoids conflict but pursues self-interest — someone who is careful, not kind.")
    if law > 0.65 and mor < 0.35:
        contradictions.append("Follows rules but not for others' benefit — loyalty to order, not people.")
    if law < 0.35 and mor > 0.65:
        contradictions.append("Breaks rules to do good — treats institutions as obstacles to justice.")
    if soc > 0.65 and def_ < 0.35:
        contradictions.append("Builds coalitions but refuses authority — leads without being led.")
    if soc < 0.35 and emp > 0.65:
        contradictions.append("Perceptive and warm, but alone — someone who sees people clearly and keeps distance anyway.")
    if deli > 0.7 and agg > 0.65:
        contradictions.append("Plans carefully, acts violently — the deliberateness makes the aggression more precise, not less.")
    if deli < 0.3 and mor > 0.65:
        contradictions.append("Acts before thinking, but always for others — impulsive altruism, consequences be damned.")

    if not contradictions:
        return "No strong contradictions detected — this person is unusually consistent. Note that in the mirror."
    return "\n".join(f"- {c}" for c in contradictions)


def _fmt_missions(history: list[dict]) -> str:
    if not history:
        return "No missions completed yet."
    recent = history[-8:]
    lines = []
    success = sum(1 for m in history if m.get("outcome") == "success")
    partial = sum(1 for m in history if m.get("outcome") == "partial")
    failure = sum(1 for m in history if m.get("outcome") == "failure")
    lines.append(f"Overall: {success} succeeded, {partial} partial, {failure} failed")

    type_counts: dict[str, int] = {}
    for m in history:
        t = m.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    dominant = sorted(type_counts, key=type_counts.get, reverse=True)[:2]
    lines.append(f"Gravitates toward: {', '.join(dominant)}")
    lines.append("Recent missions:")
    for m in recent:
        lines.append(f"  [{m.get('type','?')}] \"{m.get('title','?')}\" — {m.get('outcome','?')} via {m.get('approach_used','?')}")
    return "\n".join(lines)


def _fmt_world_state(ws: WorldState) -> str:
    if not ws.factions:
        return "World state not yet seeded."
    lines = []
    allied = [n for n, f in ws.factions.items() if f.standing >= 40]
    hostile = [n for n, f in ws.factions.items() if f.standing <= -40]
    neutral = [n for n, f in ws.factions.items() if -40 < f.standing < 40]
    if allied:
        lines.append(f"Allies: {', '.join(allied)}")
    if hostile:
        lines.append(f"Enemies: {', '.join(hostile)}")
    if neutral:
        lines.append(f"Neutral: {', '.join(neutral)}")
    lines.append(f"Global tension: {ws.global_tension:.2f}")
    return "\n".join(lines) if lines else "No significant faction shifts yet."


def _fmt_lore(lore: list[dict]) -> str:
    if not lore:
        return "No lore discovered yet."
    lines = [f"{len(lore)} entries found"]
    secrets = [e for e in lore if e.get("reveals_secret")]
    if secrets:
        lines.append(f"Significant secrets uncovered: {len(secrets)}")
        for s in secrets[:3]:
            lines.append(f"  - \"{s.get('title', '?')}\"")
    else:
        for e in lore[:4]:
            lines.append(f"  - \"{e.get('title', '?')}\" ({e.get('type', '?')})")
    return "\n".join(lines)


def _fmt_stats(stats: PlayerStats | None, world: dict) -> str:
    if stats is None:
        return "Stats not initialized."
    flavors = world.get("stat_flavors", {})
    elevated = [(k, getattr(stats, k)) for k in STAT_KEYS if getattr(stats, k) >= 4]
    if not elevated:
        return "No stats significantly elevated yet — still early."
    return "Elevated: " + ", ".join(
        f"{flavors.get(k, k.title())} {v}/10" for k, v in elevated
    )


def _fmt_resets(resets: list[dict]) -> str:
    if not resets:
        return ""
    lines = [f"REINVENTION HISTORY ({len(resets)} reset(s))"]
    for r in resets:
        lines.append(
            f"  Day {r.get('in_game_day', '?')}: reset via {r['method']} "
            f"(was '{r.get('archetype_at_reset', '?')}', "
            f"{r.get('mission_count_at_reset', 0)} missions in)"
        )
    return "\n".join(lines)


def _fv(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else "unobserved"
