import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core import session as sessions
from core.onboarding import OPENING, converse, generate_options, _profile_to_preferences
from core.archetype import crystallize
from core.preferences import GamerFocus
from core.world_state import WorldState
from core.input_guard import check
from api.rate_limit import check_rate_limit, record_api_call

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class RespondRequest(BaseModel):
    message: str


class ChooseRequest(BaseModel):
    choice: str


@router.post("/start")
def start():
    """
    Begin a new onboarding session. Returns the Architect's opening message and a session_id.
    No Claude call — the opening is pre-written.
    """
    session_id = uuid.uuid4().hex
    sessions.get(session_id)  # creates and registers the session
    return {
        "session_id": session_id,
        "message": OPENING,
        "stage": "facility",
    }


@router.post("/{session_id}/respond")
def respond(session_id: str, req: RespondRequest):
    """
    Send a player message to The Architect. Updates profile silently.
    Returns the Architect's reply and whether it's ready to generate worlds.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    if game_session.onboarding_stage != "facility":
        raise HTTPException(
            status_code=400,
            detail=f"Onboarding stage is '{game_session.onboarding_stage}', expected 'facility'.",
        )

    safe_message = check(req.message, "player_message")
    check_rate_limit(session_id)

    try:
        result = converse(safe_message, game_session.facility_history, game_session.profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Architect error: {e}")
    record_api_call(session_id)

    # Update conversation history
    game_session.facility_history.append({"role": "user", "content": safe_message})
    game_session.facility_history.append({"role": "assistant", "content": result["reply"]})

    # Update profile
    game_session.profile = result["updated_profile"]

    # Update preferences from extracted data
    extracted = result.get("extracted", {})
    if extracted.get("world_style") is not None:
        game_session.preferences.world_style = extracted["world_style"]
    if extracted.get("gamer_focus") is not None:
        gf = extracted["gamer_focus"]
        game_session.preferences.gamer_focus = GamerFocus(
            story=gf.get("story", 0.0),
            world=gf.get("world", 0.0),
            missions=gf.get("missions", 0.0),
            combat=gf.get("combat", 0.0),
            social=gf.get("social", 0.0),
        )

    return {
        "session_id": session_id,
        "reply": result["reply"],
        "ready": result["ready"],
        "stage": game_session.onboarding_stage,
    }


@router.post("/{session_id}/generate-options")
def generate_world_options(session_id: str):
    """
    Crystallize the player's profile and generate two world options in parallel.
    World A is built from stated preferences; World B from psychological profile.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    if game_session.onboarding_stage != "facility":
        raise HTTPException(
            status_code=400,
            detail=f"Onboarding stage is '{game_session.onboarding_stage}', expected 'facility'.",
        )

    check_rate_limit(session_id)

    try:
        archetype = crystallize(game_session.profile, force=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not crystallize profile: {e}")

    # 1 call for crystallize + 2 for world generation
    record_api_call(session_id)
    record_api_call(session_id)
    record_api_call(session_id)

    options = generate_options(game_session.profile, archetype, game_session.preferences)

    world_a_name = options[0]["world"].get("name", "World A")
    world_b_name = options[1]["world"].get("name", "World B")
    facility_message = (
        f"Two worlds. Built from the same source — you.\n\n"
        f"{world_a_name} is the world you asked for. It matches your words.\n\n"
        f"{world_b_name} is the world we think you actually want. "
        f"It was built from your patterns — how you answered, not what you said. "
        f"They diverged more than you might expect.\n\n"
        f"Choose carefully. You will live there for a while."
    )

    game_session.archetype = archetype
    game_session.world_options = options
    game_session.onboarding_stage = "options"

    return {
        "session_id": session_id,
        "facility_message": facility_message,
        "options": [
            {
                "id": opt["id"],
                "label": opt["label"],
                "name": opt["world"].get("name"),
                "tagline": opt["world"].get("tagline"),
                "tone": opt["world"].get("tone"),
                "setting_preview": opt["world"].get("setting", "")[:300],
            }
            for opt in options
        ],
        "stage": "options",
    }


@router.post("/{session_id}/choose")
def choose(session_id: str, req: ChooseRequest):
    """
    The player picks World A (stated preferences) or World B (profile-derived).
    Commits the chosen world to the session and marks onboarding complete.
    """
    if req.choice not in ("A", "B"):
        raise HTTPException(status_code=400, detail="Choice must be 'A' or 'B'.")

    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    if game_session.onboarding_stage != "options":
        raise HTTPException(
            status_code=400,
            detail=f"Onboarding stage is '{game_session.onboarding_stage}', expected 'options'.",
        )

    chosen = next(
        (opt for opt in game_session.world_options if opt["id"] == req.choice),
        None,
    )
    if chosen is None:
        raise HTTPException(status_code=400, detail="World option not found. Generate options first.")

    game_session.generated_world = chosen["world"]

    if req.choice == "B":
        game_session.preferences = _profile_to_preferences(
            game_session.profile, game_session.archetype
        )
    # If choice is A, existing preferences are already set from the conversation.

    game_session.world_state = WorldState.from_generated_world(chosen["world"])
    game_session.inventory.currency_name = chosen["world"].get("currency", {}).get("name", "Gold")
    game_session.resources_initialized = True
    game_session.onboarding_stage = "complete"

    return {
        "session_id": session_id,
        "world": chosen["world"],
        "archetype": game_session.archetype,
        "stage": "complete",
        "message": "Your world is ready. Step through.",
    }
