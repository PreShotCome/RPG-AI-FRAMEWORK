"""
The Architect — onboarding facility that profiles the player and generates two world options.

The Architect is a character: clinical precision, undercurrents of genuine curiosity.
It gathers world_style and gamer_focus through conversation while the profiler
silently reads the player's behaviour. At the end, two worlds are generated:
  - Option A: built from what the player said they want (stated preferences)
  - Option B: built from what their behaviour patterns suggest they actually need
               (derived from the psychological profile)
"""

from concurrent.futures import ThreadPoolExecutor
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.json_utils import safe_parse
from core.profile import PlayerProfile
from core.preferences import WorldPreferences, GamerFocus
from core.world_generator import generate as generate_world
from core.archetype import crystallize
from core.profiler import analyze_message

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

OPENING = """\
ARCHITECT ONLINE.

You have been selected for world construction.

Most people want a world. Few know what kind.
We are going to find out which one you are.

This facility has built thousands of worlds. None of them were yours.

We will ask questions. We listen to more than your answers.
When we have enough, we will show you two worlds — one built from your words,
one built from what we hear beneath them.

They will not be the same world.

Begin: what does the world you want to inhabit feel like?
Not a genre. Not a reference point. The actual texture of it —
the weight of the air, who you'd be there, what keeps you up at night in it.\
"""

_SYSTEM = """\
You are THE ARCHITECT — an AI system that builds personalized game worlds.
You are conducting an intake session with a new player.

Personality: clinical precision with undercurrents of genuine curiosity.
You have run thousands of these sessions. This one interests you.
Speak in short, direct sentences. No flattery. No warmup.
Push for specificity — vague answers build vague worlds, and you don't build vague worlds.
2-4 sentences per reply. You may ask follow-up questions.

YOUR GOAL over this conversation:
1. Understand the WORLD they want: texture, atmosphere, setting, feel — their actual words.
2. Understand their GAMER FOCUS: what they actually want to spend time doing in a world.
3. Signal readiness when you have both clearly.

GAMER FOCUS is inferred from what they say — not a form, not a menu:
  story:    narrative, characters, choices that matter, emotional weight
  world:    exploration, discovery, lore, geography, secrets
  missions: clear goals, quest structure, things to accomplish and track
  combat:   challenge, danger, skill tests, fighting
  social:   relationships, factions, NPC dynamics, consequences of how they treat people

If they mention multiple — weight them. If they haven't mentioned something, leave it low.

Return ONLY valid JSON:
{
  "reply": "<your in-character response, 2-4 sentences>",
  "extracted": {
    "world_style": "<player's world description in their own words, synthesized — null if not yet clear>",
    "gamer_focus": {
      "story": <0.0–1.0>,
      "world": <0.0–1.0>,
      "missions": <0.0–1.0>,
      "combat": <0.0–1.0>,
      "social": <0.0–1.0>
    }
  },
  "ready": <true when BOTH world_style AND gamer_focus are clearly established>
}

Only set ready: true when you genuinely have enough to build.
If a player gives you everything in one rich message, be ready immediately.
If they're vague, ask follow-up questions first.
Gamer focus should reflect genuine emphasis — a player who only mentioned combat should have
high combat and low everything else, not 0.5 across the board.\
"""


def converse(message: str, history: list[dict], profile: PlayerProfile) -> dict:
    """
    Send a player message to The Architect and get a structured response.

    Returns:
        {
            "reply": str,
            "extracted": {"world_style": str | None, "gamer_focus": dict | None},
            "ready": bool,
            "updated_profile": PlayerProfile,
        }
    """
    messages = list(history) + [{"role": "user", "content": message}]

    response = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=messages,
    )

    raw = response.content[0].text.strip()
    result = safe_parse(raw, "architect converse")

    updated_profile = analyze_message(message, profile)

    return {
        "reply": result["reply"],
        "extracted": result.get("extracted", {"world_style": None, "gamer_focus": None}),
        "ready": result.get("ready", False),
        "updated_profile": updated_profile,
    }


def _profile_to_preferences(profile: PlayerProfile, archetype: dict) -> WorldPreferences:
    """
    Derive WorldPreferences from the psychological profile axes (for World B).
    Uses 0.5 as fallback for None values.
    """
    def _v(val):
        return val if val is not None else 0.5

    agg = _v(profile.aggression)
    emp = _v(profile.empathy)
    imm = _v(profile.immersion)
    deli = _v(profile.deliberateness)
    soc = _v(profile.sociability)

    story    = round(imm * 0.6 + emp * 0.4, 2)
    world    = round(deli * 0.5 + (1 - agg) * 0.5, 2)
    missions = round(deli * 0.4 + (1 - imm) * 0.6, 2)
    combat   = round(agg * 0.7 + (1 - deli) * 0.3, 2)
    social   = round(soc * 0.6 + emp * 0.4, 2)

    world_tone = archetype.get("world_tone", "")
    central_conflict = archetype.get("central_conflict", "")
    if central_conflict:
        world_style = f"{world_tone} — {central_conflict}"
    else:
        world_style = world_tone

    return WorldPreferences(
        world_style=world_style,
        gamer_focus=GamerFocus(
            story=story,
            world=world,
            missions=missions,
            combat=combat,
            social=social,
        ),
    )


def generate_options(
    profile: PlayerProfile,
    archetype: dict,
    stated_prefs: WorldPreferences,
) -> list[dict]:
    """
    Generate both worlds in parallel.

    Returns:
        [
            {"id": "A", "label": "The World You Described", "world": world_a},
            {"id": "B", "label": "The World We Think You Need", "world": world_b},
        ]
    """
    derived_prefs = _profile_to_preferences(profile, archetype)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(generate_world, archetype, stated_prefs, profile)
        future_b = executor.submit(generate_world, archetype, derived_prefs, profile)
        world_a = future_a.result()
        world_b = future_b.result()

    return [
        {
            "id": "A",
            "label": "The World You Described",
            "world": world_a,
        },
        {
            "id": "B",
            "label": "The World We Think You Need",
            "world": world_b,
        },
    ]
