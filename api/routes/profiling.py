from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.profiler import analyze_message
from core.archetype import crystallize
from core import session as sessions

router = APIRouter(prefix="/profile", tags=["profiling"])


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
    game_session = sessions.get(req.session_id)
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
