"""
Player profile: the 9-axis model of who the player is.

All values are floats in [0.0, 1.0] unless noted.
A value of None means the axis hasn't been observed yet.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PlayerProfile:
    # --- Combat vs. Diplomacy vs. Stealth vs. Exploration ---
    # 0 = pure diplomat/avoider, 1 = pure combatant
    aggression: Optional[float] = None

    # --- Morality ---
    # 0 = purely self-serving / evil, 1 = purely altruistic / good
    morality: Optional[float] = None

    # --- Law alignment ---
    # 0 = chaotic (ignores rules), 1 = lawful (follows authority)
    lawfulness: Optional[float] = None

    # --- Communication voice ---
    # 0 = blunt/aggressive, 1 = warm/empathetic
    empathy: Optional[float] = None

    # --- Roleplay depth ---
    # 0 = treats it like a game, 1 = deep immersive roleplayer
    immersion: Optional[float] = None

    # --- Decision speed ---
    # 0 = impulsive, 1 = deliberate/cautious
    deliberateness: Optional[float] = None

    # --- Social role ---
    # 0 = lone wolf, 1 = social leader
    sociability: Optional[float] = None

    # --- Authority stance ---
    # 0 = openly defiant, 1 = deferential/respectful
    deference: Optional[float] = None

    # --- Preferred themes (top tags, not a scalar) ---
    theme_weights: dict[str, float] = field(default_factory=dict)

    # How many dialogue exchanges have contributed to this profile
    observation_count: int = 0

    def is_ready(self, min_observations: int = 10) -> bool:
        """True once enough data has been collected to generate the world."""
        axes = [
            self.aggression, self.morality, self.lawfulness,
            self.empathy, self.immersion, self.deliberateness,
            self.sociability, self.deference,
        ]
        filled = sum(1 for v in axes if v is not None)
        return filled >= 6 and self.observation_count >= min_observations

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerProfile":
        return cls(**data)

    def top_themes(self, n: int = 3) -> list[str]:
        return sorted(self.theme_weights, key=self.theme_weights.get, reverse=True)[:n]
