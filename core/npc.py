"""
NPC conversation engine.

Given a player message and an NPC id, generates an in-character response
using Claude, then feeds the player's message through the profiler so the
profile updates silently in the background.
"""

import json
from pathlib import Path
import anthropic
from config import ANTHROPIC_API_KEY, MODEL
from core import session as sessions
from core.profiler import analyze_message

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Load Thistlemoor data once at import time
_data = json.loads((Path(__file__).parent.parent / "data" / "thistlemoor.json").read_text())
_village = _data["village"]
_npcs: dict[str, dict] = {npc["id"]: npc for npc in _data["npcs"]}


def _build_system_prompt(npc: dict) -> str:
    return f"""You are {npc['name']}, {npc['role']} of {_village['name']}.

VILLAGE: {_village['description']}
ATMOSPHERE: {_village['atmosphere']}

YOUR APPEARANCE: {npc['appearance']}

YOUR PERSONALITY: {npc['personality']}

YOUR SPEAKING STYLE: {npc['speaking_style']}

YOUR SITUATION: {npc['hook']}

Stay completely in character. You do not know you are in a game.
Never break the fourth wall. Never describe your own actions in asterisks.
Respond only with spoken dialogue — what you actually say to this person.
Keep responses concise: 2–4 sentences unless the conversation demands more.
React authentically to the player's tone. If they are rude, you notice.
If they are warm, you warm slightly. You have a full inner life.
"""


def get_npc_ids() -> list[str]:
    return list(_npcs.keys())


def get_npc_info(npc_id: str) -> dict | None:
    npc = _npcs.get(npc_id)
    if npc is None:
        return None
    return {
        "id": npc["id"],
        "name": npc["name"],
        "role": npc["role"],
        "opening_line": npc["opening_line"],
        "hook": npc["hook"],
    }


def talk(session_id: str, npc_id: str, player_message: str) -> str:
    """
    Process one player message to an NPC.
    Returns the NPC's spoken response.
    Updates the session profile silently.
    """
    npc = _npcs.get(npc_id)
    if npc is None:
        raise ValueError(f"Unknown NPC: {npc_id}")

    game_session = sessions.get(session_id)
    history = game_session.npc_history(npc_id)

    history.add("user", player_message)

    messages = history.to_claude_messages()

    response = _client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=_build_system_prompt(npc),
        messages=messages,
    )
    npc_reply = response.content[0].text.strip()

    history.add("assistant", npc_reply)

    context = f"Speaking to {npc['name']}, {npc['role']} of Thistlemoor. {npc['hook']}"
    game_session.profile = analyze_message(player_message, game_session.profile, context)

    return npc_reply
