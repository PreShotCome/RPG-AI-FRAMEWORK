"""
World generator: takes a player's archetype + stated preferences and
builds a complete, personalized game world.

Inputs:
  - archetype   (from core/archetype.py — who the player IS)
  - preferences (from core/preferences.py — what world/game they WANT)
  - profile     (the raw 9-axis profile — for fine-tuning faction/conflict design)

Output: a world dict that Godot uses to populate the game.
"""

import json
from core.json_utils import safe_parse
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.preferences import WorldPreferences
from core.creative_voice import WONDER_DIRECTIVE

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = (
    "You are a world architect for an AI-powered RPG. You generate complete,\n"
    "personalized game worlds that match both who the player is psychologically\n"
    "and what kind of game they want to play.\n\n"
    + WONDER_DIRECTIVE
    + "\n\n"
    "Return ONLY valid JSON — no explanation, no markdown fences.\n\n"
    "The world must feel like it was made specifically for this player.\n"
    "Factions, conflicts, and power structures should reflect their moral/law alignment.\n"
    "Tone and atmosphere should match their stated world style exactly.\n"
    "Gameplay emphasis should foreground what they said they care about most.\n\n"
    "Schema:\n"
    "{\n"
    '  "name": "<evocative world name>",\n'
    '  "tagline": "<one sentence that captures the world\'s essence>",\n'
    '  "setting": "<2–3 paragraph description of the world — its history, current state, and feel>",\n'
    '  "tone": "<emotional register — e.g. \'gritty and desperate\', \'mythic and awe-inspiring\', \'paranoid noir\'>",\n'
    "\n"
    '  "regions": [\n'
    "    {\n"
    '      "name": "<region name>",\n'
    '      "description": "<what this place is and feels like>",\n'
    '      "hook": "<why the player would go here>",\n'
    '      "dominant_theme": "<one of: justice, revenge, power, mystery, survival, redemption, loyalty, freedom, knowledge, sacrifice>"\n'
    "    }\n"
    "  ],\n"
    "\n"
    '  "factions": [\n'
    "    {\n"
    '      "name": "<faction name>",\n'
    '      "description": "<who they are and what they want>",\n'
    '      "alignment": "<lawful|neutral|chaotic> <good|neutral|evil>",\n'
    '      "player_relationship": "<how this faction relates to a player with the given profile — ally, antagonist, complex>",\n'
    '      "hook": "<why the player would care about this faction>"\n'
    "    }\n"
    "  ],\n"
    "\n"
    '  "central_conflict": {\n'
    '    "description": "<the main tension driving the world>",\n'
    '    "stakes": "<what happens if this conflict resolves one way or another>",\n'
    '    "player_role": "<how someone with this archetype naturally fits into this conflict>"\n'
    "  },\n"
    "\n"
    '  "gameplay_emphasis": {\n'
    '    "primary": "<what the world rewards most — exploration, story choices, combat, social manipulation, etc.>",\n'
    '    "secondary": "<secondary emphasis>",\n'
    '    "de_emphasized": "<what is intentionally sparse — not every world needs everything>"\n'
    "  },\n"
    "\n"
    '  "starting_location": {\n'
    '    "name": "<name>",\n'
    '    "description": "<where the player begins, post-training-world>",\n'
    '    "immediate_hook": "<the first thing that pulls them in>"\n'
    "  },\n"
    "\n"
    '  "currency": {\n'
    '    "name": "<what this world calls its primary currency — specific to the setting>",\n'
    '    "symbol": "<1-3 char shorthand, e.g. \'G\', \'cr\', \'₿\', \'\xa5\'>",\n'
    '    "lore": "<one sentence: origin or cultural meaning of this currency>"\n'
    "  },\n"
    "\n"
    '  "stat_flavors": {\n'
    '    "combat":     "<world-specific display name for combat skill, e.g. \'Muscle\', \'Warfare\', \'Heat\'>",\n'
    '    "stealth":    "<e.g. \'Shadow\', \'Ghost\', \'Quiet\'>",\n'
    '    "persuasion": "<e.g. \'Silver Tongue\', \'Influence\', \'Pull\'>",\n'
    '    "intellect":  "<e.g. \'Head\', \'Lore\', \'Circuit\'>",\n'
    '    "endurance":  "<e.g. \'Grit\', \'Vitality\', \'Iron\'>",\n'
    '    "luck":       "<e.g. \'Fortune\', \'Fate\', \'Chance\'>"\n'
    "  }\n"
    "}\n\n"
    "Generate exactly 3 regions and exactly 3 factions.\n"
)


def generate(
    archetype: dict,
    preferences: WorldPreferences,
    profile: PlayerProfile,
) -> dict:
    """
    Generate a complete world. Uses extended thinking for coherence.
    Returns the world dict.
    """
    focus = preferences.gamer_focus.normalized()
    top_focus = preferences.gamer_focus.top(2)

    prompt = f"""
PLAYER ARCHETYPE
Name: {archetype['name']}
Summary: {archetype['summary']}
World tone seed: {archetype['world_tone']}
Central conflict seed: {archetype['central_conflict']}
Motifs: {', '.join(archetype['motifs'])}

PSYCHOLOGICAL PROFILE (silent — player does not know these scores)
Aggression:     {_fmt(profile.aggression)}   (0=avoidant, 1=combative)
Morality:       {_fmt(profile.morality)}   (0=selfish, 1=altruistic)
Lawfulness:     {_fmt(profile.lawfulness)}   (0=chaotic, 1=lawful)
Empathy:        {_fmt(profile.empathy)}   (0=blunt, 1=warm)
Deliberateness: {_fmt(profile.deliberateness)}   (0=impulsive, 1=cautious)
Sociability:    {_fmt(profile.sociability)}   (0=lone wolf, 1=leader)
Deference:      {_fmt(profile.deference)}   (0=defiant, 1=deferential)
Top themes:     {', '.join(profile.top_themes())}

PLAYER-STATED PREFERENCES
World style (their exact words): "{preferences.world_style}"

What kind of gamer they are (normalized weights):
  Story / narrative:    {focus['story']:.0%}
  World / exploration:  {focus['world']:.0%}
  Missions / quests:    {focus['missions']:.0%}
  Combat / action:      {focus['combat']:.0%}
  Social / roleplay:    {focus['social']:.0%}
Primary interest: {top_focus[0]}
Secondary interest: {top_focus[1]}

INSTRUCTIONS
- The world setting MUST match the player's stated style description above.
  If they said "1920s prohibition city with secret magic", build that —
  not a generic fantasy world with a noir coat of paint.
- The factions and conflict should reflect their moral/law profile.
  A lawful-good player needs oppression to fight from within.
  A chaotic-evil player needs power structures to dismantle or exploit.
- Weight the world's content toward what the player said they care about.
  Story-heavy player → rich NPC backstories, moral dilemmas everywhere.
  Combat player → territorial conflicts, dangerous traversal, skill gates.
  World/exploration player → mysteries, hidden lore, geography that rewards curiosity.
  Social player → political webs, NPCs with competing agendas, relationship consequences.
  Mission player → clear faction bounties, visible quest hooks, layered objectives.
- IMMERSION DEPTH ({_fmt(profile.immersion)} — 0=gamey, 1=deep roleplayer):
  High immersion (≥0.65) → make the world feel lived-in and internally consistent.
    Every faction has a believable history. Regions have texture beyond function.
    The setting description should read like prose a novelist would write about a real place.
    Currency has cultural meaning. Factions have internal contradictions.
  Low immersion (≤0.35) → keep it clean and legible.
    Clear allegiances, obvious hooks, practical descriptions over atmospheric ones.
    Players want to know what to do, not what it smells like.
  Mid-range → balance atmosphere with clarity.
- The archetype motifs should appear as recurring symbols in the world.
""".strip()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "enabled", "budget_tokens": 5000},
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            return safe_parse(block.text, "world generation")

    raise RuntimeError("Claude returned no text block during world generation.")


def _fmt(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else "unknown"
