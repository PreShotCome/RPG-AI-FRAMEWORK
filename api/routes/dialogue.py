from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core import npc as npc_engine
from core import session as sessions

router = APIRouter(prefix="/dialogue", tags=["dialogue"])


class TalkRequest(BaseModel):
    session_id: str
    npc_id: str
    message: str


class TalkResponse(BaseModel):
    npc_id: str
    npc_name: str
    reply: str
    profile_ready: bool
    observation_count: int


class NPCInfo(BaseModel):
    id: str
    name: str
    role: str
    opening_line: str
    hook: str


@router.get("/npcs", response_model=list[NPCInfo])
def list_npcs():
    """Return all NPCs available in Thistlemoor."""
    return [npc_engine.get_npc_info(npc_id) for npc_id in npc_engine.get_npc_ids()]


@router.get("/npcs/{npc_id}", response_model=NPCInfo)
def get_npc(npc_id: str):
    info = npc_engine.get_npc_info(npc_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"NPC '{npc_id}' not found")
    return info


@router.post("/talk", response_model=TalkResponse)
def talk(req: TalkRequest):
    """Send a player message to an NPC. Profile is updated silently."""
    try:
        reply = npc_engine.talk(req.session_id, req.npc_id, req.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    game_session = sessions.get(req.session_id)
    npc_info = npc_engine.get_npc_info(req.npc_id)

    return TalkResponse(
        npc_id=req.npc_id,
        npc_name=npc_info["name"],
        reply=reply,
        profile_ready=game_session.profile.is_ready(),
        observation_count=game_session.profile.observation_count,
    )


@router.get("/{session_id}/{npc_id}/history")
def get_history(session_id: str, npc_id: str):
    """Return the full conversation history with a specific NPC."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    game_session = sessions.get(session_id)
    history = game_session.npc_history(npc_id)
    return {"session_id": session_id, "npc_id": npc_id, "messages": history.messages}
