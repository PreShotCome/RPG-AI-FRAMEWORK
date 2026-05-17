from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import uuid
from core import session as sessions
from core.world_state import WorldState
from core.mirror_generator import generate
from api.rate_limit import check_rate_limit, record_api_call

router = APIRouter(prefix="/mirror", tags=["mirror"])


def _require_world(game_session) -> None:
    if game_session.generated_world is None:
        raise HTTPException(
            status_code=400,
            detail="World not generated yet. Call POST /world/{session_id}/generate first.",
        )


def _ensure_seeded(game_session) -> None:
    if not game_session.world_state.factions and game_session.generated_world:
        game_session.world_state = WorldState.from_generated_world(game_session.generated_world)


@router.post("/{session_id}")
def generate_mirror(session_id: str):
    """
    Generate a Player Mirror — a literary portrait of who this player
    has become in their world.

    Written in second person. Specific to this player's actual history,
    choices, relationships, and contradictions. Not a stats summary.

    Every mirror is stored on the session, so the player can look back
    and see who they used to be. Call at any meaningful moment — after
    a cluster of missions, after a reset, after a major event.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    game_session = sessions.get(session_id)
    _require_world(game_session)
    _ensure_seeded(game_session)

    if game_session.archetype is None:
        raise HTTPException(
            status_code=400,
            detail="Archetype not yet set. Complete world generation first.",
        )

    if game_session.profile.observation_count < 5:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only {game_session.profile.observation_count} observations recorded. "
                "The mirror needs more of you in it — play more before generating one."
            ),
        )

    record_api_call(session_id)
    text = generate(
        profile=game_session.profile,
        archetype=game_session.archetype,
        world=game_session.generated_world,
        world_state=game_session.world_state,
        preferences=game_session.preferences,
        mission_history=game_session.mission_history,
        lore_discovered=game_session.lore_discovered,
        stats=game_session.stats if game_session.resources_initialized else None,
        reset_history=game_session.reset_history,
        in_game_day=game_session.in_game_day,
    )

    entry = {
        "id": uuid.uuid4().hex[:8],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "in_game_day": game_session.in_game_day,
        "mission_count": len(game_session.mission_history),
        "observation_count": game_session.profile.observation_count,
        "archetype_name": game_session.archetype.get("name", ""),
        "reset_count": len(game_session.reset_history),
        "text": text,
    }

    game_session.mirrors.append(entry)

    return {
        "session_id": session_id,
        "mirror": entry,
        "total_mirrors": len(game_session.mirrors),
    }


@router.get("/{session_id}")
def get_mirrors(session_id: str):
    """
    All mirrors generated for this session — the player's evolution over time.

    Earlier mirrors show who they were. The latest shows who they are.
    The distance between them is the story.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    return {
        "session_id": session_id,
        "mirrors": game_session.mirrors,
        "count": len(game_session.mirrors),
    }


@router.get("/{session_id}/latest")
def get_latest_mirror(session_id: str):
    """The most recently generated mirror."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)
    if not game_session.mirrors:
        raise HTTPException(
            status_code=404,
            detail="No mirrors generated yet. Call POST /mirror/{session_id} first.",
        )

    return {
        "session_id": session_id,
        "mirror": game_session.mirrors[-1],
    }
