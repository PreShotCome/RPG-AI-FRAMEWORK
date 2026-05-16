from fastapi import APIRouter, HTTPException
from core.save_system import load_game
from core.player_profile import PlayerProfile
from core.world_generator import get_training_world, get_area_info
from core.npc_system import get_npcs_in_area
from config import TRAINING_WORLD_MAX_LEVEL

router = APIRouter(prefix="/world", tags=["world"])


@router.get("/info/{save_id}")
async def world_info(save_id: str):
    """Return the current world state for this save."""
    save = load_game(save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)
    is_training = profile.level <= TRAINING_WORLD_MAX_LEVEL and not profile.checkpoint_reached

    if is_training:
        world = get_training_world()
    elif save.world_state:
        world = save.world_state
    else:
        raise HTTPException(status_code=404, detail="No world generated yet. Complete the checkpoint first.")

    return {
        "world": world,
        "is_training": is_training,
        "current_area": save.current_area_id,
        "level": profile.level,
        "checkpoint_reached": profile.checkpoint_reached,
    }


@router.get("/area/{save_id}/{area_id}")
async def area_info(save_id: str, area_id: str):
    """Return details about a specific area."""
    save = load_game(save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)
    is_training = profile.level <= TRAINING_WORLD_MAX_LEVEL and not profile.checkpoint_reached

    if is_training:
        area = get_area_info(area_id, save.world_seed)
        if not area:
            raise HTTPException(status_code=404, detail=f"Area '{area_id}' not found")
        return {"area": area, "is_training": True}

    # Post-checkpoint: look in generated world regions
    if save.world_state:
        regions = save.world_state.get("regions", [])
        region = next((r for r in regions if r.get("id") == area_id), None)
        if region:
            return {"area": region, "is_training": False}

    raise HTTPException(status_code=404, detail=f"Area '{area_id}' not found")


@router.get("/npcs/{save_id}/{area_id}")
async def npcs_in_area(save_id: str, area_id: str):
    """Return NPCs in a specific area."""
    save = load_game(save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)
    is_training = profile.level <= TRAINING_WORLD_MAX_LEVEL and not profile.checkpoint_reached

    if is_training:
        npcs = get_npcs_in_area(area_id)
        # Only expose safe fields to Godot (hide profiling_style, signature_questions)
        safe_npcs = [
            {
                "id": npc.get("id"),
                "name": npc.get("name"),
                "role": npc.get("role"),
                "appearance": npc.get("appearance"),
                "greeting": npc.get("greeting"),
                "area_id": npc.get("area_id"),
            }
            for npc in npcs
        ]
        return {"npcs": safe_npcs, "area_id": area_id}

    # Post-checkpoint world can have dynamically placed NPCs
    return {"npcs": [], "area_id": area_id, "note": "NPC placement in generated world coming soon."}


@router.get("/profile/{save_id}")
async def player_profile(save_id: str):
    """Return the current player profile summary."""
    save = load_game(save_id)
    if not save:
        raise HTTPException(status_code=404, detail="Save file not found")

    profile = PlayerProfile.from_dict(save.profile)

    return {
        "level": profile.level,
        "archetype": profile.archetype,
        "archetype_description": profile.archetype_description,
        "checkpoint_reached": profile.checkpoint_reached,
        "dominant_playstyle": profile.get_dominant_playstyle(),
        "moral_label": profile.get_moral_label(),
        "law_label": profile.get_law_label(),
        "dominant_voice": profile.get_dominant_voice(),
        "social_role": profile.get_dominant_social_role(),
        "authority_stance": profile.get_dominant_authority_stance(),
        "top_themes": profile.get_top_themes(3),
        "interactions_logged": len(profile.interaction_log),
        "summary": profile.get_summary_for_ai(),
    }
