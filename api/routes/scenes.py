import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from core import session as sessions
from core.scene_generator import generate_scene, resolve_action
from core.world_state import WorldEvent
from core.profiler import analyze_message
from core.input_guard import check
from api.rate_limit import check_rate_limit, record_api_call

router = APIRouter(prefix="/scenes", tags=["scenes"])


class ExploreRequest(BaseModel):
    location: str = ""


class ActRequest(BaseModel):
    action: str

    @field_validator("action")
    @classmethod
    def non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("action must not be empty")
        return v


def _require_world_ready(gs, session_id: str):
    if gs.generated_world is None:
        raise HTTPException(status_code=400, detail="World not generated yet.")
    if gs.archetype is None:
        raise HTTPException(status_code=400, detail="Archetype missing.")


@router.post("/{session_id}/explore")
def explore(session_id: str, req: ExploreRequest = ExploreRequest()):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    gs = sessions.get(session_id)
    _require_world_ready(gs, session_id)

    gs.active_mission_id = None

    record_api_call(session_id)
    scene = generate_scene(
        world=gs.generated_world,
        world_state=gs.world_state,
        profile=gs.profile,
        archetype=gs.archetype or {},
        scene_history=gs.scene_history,
        location=req.location,
        mode="exploration",
        mission=None,
        stats=gs.stats if gs.resources_initialized else None,
    )
    if scene is None:
        raise HTTPException(status_code=500, detail="Scene generation failed.")

    gs.current_scene = scene

    return {
        "session_id": session_id,
        "scene": scene,
        "mode": "exploration",
        "world_state": gs.world_state.summary(),
    }


@router.post("/{session_id}/act")
def act(session_id: str, req: ActRequest):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    gs = sessions.get(session_id)
    _require_world_ready(gs, session_id)

    if not gs.current_scene:
        raise HTTPException(status_code=400, detail="No current scene. Call /explore or start a mission first.")

    safe_action = check(req.action, "player_message")

    mode = "mission" if gs.active_mission_id else "exploration"
    mission = None
    if gs.active_mission_id:
        mission = next((m for m in gs.mission_pool if m["id"] == gs.active_mission_id), None)

    scenes_in_mission = 0
    if gs.active_mission_id:
        logs = gs.mission_scene_logs.get(gs.active_mission_id, [])
        scenes_in_mission = len(logs)

    record_api_call(session_id)
    result = resolve_action(
        scene=gs.current_scene,
        player_action=safe_action,
        world=gs.generated_world,
        world_state=gs.world_state,
        profile=gs.profile,
        archetype=gs.archetype or {},
        scene_history=gs.scene_history,
        stats=gs.stats if gs.resources_initialized else None,
        mode=mode,
        mission=mission,
        scenes_in_mission=scenes_in_mission,
    )
    if result is None:
        raise HTTPException(status_code=500, detail="Action resolution failed.")

    # Append to scene history (cap at 20)
    scene_entry = {**gs.current_scene, "player_action": safe_action}
    gs.scene_history.append(scene_entry)
    if len(gs.scene_history) > 20:
        gs.scene_history = gs.scene_history[-20:]

    # Track mission scene logs
    if gs.active_mission_id:
        if gs.active_mission_id not in gs.mission_scene_logs:
            gs.mission_scene_logs[gs.active_mission_id] = []
        gs.mission_scene_logs[gs.active_mission_id].append(scene_entry)

    # Apply world impacts
    world_impacts = result.get("world_impacts") or {}
    if world_impacts:
        event = WorldEvent(
            summary=f"Player action: {safe_action[:80]}",
            faction_impacts={
                k: v for k, v in world_impacts.items()
                if k in gs.world_state.factions
            },
        )
        gs.world_state.apply_event(event)

    # Update profile from behavioral signal
    profile_signal = result.get("profile_signal", "")
    if profile_signal:
        record_api_call(session_id)
        gs.profile = analyze_message(safe_action, gs.profile, profile_signal)

    # Quest discovered
    quest_discovered = result.get("quest_discovered")
    if quest_discovered:
        quest_discovered["id"] = uuid.uuid4().hex
        gs.mission_pool.append(quest_discovered)

    # NPC encountered
    npc_encountered = result.get("npc_encountered")
    if npc_encountered:
        npc_encountered["id"] = uuid.uuid4().hex
        if not hasattr(gs, "journal_npcs") or gs.journal_npcs is None:
            gs.journal_npcs = []
        gs.journal_npcs = getattr(gs, "journal_npcs", [])
        gs.journal_npcs.append(npc_encountered)

    # Mission outcome
    mission_outcome = result.get("mission_outcome")
    completed_mission_id = gs.active_mission_id
    if mission_outcome and gs.active_mission_id:
        finished_mission = next(
            (m for m in gs.mission_pool if m["id"] == gs.active_mission_id), None
        )
        if finished_mission:
            history_entry = {
                **finished_mission,
                "outcome": mission_outcome.get("result"),
                "summary": mission_outcome.get("summary"),
            }
            gs.mission_history.append(history_entry)
            gs.mission_pool = [m for m in gs.mission_pool if m["id"] != gs.active_mission_id]
        gs.active_mission_id = None
        record_api_call(session_id)

    # Advance to next scene
    next_scene = result.get("next_scene")
    if next_scene:
        gs.current_scene = next_scene

    return {
        "session_id": session_id,
        "narrative": result.get("narrative", ""),
        "next_scene": next_scene,
        "mode": mode,
        "mission_outcome": mission_outcome,
        "mission_id": completed_mission_id if mission_outcome else None,
        "quest_discovered": quest_discovered,
        "npc_encountered": npc_encountered,
        "world_state": gs.world_state.summary(),
    }


@router.post("/{session_id}/mission/{mission_id}/start")
def start_mission(session_id: str, mission_id: str):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    gs = sessions.get(session_id)
    _require_world_ready(gs, session_id)

    mission = next((m for m in gs.mission_pool if m["id"] == mission_id), None)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found in pool.")

    gs.active_mission_id = mission_id
    if mission_id not in gs.mission_scene_logs:
        gs.mission_scene_logs[mission_id] = []

    record_api_call(session_id)
    scene = generate_scene(
        world=gs.generated_world,
        world_state=gs.world_state,
        profile=gs.profile,
        archetype=gs.archetype or {},
        scene_history=gs.scene_history,
        location=mission.get("location", ""),
        mode="mission",
        mission=mission,
        stats=gs.stats if gs.resources_initialized else None,
    )
    if scene is None:
        raise HTTPException(status_code=500, detail="Scene generation failed.")

    scene["mode"] = "mission"
    scene["mission_id"] = mission_id
    gs.current_scene = scene

    return {
        "session_id": session_id,
        "scene": scene,
        "mission": mission,
        "mode": "mission",
        "world_state": gs.world_state.summary(),
    }


@router.get("/{session_id}/current")
def get_current(session_id: str):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    gs = sessions.get(session_id)
    mode = "mission" if gs.active_mission_id else "exploration"

    return {
        "session_id": session_id,
        "scene": gs.current_scene,
        "mode": mode,
        "active_mission_id": gs.active_mission_id,
    }
