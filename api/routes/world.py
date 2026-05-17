from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from core import session as sessions
from core.archetype import crystallize
from core.preferences import WorldPreferences, GamerFocus, GAMER_FOCUS_KEYS
from core.world_generator import generate

router = APIRouter(prefix="/world", tags=["world"])


class GamerFocusInput(BaseModel):
    story: float = 0.0
    world: float = 0.0
    missions: float = 0.0
    combat: float = 0.0
    social: float = 0.0

    @field_validator("story", "world", "missions", "combat", "social")
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Focus weights must be non-negative")
        return v


class GenerateRequest(BaseModel):
    # Free-text: "gritty 1920s prohibition city", "far-future space western", anything
    world_style: str
    gamer_focus: GamerFocusInput = GamerFocusInput()

    @field_validator("world_style")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("world_style cannot be empty")
        return v.strip()


class WorldResponse(BaseModel):
    session_id: str
    archetype: dict
    world: dict


@router.post("/{session_id}/generate", response_model=WorldResponse)
def generate_world(session_id: str, req: GenerateRequest):
    """
    The level-10 payoff. Takes the player's world style description and
    gamer focus weights, crystallizes their profile into an archetype,
    then generates a full personalized world.

    Safe to call multiple times — each call regenerates the world.
    The archetype is cached on the session after the first crystallization.
    """
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    game_session = sessions.get(session_id)

    if not game_session.profile.is_ready():
        raise HTTPException(
            status_code=400,
            detail=f"Profile not ready yet ({game_session.profile.observation_count} observations, need at least 10 with 6 axes filled).",
        )

    # Crystallize once; reuse on subsequent calls
    if game_session.archetype is None:
        try:
            game_session.archetype = crystallize(game_session.profile)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Store preferences on the session
    game_session.preferences = WorldPreferences(
        world_style=req.world_style,
        gamer_focus=GamerFocus(
            story=req.gamer_focus.story,
            world=req.gamer_focus.world,
            missions=req.gamer_focus.missions,
            combat=req.gamer_focus.combat,
            social=req.gamer_focus.social,
        ),
    )

    world = generate(
        archetype=game_session.archetype,
        preferences=game_session.preferences,
        profile=game_session.profile,
    )
    game_session.generated_world = world

    return WorldResponse(
        session_id=session_id,
        archetype=game_session.archetype,
        world=world,
    )


@router.get("/{session_id}")
def get_world(session_id: str):
    """Return the already-generated world for this session."""
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    game_session = sessions.get(session_id)
    if game_session.generated_world is None:
        raise HTTPException(status_code=404, detail="World not generated yet")
    return {
        "session_id": session_id,
        "archetype": game_session.archetype,
        "preferences": game_session.preferences.to_dict(),
        "world": game_session.generated_world,
    }
