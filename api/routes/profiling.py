from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from core.profiler import analyze_message
from core.archetype import crystallize
from core.profile import PlayerProfile
from core import session as sessions
from api.rate_limit import check_rate_limit, record_api_call

RESET_METHODS = ("therapy", "school", "quest")

# Minimum observations on the current profile before another reset is allowed.
# Prevents immediately resetting after a reset.
MIN_OBSERVATIONS_BEFORE_RESET = 5

# Seed messages that leave a small trace on the fresh profile.
# analyze_message will score these lightly — not enough to lock an axis, just a seed.
_METHOD_SEEDS: dict[str, tuple[str, str]] = {
    "therapy": (
        "I've been thinking about how my choices affect the people around me. "
        "I want to be more aware of others' feelings going forward.",
        "Character reset via therapy — seeding empathy.",
    ),
    "school": (
        "I've been studying strategy and discipline. "
        "I'm going to approach decisions more carefully from now on.",
        "Character reset via school — seeding deliberateness.",
    ),
    "quest": ("", ""),  # blank slate — no seed
}

router = APIRouter(prefix="/profile", tags=["profiling"])


class ResetRequest(BaseModel):
    method: str
    confirmed: bool = False  # Godot must send True — prevents accidental resets

    def validate_method(self) -> None:
        if self.method not in RESET_METHODS:
            raise ValueError(f"method must be one of: {', '.join(RESET_METHODS)}")


class AnalyzeRequest(BaseModel):
    session_id: str
    message: str
    context: str = ""


class ProfileResponse(BaseModel):
    session_id: str
    profile: dict
    ready: bool


class ArchetypeResponse(BaseModel):
    session_id: str
    archetype: dict


@router.post("/analyze", response_model=ProfileResponse)
def analyze(req: AnalyzeRequest):
    """Manually feed a message into the profiler (use /dialogue/talk during gameplay)."""
    check_rate_limit(req.session_id)
    game_session = sessions.get(req.session_id)
    record_api_call(req.session_id)
    game_session.profile = analyze_message(req.message, game_session.profile, req.context)
    return ProfileResponse(
        session_id=req.session_id,
        profile=game_session.profile.to_dict(),
        ready=game_session.profile.is_ready(),
    )


@router.get("/{session_id}", response_model=ProfileResponse)
def get_profile(session_id: str):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    game_session = sessions.get(session_id)
    return ProfileResponse(
        session_id=session_id,
        profile=game_session.profile.to_dict(),
        ready=game_session.profile.is_ready(),
    )


@router.post("/{session_id}/reset")
def reset_profile(session_id: str, req: ResetRequest):
    """
    Reset the player's psychological profile while keeping their world.

    This is a diegetic act — the player went to therapy, enrolled in school,
    or completed a specific quest. The cost (time, money, resource) is enforced
    by Godot. The server enforces one rule: the current profile must have at
    least 5 observations before another reset is allowed, so you can't chain-reset.

    What resets:
      - Profile axes (back to unobserved)
      - Mission pool (was tailored to the old profile)
      - NPC conversation histories (fresh start — NPCs still exist)

    What stays:
      - The world, world state, faction standings
      - Mission history (those things happened)
      - Lore discovered
      - NPC registry
      - Active events, event log
      - Archetype (the world still sees you as who you were until you
        rebuild enough to call /crystallize again)

    The method leaves a small trace on the fresh profile:
      therapy → seeds a light empathy observation
      school  → seeds a light deliberateness observation
      quest   → true blank slate, no seed
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    if req.method not in RESET_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"method must be one of: {', '.join(RESET_METHODS)}",
        )

    if not req.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Send confirmed=true to proceed. This cannot be undone (unless you have a save).",
        )

    game_session = sessions.get(session_id)

    # Enforce minimum observations — can't reset immediately after a reset
    if game_session.profile.observation_count < MIN_OBSERVATIONS_BEFORE_RESET:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Profile only has {game_session.profile.observation_count} observations. "
                f"Need at least {MIN_OBSERVATIONS_BEFORE_RESET} before a reset is allowed. "
                f"Play more before trying again."
            ),
        )

    # Record before wiping
    reset_record = {
        "method": req.method,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "observation_count_at_reset": game_session.profile.observation_count,
        "mission_count_at_reset": len(game_session.mission_history),
        "archetype_at_reset": game_session.archetype.get("name") if game_session.archetype else None,
        "in_game_day": game_session.in_game_day,
    }
    game_session.reset_history.append(reset_record)

    # ── Reset ─────────────────────────────────────────────────────────────────
    game_session.profile = PlayerProfile()
    game_session.mission_pool = []
    game_session.npc_histories = {}
    # archetype intentionally kept — world still knows who you were

    # Apply method seed to the fresh profile
    seed_message, seed_context = _METHOD_SEEDS[req.method]
    if seed_message:
        record_api_call(session_id)
        game_session.profile = analyze_message(seed_message, game_session.profile, seed_context)

    return {
        "session_id": session_id,
        "reset": True,
        "method": req.method,
        "record": reset_record,
        "profile": game_session.profile.to_dict(),
        "archetype_retained": game_session.archetype.get("name") if game_session.archetype else None,
        "observations_needed_to_crystallize": 10,
        "message": (
            "Profile cleared. The world remembers who you were. "
            "Rebuild through action — call /crystallize when ready for a new archetype."
        ),
    }


@router.post("/{session_id}/crystallize", response_model=ArchetypeResponse)
def crystallize_profile(session_id: str):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    game_session = sessions.get(session_id)
    try:
        archetype = crystallize(game_session.profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ArchetypeResponse(session_id=session_id, archetype=archetype)
