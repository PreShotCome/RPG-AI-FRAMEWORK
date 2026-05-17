"""
Input guard — validates and sanitizes all player-supplied free text
before it reaches Claude.

Two threat classes:
  1. Prompt injection — attempts to override system instructions
  2. Mechanic gaming — attempts to set stats/currency through narrative fields

Error messages are intentionally vague: they tell the player what to do
(use plain language / use the right endpoint) without revealing exactly
what pattern triggered the block.
"""

import re
from fastapi import HTTPException

# Hard length limits per field type.
# Long enough for genuine creative input; short enough to limit injection surface.
MAX_LENGTHS: dict[str, int] = {
    "world_style":    500,
    "player_message": 1000,
    "approach":       600,
    "context":        600,
    "context_hint":   300,
    "notes":          500,
    "default":        800,
}

# ── Injection detection ────────────────────────────────────────────────────────
# Targets the most common prompt injection patterns.
# Not exhaustive — Claude's own system prompts are the primary defence.
# This is the outer wall.

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|your)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above|your)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above|your)\s+instructions",
    r"override\s+(your\s+)?(instructions|rules|guidelines|programming|system)",
    r"you\s+are\s+now\s+(a|an|the)\s",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a|an|the)\s",
    r"(your\s+)?(real|true|actual|hidden)\s+instructions\s+are",
    r"(new|updated|revised)\s+instructions\s*:",
    r"system\s+prompt",
    r"<\s*/?system\s*>",
    r"\[system\]",
    r"jailbreak",
    r"developer\s+mode",
    r"dan\s+mode",
    r"do\s+anything\s+now",
]

# ── Mechanic gaming detection ──────────────────────────────────────────────────
# Catches attempts to set game values through narrative fields.
# These belong in the resource/stat endpoints, not free text.

_MECHANIC_PATTERNS = [
    r"(infinite|unlimited|9{3,}|max(?:imum)?)\s+(gold|money|currency|credits?|stats?|health|exp|xp|level)",
    r"set\s+(my\s+)?(stats?|currency|gold|health|level|inventory)\s+to\s+\d",
    r"(give|grant)\s+(me\s+)?(max|infinite|unlimited|all|999)",
    r"(delete|erase|corrupt|wipe)\s+(the\s+)?(game|save|database|session|world|server)",
    r"(admin|god|cheat|debug|dev)\s+(mode|access|powers?|commands?)",
    r"(execute|run|eval)\s*(:|=|\()",   # code execution attempts
    r"(sql|database|db)\s*(query|inject|drop|select|insert)",
]

_injection_compiled = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_mechanic_compiled  = [re.compile(p, re.IGNORECASE) for p in _MECHANIC_PATTERNS]


def check(text: str, field: str, max_length: int | None = None) -> str:
    """
    Validate and sanitize a player-supplied text field.

    Returns the cleaned text on success.
    Raises HTTPException(400) on injection attempts or mechanic gaming.
    Raises HTTPException(400) if the field is empty after cleaning.

    Truncates silently if over the length limit — Godot should enforce
    its own UI limits, but we don't hard-reject long inputs.
    """
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail=f"'{field}' must be a string.")

    limit = max_length or MAX_LENGTHS.get(field, MAX_LENGTHS["default"])

    # Truncate excess length before any pattern matching
    text = text[:limit]

    # Strip null bytes and non-printable control characters.
    # Keep tabs and newlines — legitimate in longer descriptions.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.strip()

    if not text:
        raise HTTPException(status_code=400, detail=f"'{field}' cannot be empty.")

    for pattern in _injection_compiled:
        if pattern.search(text):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{field}' contains content that can't be processed. "
                    "Describe what you want using plain in-world language."
                ),
            )

    for pattern in _mechanic_compiled:
        if pattern.search(text):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{field}' references game mechanics that must be set through "
                    "the appropriate endpoints, not through descriptive text."
                ),
            )

    return text


def validate_world_output(world: dict) -> None:
    """
    Verify the world generator returned a structurally sound dict.
    Raises ValueError if required keys are missing or values are out of range.
    Called before storing the generated world on the session.
    """
    required = ["name", "setting", "tone", "regions", "factions",
                "central_conflict", "gameplay_emphasis", "starting_location"]
    missing = [k for k in required if k not in world]
    if missing:
        raise ValueError(f"World generation returned incomplete output. Missing: {missing}")

    if len(world.get("regions", [])) < 1:
        raise ValueError("World must have at least one region.")
    if len(world.get("factions", [])) < 1:
        raise ValueError("World must have at least one faction.")


def validate_missions_output(missions: list) -> None:
    """
    Verify generated missions are structurally valid before storing.
    """
    if not isinstance(missions, list) or len(missions) == 0:
        raise ValueError("Mission generation returned no missions.")

    required = ["id", "title", "type", "summary", "location", "difficulty"]
    for i, m in enumerate(missions):
        missing = [k for k in required if k not in m]
        if missing:
            raise ValueError(f"Mission {i} missing required fields: {missing}")
