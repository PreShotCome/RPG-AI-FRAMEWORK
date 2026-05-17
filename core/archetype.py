"""
Crystallize a completed PlayerProfile into a named personal archetype.
Called once at level 10 — the output seeds all downstream world generation.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile
from core.json_utils import safe_parse

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """
You are a narrative architect for an AI-powered RPG. Given a player's
psychological profile, synthesize a single poetic archetype that captures
their essence. This archetype will be used to generate an entire fantasy world.

Return ONLY valid JSON — no explanation, no markdown fences.

Schema:
{
  "name":        "<poetic title, 2–4 words, e.g. 'The Reluctant Protector'>",
  "summary":     "<1–2 sentence description of who this person is>",
  "world_tone":  "<the emotional register of the world — e.g. 'gritty and oppressed' or 'mythic and awe-inspiring'>",
  "central_conflict": "<the type of conflict that will resonate most — e.g. 'corruption of a once-just order'>",
  "motifs":      ["<3 symbolic motifs to weave into the world, e.g. 'crumbling institutions', 'reluctant heroes'>"]
}
"""


def crystallize(profile: PlayerProfile, force: bool = False) -> dict:
    """
    Takes a completed profile and returns the archetype dict.
    Raises ValueError if the profile isn't ready yet (unless force=True).
    """
    if not force and not profile.is_ready():
        raise ValueError("Profile has insufficient observations to crystallize.")

    profile_summary = f"""
Aggression:     {_fmt(profile.aggression)}  (0=avoidant, 1=combative)
Morality:       {_fmt(profile.morality)}  (0=selfish, 1=altruistic)
Lawfulness:     {_fmt(profile.lawfulness)}  (0=chaotic, 1=lawful)
Empathy:        {_fmt(profile.empathy)}  (0=blunt, 1=warm)
Immersion:      {_fmt(profile.immersion)}  (0=gamey, 1=deep roleplayer)
Deliberateness: {_fmt(profile.deliberateness)}  (0=impulsive, 1=cautious)
Sociability:    {_fmt(profile.sociability)}  (0=lone wolf, 1=leader)
Deference:      {_fmt(profile.deference)}  (0=defiant, 1=deferential)
Top themes:     {', '.join(profile.top_themes())}
Observations:   {profile.observation_count}
""".strip()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        thinking={"type": "enabled", "budget_tokens": 2000},
        system=_SYSTEM,
        messages=[{"role": "user", "content": profile_summary}],
    )

    for block in response.content:
        if block.type == "text":
            return safe_parse(block.text, "archetype crystallization")

    raise RuntimeError("Claude returned no text block for archetype crystallization.")


def _fmt(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else "unknown"
