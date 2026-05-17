from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from core import session as sessions
from core.resources import (
    PlayerStats, PlayerInventory, STAT_KEYS, STAT_MAX,
    calculate_mission_reward, apply_reward,
)

router = APIRouter(prefix="/resources", tags=["resources"])

_STARTING_CURRENCY = 150.0  # enough to see the upgrade system without trivializing it


# ── Request models ─────────────────────────────────────────────────────────────

class EarnRequest(BaseModel):
    currency: float = 0.0
    faction_tokens: dict[str, int] = {}
    reason: str = ""  # for logging — not enforced

    @field_validator("currency")
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("currency amount must be non-negative")
        return v


class SpendRequest(BaseModel):
    currency: float = 0.0
    faction_tokens: dict[str, int] = {}
    reason: str = ""

    @field_validator("currency")
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("currency amount must be non-negative")
        return v


class UpgradeRequest(BaseModel):
    stat: str

    @field_validator("stat")
    @classmethod
    def valid_stat(cls, v: str) -> str:
        if v not in STAT_KEYS:
            raise ValueError(f"stat must be one of: {', '.join(STAT_KEYS)}")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(session_id: str):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions.get(session_id)


def _require_initialized(game_session) -> None:
    if not game_session.resources_initialized:
        raise HTTPException(
            status_code=400,
            detail="Resources not initialized. Call POST /resources/{session_id}/initialize first.",
        )


def _stat_flavors(game_session) -> dict[str, str]:
    if game_session.generated_world:
        return game_session.generated_world.get("stat_flavors", {})
    return {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{session_id}/initialize")
def initialize(session_id: str):
    """
    Seed the player's stats and inventory from the generated world.

    Call once after world generation. Reads currency name and stat flavor
    names from the world dict. Safe to call again — returns current state
    if already initialized without resetting it.
    """
    game_session = _get_session(session_id)

    if game_session.generated_world is None:
        raise HTTPException(
            status_code=400,
            detail="World not generated yet. Call POST /world/{session_id}/generate first.",
        )

    if game_session.resources_initialized:
        world = game_session.generated_world
        return {
            "session_id": session_id,
            "already_initialized": True,
            "stats": game_session.stats.with_flavors(_stat_flavors(game_session)),
            "inventory": game_session.inventory.to_dict(),
            "currency": world.get("currency", {}),
        }

    world = game_session.generated_world
    currency_info = world.get("currency", {})

    game_session.stats = PlayerStats()
    game_session.inventory = PlayerInventory(
        currency=_STARTING_CURRENCY,
        currency_name=currency_info.get("name", "gold"),
    )

    # Seed empty token balances for each faction
    for faction in world.get("factions", []):
        game_session.inventory.faction_tokens[faction["name"]] = 0

    game_session.resources_initialized = True

    return {
        "session_id": session_id,
        "initialized": True,
        "starting_currency": _STARTING_CURRENCY,
        "stats": game_session.stats.with_flavors(_stat_flavors(game_session)),
        "inventory": game_session.inventory.to_dict(),
        "currency": currency_info,
        "stat_flavors": world.get("stat_flavors", {}),
    }


@router.get("/{session_id}")
def get_resources(session_id: str):
    """Full resource snapshot — stats with display names, inventory, upgrade costs."""
    game_session = _get_session(session_id)
    _require_initialized(game_session)

    world = game_session.generated_world or {}
    flavors = _stat_flavors(game_session)

    return {
        "session_id": session_id,
        "stats": game_session.stats.with_flavors(flavors),
        "inventory": game_session.inventory.to_dict(),
        "currency_info": world.get("currency", {}),
        "stat_flavors": flavors,
    }


@router.post("/{session_id}/earn")
def earn(session_id: str, req: EarnRequest):
    """
    Credit resources to the player.

    Godot calls this to apply mission rewards, event payouts, NPC trades,
    or anything else that gives the player resources. The reason field is
    for logging only.
    """
    game_session = _get_session(session_id)
    _require_initialized(game_session)

    game_session.inventory.earn_currency(req.currency)
    for faction, amount in req.faction_tokens.items():
        game_session.inventory.earn_faction_token(faction, amount)

    return {
        "session_id": session_id,
        "earned": {"currency": req.currency, "faction_tokens": req.faction_tokens},
        "inventory": game_session.inventory.to_dict(),
    }


@router.post("/{session_id}/spend")
def spend(session_id: str, req: SpendRequest):
    """
    Deduct resources from the player. Returns 402 if insufficient funds.

    Godot calls this for profile resets, NPC services, buying items —
    anything that costs resources outside of stat upgrades.
    """
    game_session = _get_session(session_id)
    _require_initialized(game_session)

    # Check affordability before touching anything
    if req.currency > game_session.inventory.currency:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient currency. Need {req.currency} "
                f"{game_session.inventory.currency_name}, "
                f"have {game_session.inventory.currency:.2f}."
            ),
        )
    for faction, amount in req.faction_tokens.items():
        have = game_session.inventory.faction_tokens.get(faction, 0)
        if have < amount:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient {faction} tokens. Need {amount}, have {have}.",
            )

    # All checks passed — deduct
    game_session.inventory.spend_currency(req.currency)
    for faction, amount in req.faction_tokens.items():
        game_session.inventory.spend_faction_token(faction, amount)

    return {
        "session_id": session_id,
        "spent": {"currency": req.currency, "faction_tokens": req.faction_tokens},
        "inventory": game_session.inventory.to_dict(),
    }


@router.post("/{session_id}/upgrade")
def upgrade_stat(session_id: str, req: UpgradeRequest):
    """
    Spend currency to upgrade a stat by 1 level.

    Cost = current_level × 100. Returns 402 if insufficient funds,
    400 if stat is already at max.
    """
    game_session = _get_session(session_id)
    _require_initialized(game_session)

    stat = req.stat
    if not game_session.stats.can_upgrade(stat):
        raise HTTPException(
            status_code=400,
            detail=f"'{stat}' is already at max level {STAT_MAX}.",
        )

    cost = game_session.stats.upgrade_cost(stat)
    if game_session.inventory.currency < cost:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient currency. Upgrading '{stat}' costs {cost} "
                f"{game_session.inventory.currency_name}, "
                f"have {game_session.inventory.currency:.2f}."
            ),
        )

    game_session.inventory.spend_currency(cost)
    new_level = game_session.stats.upgrade(stat)
    flavors = _stat_flavors(game_session)

    return {
        "session_id": session_id,
        "upgraded": stat,
        "display_name": flavors.get(stat, stat.title()),
        "new_level": new_level,
        "cost_paid": cost,
        "next_upgrade_cost": game_session.stats.upgrade_cost(stat) if game_session.stats.can_upgrade(stat) else None,
        "inventory": game_session.inventory.to_dict(),
    }
