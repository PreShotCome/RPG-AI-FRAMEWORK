"""
ProfileAnalyzer: sends a player's message to Claude and gets back
a structured update to apply to the PlayerProfile.

This is the piece that will eventually be replaced by (or forwarded to)
the Brain on Render. For now it calls Claude directly.
"""

import json
from core.json_utils import safe_parse
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core.profile import PlayerProfile

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Themes the engine tracks — Brain can expand this list later
KNOWN_THEMES = [
    "justice", "revenge", "power", "mystery", "survival",
    "redemption", "loyalty", "freedom", "knowledge", "sacrifice",
]

_SYSTEM = """
You are a silent psychological profiler for an RPG. Your job is to analyze
a single player message and return a JSON object estimating what it reveals
about the player across these axes.

Return ONLY valid JSON — no explanation, no markdown fences.

Schema:
{
  "aggression":      <0.0–1.0 or null>,   // 0=avoidant, 1=combative
  "morality":        <0.0–1.0 or null>,   // 0=selfish/evil, 1=altruistic/good
  "lawfulness":      <0.0–1.0 or null>,   // 0=chaotic, 1=lawful
  "empathy":         <0.0–1.0 or null>,   // 0=blunt, 1=warm/empathetic
  "immersion":       <0.0–1.0 or null>,   // 0=gamey, 1=deep roleplayer
  "deliberateness":  <0.0–1.0 or null>,   // 0=impulsive, 1=cautious
  "sociability":     <0.0–1.0 or null>,   // 0=lone wolf, 1=social leader
  "deference":       <0.0–1.0 or null>,   // 0=defiant, 1=deferential
  "themes":          { "<theme>": <0.0–1.0> }  // only themes clearly signaled
}

Return null for any axis you cannot confidently read from this single message.
Only include themes from this list: """ + json.dumps(KNOWN_THEMES) + """
Only include a theme if the message meaningfully signals it.
"""


def _weighted_average(current: float | None, new_value: float, count: int) -> float:
    """Blend a new observation into a running average, giving newer data slightly more weight."""
    if current is None:
        return new_value
    # exponential moving average — recent observations count more
    alpha = max(0.2, 1.0 / (count + 1))
    return current * (1 - alpha) + new_value * alpha


def analyze_message(message: str, profile: PlayerProfile, context: str = "") -> PlayerProfile:
    """
    Analyze a single player message and return an updated PlayerProfile.
    Does NOT mutate the input — returns a new profile.
    """
    prompt = message
    if context:
        prompt = f"[Context: {context}]\n\nPlayer said: {message}"

    response = _client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    data = safe_parse(raw, "profile analysis")

    count = profile.observation_count + 1
    updated = PlayerProfile(
        observation_count=count,
        theme_weights=dict(profile.theme_weights),
    )

    scalar_axes = [
        "aggression", "morality", "lawfulness", "empathy",
        "immersion", "deliberateness", "sociability", "deference",
    ]
    for axis in scalar_axes:
        current = getattr(profile, axis)
        new_val = data.get(axis)
        if new_val is not None:
            setattr(updated, axis, _weighted_average(current, float(new_val), count))
        else:
            setattr(updated, axis, current)

    for theme, weight in (data.get("themes") or {}).items():
        if theme in KNOWN_THEMES:
            prev = updated.theme_weights.get(theme, 0.0)
            updated.theme_weights[theme] = _weighted_average(prev, float(weight), count)

    return updated
