"""
Central in-memory session store.

Holds everything that belongs to a single playthrough:
  - the player's evolving profile (updates continuously, not just during training)
  - per-NPC conversation histories
  - world state (faction standings, regional tension — shifts with mission outcomes)
  - mission pool and history

Replace the dict with file/DB persistence when the save system is built.
"""

from dataclasses import dataclass, field
from typing import Optional
from core.profile import PlayerProfile
from core.preferences import WorldPreferences, GamerFocus
from core.world_state import WorldState
from core.resources import PlayerStats, PlayerInventory

DIFFICULTIES = ("casual", "regular", "hardcore")

# Which slots each tier can load from
LOAD_PERMISSIONS: dict[str, set[str]] = {
    "casual":   {"slot_1", "slot_2", "slot_3", "auto", "glitch"},
    "regular":  {"day_start", "auto", "glitch"},
    "hardcore": {"glitch"},
}

# Which slots each tier can write to
SAVE_PERMISSIONS: dict[str, set[str]] = {
    "casual":   {"slot_1", "slot_2", "slot_3", "auto", "glitch"},
    "regular":  {"day_start", "auto", "glitch"},
    "hardcore": {"auto", "glitch"},
}


@dataclass
class NPCHistory:
    messages: list[dict] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def to_claude_messages(self) -> list[dict]:
        return list(self.messages)


@dataclass
class GameSession:
    profile: PlayerProfile = field(default_factory=PlayerProfile)
    npc_histories: dict[str, NPCHistory] = field(default_factory=dict)
    preferences: WorldPreferences = field(default_factory=WorldPreferences)
    archetype: Optional[dict] = None
    generated_world: Optional[dict] = None
    world_state: WorldState = field(default_factory=WorldState)
    mission_pool: list[dict] = field(default_factory=list)
    mission_history: list[dict] = field(default_factory=list)
    npc_registry: dict[str, dict] = field(default_factory=dict)
    active_events: list[dict] = field(default_factory=list)
    event_log: list[dict] = field(default_factory=list)
    lore_discovered: list[dict] = field(default_factory=list)
    reset_history: list[dict] = field(default_factory=list)
    mirrors: list[dict] = field(default_factory=list)
    stats: PlayerStats = field(default_factory=PlayerStats)
    inventory: PlayerInventory = field(default_factory=PlayerInventory)
    resources_initialized: bool = False
    difficulty: str = "regular"
    world_name: str = ""
    in_game_day: int = 1

    def npc_history(self, npc_id: str) -> NPCHistory:
        if npc_id not in self.npc_histories:
            self.npc_histories[npc_id] = NPCHistory()
        return self.npc_histories[npc_id]

    def find_mission(self, mission_id: str) -> Optional[dict]:
        return next((m for m in self.mission_pool if m["id"] == mission_id), None)

    def to_dict(self) -> dict:
        return {
            "profile": self.profile.to_dict(),
            "npc_histories": {
                npc_id: h.messages for npc_id, h in self.npc_histories.items()
            },
            "preferences": self.preferences.to_dict(),
            "archetype": self.archetype,
            "generated_world": self.generated_world,
            "world_state": self.world_state.to_dict(),
            "mission_pool": self.mission_pool,
            "mission_history": self.mission_history,
            "npc_registry": self.npc_registry,
            "active_events": self.active_events,
            "event_log": self.event_log,
            "lore_discovered": self.lore_discovered,
            "reset_history": self.reset_history,
            "mirrors": self.mirrors,
            "stats": self.stats.to_dict(),
            "inventory": self.inventory.to_dict(),
            "resources_initialized": self.resources_initialized,
            "difficulty": self.difficulty,
            "world_name": self.world_name,
            "in_game_day": self.in_game_day,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameSession":
        session = cls()
        session.profile = PlayerProfile.from_dict(data["profile"])
        session.npc_histories = {
            npc_id: NPCHistory(messages=msgs)
            for npc_id, msgs in data.get("npc_histories", {}).items()
        }
        session.preferences = WorldPreferences.from_dict(data.get("preferences", {}))
        session.archetype = data.get("archetype")
        session.generated_world = data.get("generated_world")
        session.world_state = WorldState.from_dict(data.get("world_state", {}))
        session.mission_pool = data.get("mission_pool", [])
        session.mission_history = data.get("mission_history", [])
        session.npc_registry = data.get("npc_registry", {})
        session.active_events = data.get("active_events", [])
        session.event_log = data.get("event_log", [])
        session.lore_discovered = data.get("lore_discovered", [])
        session.reset_history = data.get("reset_history", [])
        session.mirrors = data.get("mirrors", [])
        session.stats = PlayerStats.from_dict(data.get("stats", {}))
        session.inventory = PlayerInventory.from_dict(data.get("inventory", {}))
        session.resources_initialized = data.get("resources_initialized", False)
        session.difficulty = data.get("difficulty", "regular")
        session.world_name = data.get("world_name", "")
        session.in_game_day = data.get("in_game_day", 1)
        return session


_store: dict[str, GameSession] = {}


def get(session_id: str) -> GameSession:
    if session_id not in _store:
        _store[session_id] = GameSession()
    return _store[session_id]


def exists(session_id: str) -> bool:
    return session_id in _store
