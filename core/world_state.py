"""
Mutable world state — changes as the player completes missions and makes choices.

Faction standings and regional tension start neutral and drift based on outcomes.
This feeds back into mission generation so the world feels reactive.
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class FactionStanding:
    name: str
    standing: float = 0.0  # -100 (hostile) to +100 (allied)
    description: str = ""

    def adjust(self, delta: float) -> None:
        self.standing = max(-100.0, min(100.0, self.standing + delta))

    def label(self) -> str:
        if self.standing >= 60:
            return "allied"
        if self.standing >= 20:
            return "friendly"
        if self.standing >= -20:
            return "neutral"
        if self.standing >= -60:
            return "unfriendly"
        return "hostile"


@dataclass
class RegionState:
    name: str
    tension: float = 0.5  # 0.0 (peaceful) to 1.0 (warzone)
    controlling_faction: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def adjust_tension(self, delta: float) -> None:
        self.tension = max(0.0, min(1.0, self.tension + delta))


@dataclass
class WorldEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    summary: str = ""
    mission_id: Optional[str] = None
    faction_impacts: dict[str, float] = field(default_factory=dict)
    region_impacts: dict[str, float] = field(default_factory=dict)


@dataclass
class WorldState:
    factions: dict[str, FactionStanding] = field(default_factory=dict)
    regions: dict[str, RegionState] = field(default_factory=dict)
    events: list[WorldEvent] = field(default_factory=list)
    global_tension: float = 0.3  # 0.0 (stable) to 1.0 (total chaos)

    @classmethod
    def from_generated_world(cls, world: dict) -> "WorldState":
        """Seed world state from the generated world dict."""
        state = cls()
        for f in world.get("factions", []):
            state.factions[f["name"]] = FactionStanding(
                name=f["name"],
                description=f.get("description", ""),
            )
        for r in world.get("regions", []):
            state.regions[r["name"]] = RegionState(name=r["name"])
        return state

    def apply_event(self, event: WorldEvent) -> None:
        for faction_name, delta in event.faction_impacts.items():
            if faction_name in self.factions:
                self.factions[faction_name].adjust(delta)
        for region_name, delta in event.region_impacts.items():
            if region_name in self.regions:
                self.regions[region_name].adjust_tension(delta)
        # Global tension nudges toward the average regional tension
        if self.regions:
            avg = sum(r.tension for r in self.regions.values()) / len(self.regions)
            self.global_tension = max(0.0, min(1.0, self.global_tension * 0.8 + avg * 0.2))
        self.events.append(event)

    def summary(self) -> dict:
        return {
            "global_tension": round(self.global_tension, 2),
            "factions": {
                name: {"standing": round(f.standing, 1), "label": f.label()}
                for name, f in self.factions.items()
            },
            "regions": {
                name: {"tension": round(r.tension, 2), "controlling_faction": r.controlling_faction}
                for name, r in self.regions.items()
            },
            "recent_events": [e.summary for e in self.events[-5:]],
        }
