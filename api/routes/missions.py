from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from core import session as sessions
from core.world_state import WorldState, WorldEvent
from core.mission_generator import generate_pool
from core.profiler import analyze_message

router = APIRouter(prefix="/missions", tags=["missions"])

_POOL_SIZE = 4


# ── Request / Response models ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    # Godot can request a specific size; defaults to 4
    pool_size: int = _POOL_SIZE

    @field_validator("pool_size")
    @classmethod
    def valid_size(cls, v: int) -> int:
        if not (1 <= v <= 8):
            raise ValueError("pool_size must be between 1 and 8")
        return v


class CompleteRequest(BaseModel):
    mission_id: str
    outcome: str                      # "success" | "failure" | "partial"
    approach_used: str                # free-text — how the player actually did it
    notes: Optional[str] = None       # optional extra context for profile update

    @field_validator("outcome")
    @classmethod
    def valid_outcome(cls, v: str) -> str:
        if v not in ("success", "failure", "partial"):
            raise ValueError("outcome must be success, failure, or partial")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_world_ready(game_session, session_id: str):
    if game_session.generated_world is None:
        raise HTTPException(
            status_code=400,
            detail="World not generated yet. Call POST /world/{session_id}/generate first.",
        )
    if game_session.archetype is None:
        raise HTTPException(status_code=400, detail="Archetype missing — regenerate the world.")


def _ensure_world_state_seeded(game_session) -> None:
    """Seed WorldState from the generated world the first time missions are touched."""
    if not game_session.world_state.factions and game_session.generated_world:
        game_session.world_state = WorldState.from_generated_world(game_session.generated_world)


def _build_profile_signal(mission: dict, req: CompleteRequest) -> tuple[str, str]:
    """
    Build the (message, context) pair for analyze_message.
    The approach_used is the behavioural signal; context grounds it.
    """
    context = (
        f"Mission '{mission['title']}' ({mission['type']}, {mission.get('difficulty','?')} difficulty). "
        f"Outcome: {req.outcome}."
    )
    if req.notes:
        context += f" {req.notes}"
    return req.approach_used, context


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{session_id}/generate")
def generate_missions(session_id: str, req: GenerateRequest = GenerateRequest()):
    """
    Generate a fresh mission pool for this session.

    Reads the live profile, world state, and mission history — so results
    evolve naturally as the player progresses. Safe to call at any time;
    replaces the current pool.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)
    _require_world_ready(game_session, session_id)
    _ensure_world_state_seeded(game_session)

    pool = generate_pool(
        archetype=game_session.archetype,
        profile=game_session.profile,
        preferences=game_session.preferences,
        world=game_session.generated_world,
        world_state=game_session.world_state,
        history=game_session.mission_history,
        pool_size=req.pool_size,
    )
    game_session.mission_pool = pool

    return {
        "session_id": session_id,
        "pool": pool,
        "world_state": game_session.world_state.summary(),
    }


@router.post("/{session_id}/complete")
def complete_mission(session_id: str, req: CompleteRequest):
    """
    Mark a mission complete and feed the outcome back into the world.

    Three things happen:
      1. World state updates — factions and regions shift per mission's impact values.
      2. Profile updates — the approach used is fed in as a behavioural observation.
      3. Mission moves from pool to history.

    Godot should call POST /missions/{id}/generate after this to get a refreshed pool.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)
    _require_world_ready(game_session, session_id)
    _ensure_world_state_seeded(game_session)

    mission = game_session.find_mission(req.mission_id)
    if mission is None:
        raise HTTPException(
            status_code=404,
            detail=f"Mission {req.mission_id} not found in current pool.",
        )

    # 1. Apply world state changes
    # On failure, invert or dampen the intended faction impacts
    impact_scale = 1.0 if req.outcome == "success" else (-0.5 if req.outcome == "failure" else 0.4)

    event = WorldEvent(
        mission_id=req.mission_id,
        summary=f"{req.outcome.title()}: {mission['title']} ({req.approach_used})",
        faction_impacts={
            name: delta * impact_scale
            for name, delta in mission.get("faction_impact", {}).items()
        },
        region_impacts={
            name: delta * impact_scale
            for name, delta in mission.get("region_tension_impact", {}).items()
        },
    )
    game_session.world_state.apply_event(event)

    # 2. Update the profile with the behavioural signal — same pipeline as NPC dialogue
    message, context = _build_profile_signal(mission, req)
    game_session.profile = analyze_message(message, game_session.profile, context)

    # 3. Move mission to history
    history_entry = {
        **mission,
        "outcome": req.outcome,
        "approach_used": req.approach_used,
        "notes": req.notes,
    }
    game_session.mission_history.append(history_entry)
    game_session.mission_pool = [m for m in game_session.mission_pool if m["id"] != req.mission_id]

    return {
        "session_id": session_id,
        "completed": history_entry,
        "world_state": game_session.world_state.summary(),
        "profile_observations": game_session.profile.observation_count,
        "pool_remaining": len(game_session.mission_pool),
        "suggest_regenerate": len(game_session.mission_pool) <= 1,
    }


@router.get("/{session_id}")
def get_missions(session_id: str):
    """Current mission pool, history summary, and world state."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    return {
        "session_id": session_id,
        "pool": game_session.mission_pool,
        "history_count": len(game_session.mission_history),
        "history": game_session.mission_history,
        "world_state": game_session.world_state.summary(),
        "profile_observations": game_session.profile.observation_count,
    }
