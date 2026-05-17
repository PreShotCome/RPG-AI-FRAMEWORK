"""
World tick — decides whether events should fire and how many.

Event pressure is derived entirely from world state + player profile.
No manual tuning: chaotic players who destabilise regions get a churning
world; careful lawful players get quiet runs.
"""

from core.profile import PlayerProfile
from core.preferences import WorldPreferences
from core.world_state import WorldState


def compute_pressure(
    profile: PlayerProfile,
    world_state: WorldState,
    missions_since_last_event: int,
) -> float:
    """
    Returns a pressure value in [0.0, 1.0].
    Above 0.4 → generate 1 event. Above 0.75 → generate 2.

    Three inputs:
      1. World state — how tense/hostile things actually are
      2. Player profile — how much chaos they carry with them
      3. Staleness — the world shouldn't freeze if the player is being cautious
    """

    # ── 1. World state pressure ───────────────────────────────────────────────
    region_pressure = 0.0
    if world_state.regions:
        avg_tension = sum(r.tension for r in world_state.regions.values()) / len(world_state.regions)
        max_tension = max(r.tension for r in world_state.regions.values())
        region_pressure = avg_tension * 0.4 + max_tension * 0.6

    faction_pressure = 0.0
    if world_state.factions:
        hostile = [f for f in world_state.factions.values() if f.standing <= -40]
        faction_pressure = min(1.0, len(hostile) / max(len(world_state.factions), 1) * 1.5)

    world_pressure = region_pressure * 0.6 + faction_pressure * 0.4

    # ── 2. Player profile pressure ────────────────────────────────────────────
    # High aggression, low lawfulness, low deliberateness = world reacts more
    def _v(val, default=0.5):
        return val if val is not None else default

    aggression    = _v(profile.aggression)
    lawfulness    = _v(profile.lawfulness)
    deliberate    = _v(profile.deliberateness)

    # chaotic_score: 1.0 = pure chaos agent, 0.0 = stabilising force
    chaotic_score = (aggression * 0.4 + (1.0 - lawfulness) * 0.4 + (1.0 - deliberate) * 0.2)
    player_pressure = chaotic_score * 0.6  # player alone can push up to 0.6

    # ── 3. Staleness — slow background pressure if nothing has happened ───────
    staleness = min(1.0, missions_since_last_event / 8.0) * 0.25

    raw = world_pressure * 0.5 + player_pressure * 0.35 + staleness * 0.15
    return min(1.0, raw)


def events_to_generate(pressure: float) -> int:
    if pressure >= 0.75:
        return 2
    if pressure >= 0.4:
        return 1
    return 0


def bias_event_types(profile: PlayerProfile, preferences: WorldPreferences) -> list[str]:
    """
    Return event types weighted toward this player's profile + gamer focus.
    The generator uses this as a soft suggestion, not a hard constraint.
    """
    focus = preferences.gamer_focus.normalized()

    weights: dict[str, float] = {
        "faction_conflict":  focus["combat"] * 0.6 + focus["missions"] * 0.2,
        "uprising":          focus["combat"] * 0.4 + focus["story"] * 0.3,
        "political_shift":   focus["social"] * 0.7 + focus["story"] * 0.2,
        "assassination":     focus["social"] * 0.5 + focus["story"] * 0.4,
        "power_vacuum":      focus["social"] * 0.4 + focus["world"] * 0.3,
        "criminal_surge":    focus["combat"] * 0.3 + focus["missions"] * 0.4,
        "discovery":         focus["world"] * 0.8 + focus["story"] * 0.1,
        "treaty":            focus["social"] * 0.6 + focus["story"] * 0.2,
    }

    # Profile modifiers
    def _v(val, default=0.5):
        return val if val is not None else default

    agg = _v(profile.aggression)
    law = _v(profile.lawfulness)

    weights["faction_conflict"] += agg * 0.2
    weights["uprising"]         += (1.0 - law) * 0.2
    weights["treaty"]           += law * 0.2
    weights["political_shift"]  += law * 0.1

    # Sort by weight descending — top types are the suggestion
    ranked = sorted(weights.keys(), key=lambda k: weights[k], reverse=True)
    return ranked[:4]
