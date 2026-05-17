from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from core import session as sessions
from core.world_state import WorldState
from core.lore_generator import discover, LORE_TYPES, TRIGGERS
from core.input_guard import check

router = APIRouter(prefix="/lore", tags=["lore"])


# ── Request models ─────────────────────────────────────────────────────────────

class DiscoverRequest(BaseModel):
    trigger: str                   # how it was found
    context: str                   # free-text — what the player found or where they are
    region: Optional[str] = None   # region this is rooted in, if any
    faction: Optional[str] = None  # faction this concerns, if any

    @field_validator("trigger")
    @classmethod
    def valid_trigger(cls, v: str) -> str:
        if v not in TRIGGERS:
            raise ValueError(f"trigger must be one of: {', '.join(TRIGGERS)}")
        return v

    @field_validator("context")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("context cannot be empty")
        return v.strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_world(game_session) -> None:
    if game_session.generated_world is None:
        raise HTTPException(
            status_code=400,
            detail="World not generated yet. Call POST /world/{session_id}/generate first.",
        )


def _ensure_seeded(game_session) -> None:
    if not game_session.world_state.factions and game_session.generated_world:
        game_session.world_state = WorldState.from_generated_world(game_session.generated_world)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{session_id}/discover")
def discover_lore(session_id: str, req: DiscoverRequest):
    """
    Trigger a lore discovery.

    Godot calls this when the player finds an artifact, reads a book,
    explores a location, or a mission/NPC reveals structured knowledge.

    Every discovery reads the full existing lore corpus so new entries
    build on — and never contradict — what's already been found.

    If reveals_secret is true in the response, consider surfacing it
    with extra weight in the UI and potentially shifting faction standing
    via the world state endpoints.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)
    _require_world(game_session)
    _ensure_seeded(game_session)

    if game_session.archetype is None:
        raise HTTPException(status_code=400, detail="Archetype missing — regenerate the world.")

    safe_context = check(req.context, "context")

    # Validate region and faction against world if provided
    if req.region:
        world_regions = [r["name"] for r in game_session.generated_world.get("regions", [])]
        if world_regions and req.region not in world_regions:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown region '{req.region}'. World regions: {world_regions}",
            )

    if req.faction:
        world_factions = [f["name"] for f in game_session.generated_world.get("factions", [])]
        if world_factions and req.faction not in world_factions:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown faction '{req.faction}'. World factions: {world_factions}",
            )

    entry = discover(
        trigger=req.trigger,
        context=safe_context,
        world=game_session.generated_world,
        world_state=game_session.world_state,
        profile=game_session.profile,
        preferences=game_session.preferences,
        archetype=game_session.archetype,
        lore_discovered=game_session.lore_discovered,
        region=req.region or "",
        faction=req.faction or "",
    )

    game_session.lore_discovered.append(entry)

    return {
        "session_id": session_id,
        "entry": entry,
        "total_discovered": len(game_session.lore_discovered),
    }


@router.get("/{session_id}")
def get_lore(session_id: str, lore_type: Optional[str] = None, faction: Optional[str] = None):
    """
    All discovered lore, optionally filtered by type or faction.

    Useful for Godot to populate a codex/journal UI.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    if lore_type and lore_type not in LORE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"lore_type must be one of: {', '.join(LORE_TYPES)}",
        )

    game_session = sessions.get(session_id)
    entries = game_session.lore_discovered

    if lore_type:
        entries = [e for e in entries if e.get("type") == lore_type]
    if faction:
        entries = [e for e in entries if e.get("faction") == faction]

    return {
        "session_id": session_id,
        "total": len(game_session.lore_discovered),
        "filtered": len(entries),
        "entries": entries,
    }


@router.get("/{session_id}/{lore_id}")
def get_lore_entry(session_id: str, lore_id: str):
    """Fetch a single lore entry by id."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)
    entry = next((e for e in game_session.lore_discovered if e["id"] == lore_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Lore entry {lore_id} not found")

    # Surface connected entries for Godot to link in the codex
    connected = [
        e for e in game_session.lore_discovered
        if e["id"] in entry.get("connections", [])
        or lore_id in e.get("connections", [])
    ]

    return {
        "session_id": session_id,
        "entry": entry,
        "connected_entries": connected,
    }
