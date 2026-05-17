"""
Safe JSON parsing for Claude responses.

All generators use this instead of bare json.loads so a malformed
Claude response raises a clear RuntimeError rather than crashing with
a JSONDecodeError that propagates as an unhandled 500.
"""

import json
import re


def safe_parse(text: str, context: str = "") -> dict | list:
    """
    Parse JSON from a Claude response text block.

    Strips accidental markdown fences if present (rare but possible).
    Raises RuntimeError with context on failure — routes catch this
    and return 500 with a clean message.
    """
    text = text.strip()

    # Strip ```json ... ``` fences if Claude added them despite instructions
    fenced = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        snippet = text[:200].replace("\n", " ")
        label = f" ({context})" if context else ""
        raise RuntimeError(
            f"Claude returned malformed JSON{label}: {e}. "
            f"Response started with: {snippet!r}"
        )
