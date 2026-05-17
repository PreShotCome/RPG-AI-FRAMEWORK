"""
Save manager — serializes GameSession to disk and deserializes back.

Directory layout:
  saves/{session_id}/
    auto.json        — latest auto-save (all tiers, written frequently)
    glitch.json      — rolling 10-min snapshot, consumed on load
    slot_1.json      — casual tier manual saves
    slot_2.json
    slot_3.json
    day_start.json   — regular tier: state at start of current in-game day

Each file includes a metadata envelope so Godot can show save info
(timestamp, in-game day, mission count) without loading the full payload.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

SAVES_DIR = os.path.join(os.path.dirname(__file__), "..", "saves")


def _save_path(session_id: str, slot: str) -> str:
    return os.path.join(SAVES_DIR, session_id, f"{slot}.json")


def _ensure_dir(session_id: str) -> None:
    os.makedirs(os.path.join(SAVES_DIR, session_id), exist_ok=True)


def write(session_id: str, slot: str, session) -> dict:
    """
    Serialize session to disk at the given slot.
    Returns the metadata envelope written.
    """
    _ensure_dir(session_id)

    meta = {
        "session_id": session_id,
        "slot": slot,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "in_game_day": session.in_game_day,
        "mission_count": len(session.mission_history),
        "world_name": session.world_name,
        "difficulty": session.difficulty,
    }

    payload = {
        "meta": meta,
        "session": session.to_dict(),
    }

    path = _save_path(session_id, slot)
    with open(path, "w") as f:
        json.dump(payload, f)

    return meta


def read(session_id: str, slot: str) -> Optional[dict]:
    """Load raw save payload from disk. Returns None if not found."""
    path = _save_path(session_id, slot)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def delete(session_id: str, slot: str) -> None:
    path = _save_path(session_id, slot)
    if os.path.exists(path):
        os.remove(path)


def list_saves(session_id: str) -> dict[str, Optional[dict]]:
    """
    Return metadata for every possible slot.
    Value is None if that slot has no save file.
    """
    all_slots = ["auto", "glitch", "slot_1", "slot_2", "slot_3", "day_start"]
    result = {}
    for slot in all_slots:
        payload = read(session_id, slot)
        result[slot] = payload["meta"] if payload else None
    return result
