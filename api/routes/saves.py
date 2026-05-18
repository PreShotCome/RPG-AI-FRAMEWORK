from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from core import session as sessions
from core.session import DIFFICULTIES, LOAD_PERMISSIONS, SAVE_PERMISSIONS, GameSession
from core import save_manager

router = APIRouter(prefix="/saves", tags=["saves"])

MANUAL_SLOTS = {"slot_1", "slot_2", "slot_3"}
ALL_SLOTS = {"auto", "glitch", "slot_1", "slot_2", "slot_3", "day_start"}


# ── Request models ─────────────────────────────────────────────────────────────

class ConfigureRequest(BaseModel):
    difficulty: str
    world_name: str = ""

    @field_validator("difficulty")
    @classmethod
    def valid_difficulty(cls, v: str) -> str:
        if v not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of: {', '.join(DIFFICULTIES)}")
        return v


class SaveRequest(BaseModel):
    slot: str = "auto"

    @field_validator("slot")
    @classmethod
    def valid_slot(cls, v: str) -> str:
        if v not in ALL_SLOTS:
            raise ValueError(f"slot must be one of: {', '.join(sorted(ALL_SLOTS))}")
        return v


class LoadRequest(BaseModel):
    slot: str

    @field_validator("slot")
    @classmethod
    def valid_slot(cls, v: str) -> str:
        if v not in ALL_SLOTS:
            raise ValueError(f"slot must be one of: {', '.join(sorted(ALL_SLOTS))}")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(session_id: str):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions.get(session_id)


def _check_save_permission(difficulty: str, slot: str) -> None:
    if slot not in SAVE_PERMISSIONS[difficulty]:
        allowed = sorted(SAVE_PERMISSIONS[difficulty])
        raise HTTPException(
            status_code=403,
            detail=f"'{difficulty}' mode cannot save to '{slot}'. Allowed: {allowed}",
        )


def _check_load_permission(difficulty: str, slot: str) -> None:
    if slot not in LOAD_PERMISSIONS[difficulty]:
        allowed = sorted(LOAD_PERMISSIONS[difficulty])
        raise HTTPException(
            status_code=403,
            detail=f"'{difficulty}' mode cannot load from '{slot}'. Allowed: {allowed}",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{session_id}/configure")
def configure(session_id: str, req: ConfigureRequest):
    """
    Set difficulty tier and world name for this session.
    Call once after world generation, before the first save.
    """
    game_session = _get_session(session_id)
    game_session.difficulty = req.difficulty
    if req.world_name:
        game_session.world_name = req.world_name
    return {
        "session_id": session_id,
        "difficulty": game_session.difficulty,
        "world_name": game_session.world_name,
        "load_permissions": sorted(LOAD_PERMISSIONS[req.difficulty]),
        "save_permissions": sorted(SAVE_PERMISSIONS[req.difficulty]),
    }


@router.post("/{session_id}")
def save(session_id: str, req: SaveRequest = SaveRequest()):
    """
    Save the current session state to a slot.

    Godot calls this:
      - Every X minutes with slot="auto"
      - Every 10 minutes with slot="glitch" (the safety-net snapshot)
      - When a casual player manually saves with slot="slot_1/2/3"
      - When advance_day fires with slot="day_start" (handled automatically there)

    Tier restrictions are enforced — regular/hardcore players cannot write
    to manual slots.
    """
    game_session = _get_session(session_id)
    _check_save_permission(game_session.difficulty, req.slot)

    meta = save_manager.write(session_id, req.slot, game_session)
    return {"saved": True, "meta": meta}


@router.post("/{session_id}/load")
def load(session_id: str, req: LoadRequest):
    """
    Load a save slot into the active session.

    Tier restrictions apply — a hardcore player can only load the glitch save.
    The glitch save is deleted after loading to prevent chain-reloading.
    """
    game_session = _get_session(session_id)
    _check_load_permission(game_session.difficulty, req.slot)

    payload = save_manager.read(session_id, req.slot)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"No save found in slot '{req.slot}'.",
        )

    restored = GameSession.from_dict(payload["session"])

    # Replace the live session
    sessions._store[session_id] = restored

    # Glitch save is consumed on load — prevents repeated rollbacks
    if req.slot == "glitch":
        save_manager.delete(session_id, "glitch")

    return {
        "loaded": True,
        "slot": req.slot,
        "meta": payload["meta"],
        "glitch_consumed": req.slot == "glitch",
    }


@router.post("/{session_id}/advance-day")
def advance_day(session_id: str):
    """
    Godot calls this when an in-game day ends.

    Increments the day counter and, for regular tier, writes a day_start
    snapshot — the one restore point regular players get.
    """
    game_session = _get_session(session_id)
    game_session.in_game_day += 1

    day_save_meta = None
    if game_session.difficulty == "regular":
        # Overwrite the single day_start slot — only current day, not history
        day_save_meta = save_manager.write(session_id, "day_start", game_session)

    # Always write auto-save on day advance
    auto_meta = save_manager.write(session_id, "auto", game_session)

    return {
        "session_id": session_id,
        "in_game_day": game_session.in_game_day,
        "day_start_saved": day_save_meta is not None,
        "auto_saved": True,
        "meta": day_save_meta or auto_meta,
    }


@router.get("/{session_id}")
def list_saves(session_id: str):
    """
    List all save slots and their metadata.
    Null means that slot has no file yet.
    """
    game_session = _get_session(session_id)
    saves = save_manager.list_saves(session_id)

    return {
        "session_id": session_id,
        "difficulty": game_session.difficulty,
        "in_game_day": game_session.in_game_day,
        "world_name": game_session.world_name,
        "load_permissions": sorted(LOAD_PERMISSIONS[game_session.difficulty]),
        "save_permissions": sorted(SAVE_PERMISSIONS[game_session.difficulty]),
        "saves": saves,
    }
