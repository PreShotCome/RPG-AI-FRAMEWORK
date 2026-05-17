from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from core import session as sessions
from core.world_state import WorldState, WorldEvent
from core.world_tick import compute_pressure, events_to_generate, bias_event_types
from core.event_generator import generate
from core.profiler import analyze_message
from core.input_guard import check
from api.rate_limit import check_rate_limit, record_api_call

router = APIRouter(prefix="/events", tags=["events"])


# ── Request models ─────────────────────────────────────────────────────────────

class RespondRequest(BaseModel):
    event_id: str
    option_id: str
    approach: str  # free-text — how they actually do it

    @field_validator("approach")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("approach cannot be empty")
        return v.strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_world(game_session) -> None:
    if game_session.generated_world is None:
        raise HTTPException(
            status_code=400,
            detail="World not generated yet. Call POST /world/{session_id}/generate first.",
        )


def _ensure_seeded(game_session) -> None:
    if not game_session.world_state.factions and game_session.generated_world:
        game_session.world_state = WorldState.from_generated_world(game_session.generated_world)


def _missions_since_last_event(game_session) -> int:
    if not game_session.event_log:
        return len(game_session.mission_history)
    last_event_mission_count = game_session.event_log[-1].get("_mission_count_at_time", 0)
    return len(game_session.mission_history) - last_event_mission_count


def _apply_world_impact(impact: dict, game_session, scale: float = 1.0) -> None:
    faction_impacts = impact.get("faction_impacts", {})
    region_impacts = impact.get("region_tension_impacts", {})
    event = WorldEvent(
        faction_impacts={k: v * scale for k, v in faction_impacts.items()},
        region_impacts={k: v * scale for k, v in region_impacts.items()},
    )
    game_session.world_state.apply_event(event)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{session_id}/tick")
def tick(session_id: str):
    """
    Advance the world and generate events if pressure warrants it.

    Godot calls this after mission completion or when in-game time passes.
    Returns active (unresolved) events the player can respond to, plus
    any background events that were applied automatically.

    Returns empty events list if pressure is low — quiet runs stay quiet.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    game_session = sessions.get(session_id)
    _require_world(game_session)
    _ensure_seeded(game_session)

    pressure = compute_pressure(
        profile=game_session.profile,
        world_state=game_session.world_state,
        missions_since_last_event=_missions_since_last_event(game_session),
    )

    count = events_to_generate(pressure)
    new_events = []
    background_applied = []

    if count > 0:
        suggested_types = bias_event_types(game_session.profile, game_session.preferences)

        record_api_call(session_id)
        raw_events = generate(
            count=count,
            world=game_session.generated_world,
            world_state=game_session.world_state,
            profile=game_session.profile,
            preferences=game_session.preferences,
            archetype=game_session.archetype,
            mission_history=game_session.mission_history,
            event_log=game_session.event_log,
            suggested_types=suggested_types,
        )

        for event in raw_events:
            event["_mission_count_at_time"] = len(game_session.mission_history)

            if event.get("urgency") == "background" or not event.get("player_options"):
                # Apply immediately — player just hears about it
                _apply_world_impact(event.get("immediate_world_impact", {}), game_session)
                event["resolved"] = True
                game_session.event_log.append(event)
                background_applied.append(event)
            else:
                # Apply the immediate impact now; option impact applied on respond
                _apply_world_impact(event.get("immediate_world_impact", {}), game_session)
                event["resolved"] = False
                game_session.active_events.append(event)
                game_session.event_log.append(event)
                new_events.append(event)

    return {
        "session_id": session_id,
        "pressure": round(pressure, 3),
        "new_active_events": new_events,
        "background_events": background_applied,
        "active_events": game_session.active_events,
        "world_state": game_session.world_state.summary(),
    }


@router.post("/{session_id}/respond")
def respond_to_event(session_id: str, req: RespondRequest):
    """
    Player responds to an active event by choosing an option and describing
    their approach.

    Applies the option's world impact, updates the player's profile,
    and marks the event resolved.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    check_rate_limit(session_id)
    game_session = sessions.get(session_id)
    _require_world(game_session)

    safe_approach = check(req.approach, "approach")

    event = next((e for e in game_session.active_events if e["id"] == req.event_id), None)
    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Event {req.event_id} not found in active events.",
        )

    option = next((o for o in event.get("player_options", []) if o["id"] == req.option_id), None)
    if option is None:
        valid = [o["id"] for o in event.get("player_options", [])]
        raise HTTPException(
            status_code=400,
            detail=f"Option '{req.option_id}' not found. Valid: {valid}",
        )

    # Apply the chosen option's world impact
    _apply_world_impact(option.get("world_impact", {}), game_session)

    # Update profile — same pipeline as mission completion
    context = (
        f"World event: '{event['title']}' ({event['type']}). "
        f"Player chose: {option['label']}. Approach: {safe_approach}"
    )
    record_api_call(session_id)
    game_session.profile = analyze_message(safe_approach, game_session.profile, context)

    # Resolve the event
    event["resolved"] = True
    event["player_choice"] = {"option_id": req.option_id, "approach": safe_approach}
    game_session.active_events = [e for e in game_session.active_events if e["id"] != req.event_id]

    return {
        "session_id": session_id,
        "resolved_event": event,
        "world_state": game_session.world_state.summary(),
        "profile_observations": game_session.profile.observation_count,
        "active_events_remaining": len(game_session.active_events),
    }


@router.get("/{session_id}")
def get_events(session_id: str):
    """Active events awaiting player response, plus recent event log."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    return {
        "session_id": session_id,
        "active_events": game_session.active_events,
        "event_log": game_session.event_log[-10:],
        "world_state": game_session.world_state.summary(),
    }
