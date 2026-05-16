from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.profile import PlayerProfile
from core.profiler import analyze_message
from core.archetype import crystallize

router = APIRouter(prefix="/profile", tags=["profiling"])

# In-memory store keyed by session_id.
# Replace with file/DB persistence once save system is built.
_sessions: dict[str, PlayerProfile] = {}


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
    profile = _sessions.get(req.session_id, PlayerProfile())
    updated = analyze_message(req.message, profile, req.context)
    _sessions[req.session_id] = updated
    return ProfileResponse(
        session_id=req.session_id,
        profile=updated.to_dict(),
        ready=updated.is_ready(),
    )


@router.get("/{session_id}", response_model=ProfileResponse)
def get_profile(session_id: str):
    profile = _sessions.get(session_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ProfileResponse(
        session_id=session_id,
        profile=profile.to_dict(),
        ready=profile.is_ready(),
    )


@router.post("/{session_id}/crystallize", response_model=ArchetypeResponse)
def crystallize_profile(session_id: str):
    profile = _sessions.get(session_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        archetype = crystallize(profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ArchetypeResponse(session_id=session_id, archetype=archetype)
