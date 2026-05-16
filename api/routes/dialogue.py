import anthropic
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from config import ANTHROPIC_API_KEY, TRAINING_WORLD_MAX_LEVEL
from core.save_system import load_game, save_game
from core.player_profile import PlayerProfile
from core.npc_system import get_npc, npc_respond_stream, analyze_player_response
from core.dialogue_system import generate_dialogue_options

router = APIRouter(prefix="/dialogue", tags=["dialogue"])
_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


class StartDialogueRequest(BaseModel):
    save_id: str
    npc_id: str


class RespondRequest(BaseModel):
    save_id: str
    npc_id: str
    player_message: str
    npc_last_statement: str = ""


class DialogueOptionsRequest(BaseModel):
    save_id: str
    npc_id: str
    npc_last_statement: str
    dialogue_history: list[dict] = []


@router.post("/start")
async def start_dialogue(req: StartDialogueRequest):
    """Get NPC greeting to begin a conversation."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    npc = get_npc(req.npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail=f"NPC '{req.npc_id}' not found")

    return {
        "npc_id": req.npc_id,
        "npc_name": npc["name"],
        "greeting": npc.get("greeting", "..."),
        "dialogue_history": save.npc_dialogue_history.get(req.npc_id, []),
    }


@router.post("/respond")
async def respond(req: RespondRequest):
    """Stream NPC response to player message, then silently update profile."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    npc = get_npc(req.npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail=f"NPC '{req.npc_id}' not found")

    profile = PlayerProfile.from_dict(save.profile)
    history = save.npc_dialogue_history.get(req.npc_id, [])

    world_context = ""
    if save.world_state:
        ws = save.world_state
        world_context = f"{ws.get('name', '')}: {ws.get('description', '')}"
    else:
        world_context = "The quiet village of Thistlemoor, a place between nowhere and somewhere."

    full_npc_response: list[str] = []

    async def stream_and_update():
        nonlocal full_npc_response
        async for chunk in npc_respond_stream(
            req.npc_id, req.player_message, history, profile, world_context, _client
        ):
            if chunk.startswith("\x00FULL_RESPONSE\x00"):
                full_response = chunk[len("\x00FULL_RESPONSE\x00"):]
                full_npc_response.append(full_response)

                # Update dialogue history
                history.append({"role": "user", "content": req.player_message})
                history.append({"role": "assistant", "content": full_response})
                save.npc_dialogue_history[req.npc_id] = history[-20:]

                # Silently analyze and update profile (training world only)
                if profile.level <= TRAINING_WORLD_MAX_LEVEL:
                    updated_profile = await analyze_player_response(
                        req.npc_id,
                        req.npc_last_statement or npc.get("greeting", ""),
                        req.player_message,
                        profile,
                        _client,
                    )
                    save.profile = updated_profile.to_dict()
                else:
                    profile.log_interaction(
                        req.npc_id,
                        req.npc_last_statement,
                        req.player_message,
                    )
                    save.profile = profile.to_dict()

                save_game(save)
            else:
                yield chunk

    return StreamingResponse(stream_and_update(), media_type="text/plain")


@router.post("/options")
async def dialogue_options(req: DialogueOptionsRequest):
    """Generate 4 profile-matched dialogue choices. Only available after level 10."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)

    if profile.level <= TRAINING_WORLD_MAX_LEVEL:
        raise HTTPException(
            status_code=403,
            detail="Dialogue options unlock after the training world (level 10+).",
        )

    options = await generate_dialogue_options(
        req.npc_id,
        req.npc_last_statement,
        req.dialogue_history,
        profile,
        _client,
    )

    return {"options": options, "can_type_own": True}
