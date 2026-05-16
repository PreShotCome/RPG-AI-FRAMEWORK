import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import ANTHROPIC_API_KEY, TRAINING_WORLD_MAX_LEVEL
from core.save_system import new_save, save_game, load_game, list_saves, delete_save, SaveData
from core.player_profile import PlayerProfile
from core.world_generator import get_training_world, generate_real_world
from core.campaign_manager import generate_archetype

router = APIRouter(prefix="/game", tags=["game"])
_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

class LoadRequest(BaseModel):
    save_id: str

class SaveRequest(BaseModel):
    save_id: str
    world_state: dict = {}
    active_missions: list = []
    completed_missions: list = []
    current_area_id: str = "mill"
    campaign_act: int = 0

class CheckpointRequest(BaseModel):
    save_id: str

@router.post("/new")
async def new_game():
    """Create a new game with a unique world seed and start the training world."""
    save = new_save()
    save_game(save)
    world = get_training_world()
    return {
        "save_id": save.save_id,
        "world_seed": save.world_seed,
        "world": world,
        "message": "A new world has been seeded. Your story starts in Thistlemoor.",
        "is_training_world": True,
        "level": 1
    }

@router.get("/saves")
async def get_saves():
    """List all save files."""
    return {"saves": list_saves()}

@router.post("/load")
async def load(req: LoadRequest):
    """Load an existing save file."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)
    is_training = profile.level <= TRAINING_WORLD_MAX_LEVEL and not profile.checkpoint_reached

    world = None
    if is_training:
        world = get_training_world()
    elif save.world_state:
        world = save.world_state

    return {
        "save_id": save.save_id,
        "world_seed": save.world_seed,
        "world": world,
        "profile": save.profile,
        "active_missions": save.active_missions,
        "completed_missions": save.completed_missions,
        "current_area_id": save.current_area_id,
        "campaign_act": save.campaign_act,
        "is_training_world": is_training,
        "level": profile.level
    }

@router.post("/save")
async def save(req: SaveRequest):
    """Save current game state."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    save.world_state = req.world_state
    save.active_missions = req.active_missions
    save.completed_missions = req.completed_missions
    save.current_area_id = req.current_area_id
    save.campaign_act = req.campaign_act

    save_game(save)
    return {"status": "saved", "save_id": req.save_id}

@router.post("/checkpoint")
async def checkpoint(req: CheckpointRequest):
    """Trigger the level 10 checkpoint — crystallize archetype and generate real world."""
    save = load_game(req.save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)

    if profile.checkpoint_reached:
        return {"status": "already_completed", "archetype": profile.archetype}

    # Generate archetype
    archetype, description = await generate_archetype(profile, _client)
    profile.archetype = archetype
    profile.archetype_description = description
    profile.checkpoint_reached = True

    # Generate real world
    world = await generate_real_world(profile, save.world_seed, _client)

    # Save everything
    save.profile = profile.to_dict()
    save.world_state = world
    save_game(save)

    return {
        "status": "checkpoint_complete",
        "archetype": archetype,
        "archetype_description": description,
        "world": world,
        "message": f"The world reshapes itself. You are {archetype}."
    }

@router.delete("/{save_id}")
async def delete(save_id: str):
    """Delete a save file."""
    if delete_save(save_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Save file not found")
