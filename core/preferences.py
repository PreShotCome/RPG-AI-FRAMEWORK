"""
Player-stated preferences collected at the end of the training world.

These are the two explicit choices the player makes — separate from the
silent psychological profile the training world built. Both are combined
with the archetype at world generation time.
"""

from dataclasses import dataclass, field
from typing import Optional

GAMER_FOCUS_KEYS = ["story", "world", "missions", "combat", "social"]


@dataclass
class GamerFocus:
    story: float = 0.0    # narrative, character arcs, emotional beats
    world: float = 0.0    # lore, exploration, atmosphere, discovery
    missions: float = 0.0 # clear objectives, quests, progression
    combat: float = 0.0   # action, difficulty, skill expression
    social: float = 0.0   # NPC relationships, dialogue, political intrigue

    def normalized(self) -> dict[str, float]:
        total = self.story + self.world + self.missions + self.combat + self.social
        if total == 0:
            equal = 1.0 / len(GAMER_FOCUS_KEYS)
            return {k: equal for k in GAMER_FOCUS_KEYS}
        return {
            "story":   self.story   / total,
            "world":   self.world   / total,
            "missions": self.missions / total,
            "combat":  self.combat  / total,
            "social":  self.social  / total,
        }

    def top(self, n: int = 2) -> list[str]:
        ranked = sorted(GAMER_FOCUS_KEYS, key=lambda k: getattr(self, k), reverse=True)
        return ranked[:n]

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in GAMER_FOCUS_KEYS}

    @classmethod
    def from_dict(cls, data: dict) -> "GamerFocus":
        return cls(**{k: data.get(k, 0.0) for k in GAMER_FOCUS_KEYS})


@dataclass
class WorldPreferences:
    # Free-text description of the world setting the player wants.
    # Can be anything: "gritty 1920s prohibition city with secret magic",
    # "far-future space western", "grimdark medieval fantasy", etc.
    world_style: str = ""

    gamer_focus: GamerFocus = field(default_factory=GamerFocus)

    def is_set(self) -> bool:
        return bool(self.world_style.strip())

    def to_dict(self) -> dict:
        return {
            "world_style": self.world_style,
            "gamer_focus": self.gamer_focus.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldPreferences":
        return cls(
            world_style=data.get("world_style", ""),
            gamer_focus=GamerFocus.from_dict(data.get("gamer_focus", {})),
        )
