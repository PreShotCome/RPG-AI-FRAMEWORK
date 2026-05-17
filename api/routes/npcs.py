from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from core import session as sessions
from core.world_state import WorldState
from core.npc_generator import spawn, NPC_ROLES
from core.npc_dialogue import respond
from core.profiler import analyze_message
from core.input_guard import check
from api.rate_limit import check_rate_limit, record_api_call

router = APIRouter(prefix="/npcs", tags=["npcs"])


# ── Request models ─────────────────────────────────────────────────────────────

class SpawnRequest(BaseModel):
    role: str
    faction: str = "independent"
    region: str = ""
    context_hint: str = ""

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in NPC_ROLES:
            raise ValueError(f"role must be one of: {', '.join(NPC_ROLES)}")
        return v


class TalkRequest(BaseModel):
    message: str
    update_profile: bool = True  # set False if you want pure dialogue with no profiling

    @field_validator("message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be empty")
        return v.strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_world(game_session, session_id: str) -> None:
    if game_session.generated_world is None:
        raise HTTPException(
            status_code=400,
            detail="World not generated yet. Call POST /world/{session_id}/generate first.",
        )


def _ensure_world_state_seeded(game_session) -> None:
    if not game_session.world_state.factions and game_session.generated_world:
        game_session.world_state = WorldState.from_generated_world(game_session.generated_world)


def _standing_for(npc: dict, game_session) -> dict:
    faction = npc.get("faction", "independent")
    if faction == "independent" or faction not in game_session.world_state.factions:
        return {"faction": faction, "label": "neutral", "value": 0.0}
    f = game_session.world_state.factions[faction]
    return {"faction": faction, "label": f.label(), "value": round(f.standing, 1)}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{session_id}/spawn")
def spawn_npc(session_id: str, req: SpawnRequest):
    """
    Generate and register a new NPC for this session.

    Godot calls this when it needs a character — for a mission giver,
    a shopkeeper, a named encounter, etc. The NPC is stored on the session
    and referenced by id in subsequent /talk calls.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    game_session = sessions.get(session_id)
    _require_world(game_session, session_id)
    _ensure_world_state_seeded(game_session)

    # Validate faction and region against the world
    world = game_session.generated_world
    world_factions = [f["name"] for f in world.get("factions", [])]
    world_regions = [r["name"] for r in world.get("regions", [])]

    faction = req.faction
    if faction != "independent" and world_factions and faction not in world_factions:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown faction '{faction}'. World factions: {world_factions}",
        )

    region = req.region
    if region and world_regions and region not in world_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region '{region}'. World regions: {world_regions}",
        )

    if req.context_hint:
        req.context_hint = check(req.context_hint, "context_hint")

    record_api_call(session_id)
    npc = spawn(
        role=req.role,
        faction=faction,
        region=region,
        world=world,
        world_state=game_session.world_state,
        context_hint=req.context_hint,
    )

    game_session.npc_registry[npc["id"]] = npc

    return {
        "session_id": session_id,
        "npc": npc,
        "standing": _standing_for(npc, game_session),
    }


@router.post("/{session_id}/{npc_id}/talk")
def talk(session_id: str, npc_id: str, req: TalkRequest):
    """
    Send a message to an NPC and receive their in-character response.

    The NPC's tone reflects live faction standings, recent mission outcomes,
    and the player's archetype. Profile updates happen automatically unless
    update_profile=false.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    game_session = sessions.get(session_id)
    _require_world(game_session, session_id)
    _ensure_world_state_seeded(game_session)

    npc = game_session.npc_registry.get(npc_id)
    if npc is None:
        raise HTTPException(status_code=404, detail=f"NPC {npc_id} not found. Call /spawn first.")

    history_obj = game_session.npc_history(npc_id)
    safe_message = check(req.message, "player_message")

    record_api_call(session_id)
    reply = respond(
        player_message=safe_message,
        npc=npc,
        history=history_obj.to_claude_messages(),
        player=game_session.profile,
        archetype=game_session.archetype,
        world=game_session.generated_world,
        world_state=game_session.world_state,
        mission_history=game_session.mission_history,
        stats=game_session.stats if game_session.resources_initialized else None,
    )

    history_obj.add("user", safe_message)
    history_obj.add("assistant", reply)

    if req.update_profile:
        context = (
            f"Talking to {npc['name']} ({npc['role']}, {npc.get('faction','independent')}) "
            f"in {npc.get('region','unknown')}."
        )
        record_api_call(session_id)
        game_session.profile = analyze_message(req.message, game_session.profile, context)

    return {
        "session_id": session_id,
        "npc_id": npc_id,
        "npc_name": npc["name"],
        "reply": reply,
        "standing": _standing_for(npc, game_session),
        "profile_observations": game_session.profile.observation_count,
    }


@router.get("/{session_id}")
def list_npcs(session_id: str):
    """All known NPCs for this session with their current faction standings."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    return {
        "session_id": session_id,
        "npcs": [
            {
                **npc,
                "standing": _standing_for(npc, game_session),
                "conversation_turns": len(game_session.npc_history(npc_id).messages) // 2,
            }
            for npc_id, npc in game_session.npc_registry.items()
        ],
    }


@router.get("/{session_id}/{npc_id}")
def get_npc(session_id: str, npc_id: str):
    """Full NPC details and conversation history."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)
    npc = game_session.npc_registry.get(npc_id)
    if npc is None:
        raise HTTPException(status_code=404, detail=f"NPC {npc_id} not found")

    history = game_session.npc_history(npc_id)

    return {
        "session_id": session_id,
        "npc": npc,
        "standing": _standing_for(npc, game_session),
        "history": history.to_claude_messages(),
        "conversation_turns": len(history.messages) // 2,
    }
