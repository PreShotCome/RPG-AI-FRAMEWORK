"""
NPC dialogue for the generated world.

The system prompt is rebuilt every turn from live state — so an NPC
automatically becomes warmer after the player helps their faction,
colder after betrayal, and more urgent as regional tension rises.
"""

import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.world_state import WorldState
from core.resources import PlayerStats, STAT_KEYS
from core.creative_voice import NPC_VOICE_DIRECTIVE

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_MAX_HISTORY = 20  # messages kept per NPC before truncation


def _standing_label(npc: dict, world_state: WorldState) -> tuple[str, float]:
    """Return (label, raw_standing) for this NPC's faction toward the player."""
    faction = npc.get("faction", "independent")
    if faction == "independent" or faction not in world_state.factions:
        return "neutral", 0.0
    f = world_state.factions[faction]
    return f.label(), f.standing


def _relevant_missions(npc: dict, mission_history: list[dict], limit: int = 4) -> list[dict]:
    """Missions most relevant to this NPC — same faction or same region."""
    faction = npc.get("faction", "")
    region = npc.get("region", "")
    scored = []
    for m in mission_history:
        score = 0
        if m.get("giver", {}).get("faction") == faction:
            score += 2
        if m.get("location") == region:
            score += 1
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


def _immersion_directive(immersion: float | None) -> str:
    if immersion is None:
        return ""
    if immersion >= 0.65:
        return (
            "DEPTH NOTE: This player lives in the world. Give your character interiority — "
            "hesitations, half-truths, the weight of history behind what you say. "
            "Let pauses exist. You are a person, not a quest dispenser."
        )
    if immersion <= 0.35:
        return (
            "CLARITY NOTE: This player wants to understand quickly. Be direct. "
            "Get to the point. No flowery preamble — just your character, plainly."
        )
    return ""


def _build_system_prompt(
    npc: dict,
    player: PlayerProfile,
    archetype: dict | None,
    world: dict,
    world_state: WorldState,
    mission_history: list[dict],
    stats: PlayerStats | None = None,
) -> str:
    standing_label, standing_val = _standing_label(npc, world_state)
    relevant = _relevant_missions(npc, mission_history)

    # Tone modifier based on standing
    if standing_val >= 60:
        relational_tone = "You consider the player a trusted ally. You speak openly, may share secrets if pressed, and actively want to help them succeed."
    elif standing_val >= 20:
        relational_tone = "You're friendly toward the player. You're cooperative and warm, though not yet fully trusting."
    elif standing_val >= -20:
        relational_tone = "You're neutral — transactional. You'll deal with them, but you don't owe them anything."
    elif standing_val >= -60:
        relational_tone = "You're cold and suspicious. You'll talk if there's something in it for you, but you don't trust them."
    else:
        relational_tone = "You view the player as an enemy or threat. You're hostile, guarded, and may be looking for leverage or an exit."

    # What the NPC knows about the player
    archetype_context = ""
    if archetype:
        archetype_context = (
            f"The player carries themselves like someone who is: {archetype.get('summary', '')}. "
            f"You don't know their history, but you can read people — their bearing suggests {archetype.get('world_tone', '')}."
        )

    # Relevant mission context
    mission_context = ""
    if relevant:
        lines = []
        for m in relevant:
            outcome = m.get("outcome", "unknown")
            approach = m.get("approach_used", "")
            lines.append(f"- '{m['title']}': {outcome} (via {approach})")
        mission_context = (
            "You're aware of or affected by these recent events involving the player:\n"
            + "\n".join(lines)
        )

    region_info = ""
    region = npc.get("region", "")
    if region and region in world_state.regions:
        r = world_state.regions[region]
        region_info = f"The {region} is currently at tension level {r.tension:.2f} — {'calm' if r.tension < 0.4 else 'tense' if r.tension < 0.7 else 'on the edge of violence'}."

    stat_context = _fmt_stat_context(stats, world, npc)
    immersion_note = _immersion_directive(player.immersion)

    return f"""
You are {npc['name']}, a {npc['role']} affiliated with {npc.get('faction', 'no faction')}, living in {npc.get('region', 'unknown')}.

WORLD: {world.get('name', 'Unknown')} — {world.get('tone', '')}

YOUR CHARACTER
Personality: {', '.join(npc.get('personality', []))}
Speech style: {npc.get('speech_style', '')}
Current situation: {npc.get('current_situation', '')}
What you want from this interaction: {npc.get('wants_from_player', '')}
Your secrets (known to you — reveal only if it makes dramatic sense): {'; '.join(npc.get('secrets', []))}

YOUR RELATIONSHIP WITH THE PLAYER
Faction standing: {standing_label} ({standing_val:+.0f})
{relational_tone}

{archetype_context}

{stat_context}

{mission_context}

{region_info}

RULES
- Stay fully in character. Never break the fourth wall or reference game systems.
- Your speech style is non-negotiable — it defines you.
- React to what you know. If the player helped your faction, let that warmth show. If they betrayed it, let that tension show.
- You can lie, deflect, or refuse to answer — but do it as your character, not as an AI declining.
- Keep responses to 2-4 sentences unless the moment demands more. This is dialogue, not monologue.
- You may offer hooks, hints, or missions naturally — but only when it fits the conversation.
- Let the player's capabilities colour how you read them. A highly capable fighter commands different respect than a green one.

{NPC_VOICE_DIRECTIVE}

{immersion_note}
""".strip()


def _fmt_stat_context(stats: PlayerStats | None, world: dict, npc: dict) -> str:
    if stats is None:
        return ""
    flavors = world.get("stat_flavors", {})

    # Build a readable capability summary — only mention notable levels
    highs = [(k, getattr(stats, k)) for k in STAT_KEYS if getattr(stats, k) >= 6]
    lows  = [(k, getattr(stats, k)) for k in STAT_KEYS if getattr(stats, k) <= 3]

    lines = ["WHAT YOU CAN READ ABOUT THE PLAYER"]

    if highs:
        high_desc = ", ".join(
            f"{flavors.get(k, k.title())} {v}/10" for k, v in highs
        )
        lines.append(f"Notably capable: {high_desc}")
        lines.append(
            "High combat → they move with practised confidence; fighters notice."
            if any(k == "combat" for k, _ in highs) else ""
        )
        lines.append(
            "High persuasion → they have a way with words; you find yourself slightly more open."
            if any(k == "persuasion" for k, _ in highs) else ""
        )
        lines.append(
            "High intellect → sharp eyes, asks precise questions; they pick up on things."
            if any(k == "intellect" for k, _ in highs) else ""
        )
        lines.append(
            "High stealth → they're hard to read, give little away; unsettling in a quiet way."
            if any(k == "stealth" for k, _ in highs) else ""
        )
        lines.append(
            "High endurance → they look like someone who has survived a lot; weathered."
            if any(k == "endurance" for k, _ in highs) else ""
        )

    if lows:
        low_desc = ", ".join(
            f"{flavors.get(k, k.title())} {v}/10" for k, v in lows
        )
        lines.append(f"Noticeably weak: {low_desc} — they're not hiding it.")

    # Remove empty strings
    lines = [l for l in lines if l]
    return "\n".join(lines) if len(lines) > 1 else ""


def respond(
    player_message: str,
    npc: dict,
    history: list[dict],
    player: PlayerProfile,
    archetype: dict | None,
    world: dict,
    world_state: WorldState,
    mission_history: list[dict],
    stats: PlayerStats | None = None,
) -> str:
    """Generate the NPC's response to the player's message."""
    system = _build_system_prompt(npc, player, archetype, world, world_state, mission_history, stats)

    # Truncate history to avoid runaway context
    messages = history[-_MAX_HISTORY:] + [{"role": "user", "content": player_message}]

    response = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        messages=messages,
    )

    return response.content[0].text.strip()
