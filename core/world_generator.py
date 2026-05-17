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
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.preferences import WorldPreferences

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """
You are a world architect for an AI-powered RPG. You generate complete,
personalized game worlds that match both who the player is psychologically
and what kind of game they want to play.

Return ONLY valid JSON — no explanation, no markdown fences.

The world must feel like it was made specifically for this player.
Factions, conflicts, and power structures should reflect their moral/law alignment.
Tone and atmosphere should match their stated world style exactly.
Gameplay emphasis should foreground what they said they care about most.

Schema:
{
  "name": "<evocative world name>",
  "tagline": "<one sentence that captures the world's essence>",
  "setting": "<2–3 paragraph description of the world — its history, current state, and feel>",
  "tone": "<emotional register — e.g. 'gritty and desperate', 'mythic and awe-inspiring', 'paranoid noir'>",

  "regions": [
    {
      "name": "<region name>",
      "description": "<what this place is and feels like>",
      "hook": "<why the player would go here>",
      "dominant_theme": "<one of: justice, revenge, power, mystery, survival, redemption, loyalty, freedom, knowledge, sacrifice>"
    }
  ],

  "factions": [
    {
      "name": "<faction name>",
      "description": "<who they are and what they want>",
      "alignment": "<lawful|neutral|chaotic> <good|neutral|evil>",
      "player_relationship": "<how this faction relates to a player with the given profile — ally, antagonist, complex>",
      "hook": "<why the player would care about this faction>"
    }
  ],

  "central_conflict": {
    "description": "<the main tension driving the world>",
    "stakes": "<what happens if this conflict resolves one way or another>",
    "player_role": "<how someone with this archetype naturally fits into this conflict>"
  },

  "gameplay_emphasis": {
    "primary": "<what the world rewards most — exploration, story choices, combat, social manipulation, etc.>",
    "secondary": "<secondary emphasis>",
    "de_emphasized": "<what is intentionally sparse — not every world needs everything>"
  },

  "starting_location": {
    "name": "<name>",
    "description": "<where the player begins, post-training-world>",
    "immediate_hook": "<the first thing that pulls them in>"
  }
}

Generate exactly 3 regions and exactly 3 factions.
"""


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
            return json.loads(block.text.strip())

    raise RuntimeError("Claude returned no text block during world generation.")


def _fmt(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else "unknown"
