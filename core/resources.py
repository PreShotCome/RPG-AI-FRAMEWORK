"""
Player resources: stats and inventory.

Stats are canonical (combat, stealth, etc.) with world-specific display names
supplied by the world generator. Inventory holds currency and per-faction tokens.
"""

import random
from dataclasses import dataclass, field
from typing import Optional

STAT_KEYS = ["combat", "stealth", "persuasion", "intellect", "endurance", "luck"]
STAT_MIN = 1
STAT_MAX = 10

# Upgrade cost = current_level * COST_PER_LEVEL
# 1→2: 100, 2→3: 200, ... 9→10: 900. Full 1→10: 4500.
COST_PER_LEVEL = 100

# Mission rewards by (difficulty, outcome)
_REWARD_TABLE: dict[tuple[str, str], dict] = {
    ("low",    "success"): {"currency": (50,  100), "tokens": 1},
    ("medium", "success"): {"currency": (100, 200), "tokens": 2},
    ("high",   "success"): {"currency": (200, 400), "tokens": 3},
    ("low",    "partial"):  {"currency": (25,  50),  "tokens": 0},
    ("medium", "partial"):  {"currency": (50,  100), "tokens": 1},
    ("high",   "partial"):  {"currency": (100, 200), "tokens": 1},
    ("low",    "failure"):  {"currency": (10,  25),  "tokens": 0},
    ("medium", "failure"):  {"currency": (20,  40),  "tokens": 0},
    ("high",   "failure"):  {"currency": (30,  60),  "tokens": 0},
}


@dataclass
class PlayerStats:
    combat:     int = STAT_MIN
    stealth:    int = STAT_MIN
    persuasion: int = STAT_MIN
    intellect:  int = STAT_MIN
    endurance:  int = STAT_MIN
    luck:       int = STAT_MIN

    def get(self, stat: str) -> int:
        if stat not in STAT_KEYS:
            raise ValueError(f"Unknown stat '{stat}'. Valid: {STAT_KEYS}")
        return getattr(self, stat)

    def upgrade_cost(self, stat: str) -> int:
        return self.get(stat) * COST_PER_LEVEL

    def can_upgrade(self, stat: str) -> bool:
        return self.get(stat) < STAT_MAX

    def upgrade(self, stat: str) -> int:
        """Raise stat by 1. Returns new level. Caller must deduct cost first."""
        if not self.can_upgrade(stat):
            raise ValueError(f"'{stat}' is already at max level {STAT_MAX}.")
        new_val = self.get(stat) + 1
        setattr(self, stat, new_val)
        return new_val

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in STAT_KEYS}

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerStats":
        return cls(**{k: data.get(k, STAT_MIN) for k in STAT_KEYS})

    def with_flavors(self, stat_flavors: dict[str, str]) -> dict:
        """Returns stats keyed by canonical name, with display name included."""
        return {
            key: {
                "level": getattr(self, key),
                "max": STAT_MAX,
                "display_name": stat_flavors.get(key, key.title()),
                "upgrade_cost": self.upgrade_cost(key) if self.can_upgrade(key) else None,
                "at_max": not self.can_upgrade(key),
            }
            for key in STAT_KEYS
        }


@dataclass
class PlayerInventory:
    currency: float = 0.0
    faction_tokens: dict[str, int] = field(default_factory=dict)
    currency_name: str = "gold"  # set from world on initialize

    def earn_currency(self, amount: float) -> None:
        self.currency += amount

    def spend_currency(self, amount: float) -> bool:
        if self.currency < amount:
            return False
        self.currency -= amount
        return True

    def earn_faction_token(self, faction: str, amount: int = 1) -> None:
        self.faction_tokens[faction] = self.faction_tokens.get(faction, 0) + amount

    def spend_faction_token(self, faction: str, amount: int = 1) -> bool:
        current = self.faction_tokens.get(faction, 0)
        if current < amount:
            return False
        self.faction_tokens[faction] = current - amount
        return True

    def to_dict(self) -> dict:
        return {
            "currency": round(self.currency, 2),
            "currency_name": self.currency_name,
            "faction_tokens": dict(self.faction_tokens),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerInventory":
        inv = cls(
            currency=data.get("currency", 0.0),
            currency_name=data.get("currency_name", "gold"),
        )
        inv.faction_tokens = data.get("faction_tokens", {})
        return inv


def calculate_mission_reward(
    difficulty: str,
    outcome: str,
    giver_faction: str,
) -> dict:
    """
    Calculate rewards for a completed mission.
    Returns a reward dict — caller decides whether to apply it.
    """
    key = (difficulty, outcome)
    table = _REWARD_TABLE.get(key, {"currency": (20, 40), "tokens": 0})

    currency_min, currency_max = table["currency"]
    currency_earned = random.randint(currency_min, currency_max)
    tokens_earned = table["tokens"]

    return {
        "currency": currency_earned,
        "faction_tokens": {giver_faction: tokens_earned} if tokens_earned > 0 and giver_faction else {},
    }


def apply_reward(inventory: PlayerInventory, reward: dict) -> None:
    inventory.earn_currency(reward["currency"])
    for faction, amount in reward.get("faction_tokens", {}).items():
        inventory.earn_faction_token(faction, amount)
