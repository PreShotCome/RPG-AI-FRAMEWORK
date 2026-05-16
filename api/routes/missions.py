import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import ANTHROPIC_API_KEY, TRAINING_WORLD_MAX_LEVEL, MISSIONS_TO_UNLOCK_ACT
from core.save_system import load_game, save_game
from core.player_profile import PlayerProfile
from core.npc_system import get_npc
from core.mission_generator import (
    get_training_missions,
    generate_npc_mission,
    generate_campaign_mission,
)
from core.campaign_manager import check_act_unlock, get_campaign_progress

router = APIRouter(prefix="/missions", tags=["missions"])
_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


class GenerateFromNPCRequest(BaseModel):
    save_id: str
    npc_id: str


class GenerateCampaignRequest(BaseModel):
    save_id: str
    act: int
    mission_index: int


class AcceptMissionRequest(BaseModel):
    save_id: str
    mission: dict


class CompleteMissionRequest(BaseModel):
    save_id: str
    mission_id: str
    xp_gained: int = 50


@router.get("/available/{save_id}")
async def get_available_missions(save_id: str):
    """Return currently available missions for the player."""
    save = load_game(save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)
    completed_ids = {m.get("id") for m in save.completed_missions}

    if profile.level <= TRAINING_WORLD_MAX_LEVEL:
        training = get_training_missions()
        available = [m for m in training if m["id"] not in completed_ids]
        return {
            "missions": available,
            "is_training": True,
            "campaign_progress": None,
        }

    progress = get_campaign_progress(save.completed_missions)
    return {
        "missions": save.active_missions,
        "is_training": False,
        "campaign_progress": progress,
        "completed_count": len(save.completed_missions),
    }


@router.post("/generate-from-npc")
async def gen_from_npc(req: GenerateFromNPCRequest):
    """Ask an NPC for a new side mission."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    npc = get_npc(req.npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail=f"NPC '{req.npc_id}' not found")

    profile = PlayerProfile.from_dict(save.profile)

    world_context = ""
    if save.world_state:
        ws = save.world_state
        world_context = f"{ws.get('name', '')}: {ws.get('central_conflict', '')}"
    else:
        world_context = "The village of Thistlemoor and the surrounding countryside."

    mission = await generate_npc_mission(
        req.npc_id,
        npc.get("role", "villager"),
        profile,
        world_context,
        _client,
    )
    return {"mission": mission}


@router.post("/generate-campaign")
async def gen_campaign(req: GenerateCampaignRequest):
    """Generate a campaign mission for a given act and position."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)

    if not profile.checkpoint_reached:
        raise HTTPException(
            status_code=403,
            detail="Campaign missions only available after checkpoint (level 10+).",
        )

    if req.act > 0 and not check_act_unlock(save.completed_missions, req.act - 1):
        raise HTTPException(
            status_code=403,
            detail=f"Act {req.act + 1} not yet unlocked. Complete {MISSIONS_TO_UNLOCK_ACT} campaign missions in Act {req.act}.",
        )

    mission = await generate_campaign_mission(
        req.act, req.mission_index, profile, save.world_state, _client
    )
    return {"mission": mission}


@router.post("/accept")
async def accept_mission(req: AcceptMissionRequest):
    """Add a mission to the player's active list."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    existing_ids = {m.get("id") for m in save.active_missions}
    if req.mission.get("id") not in existing_ids:
        save.active_missions.append(req.mission)
        save_game(save)

    return {"status": "accepted", "mission_id": req.mission.get("id")}


@router.post("/complete")
async def complete_mission(req: CompleteMissionRequest):
    """Mark a mission complete and level up the player."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)

    # Move mission from active to completed
    mission = next((m for m in save.active_missions if m.get("id") == req.mission_id), None)
    if not mission:
        # Could be a training mission
        training = get_training_missions()
        mission = next((m for m in training if m.get("id") == req.mission_id), None)

    if mission:
        if mission not in save.completed_missions:
            save.completed_missions.append(mission)
        save.active_missions = [m for m in save.active_missions if m.get("id") != req.mission_id]

    # Level up
    old_level = profile.level
    profile.level += 1

    save.profile = profile.to_dict()
    save_game(save)

    result = {
        "status": "completed",
        "mission_id": req.mission_id,
        "old_level": old_level,
        "new_level": profile.level,
        "xp_gained": req.xp_gained,
    }

    if old_level < TRAINING_WORLD_MAX_LEVEL and profile.level >= TRAINING_WORLD_MAX_LEVEL:
        result["checkpoint_ready"] = True
        result["message"] = "You have reached the threshold. The world watches you differently now."

    return result
