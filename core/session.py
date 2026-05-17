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
from core.preferences import WorldPreferences
from core.world_state import WorldState


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

    def npc_history(self, npc_id: str) -> NPCHistory:
        if npc_id not in self.npc_histories:
            self.npc_histories[npc_id] = NPCHistory()
        return self.npc_histories[npc_id]

    def find_mission(self, mission_id: str) -> Optional[dict]:
        return next((m for m in self.mission_pool if m["id"] == mission_id), None)


_store: dict[str, GameSession] = {}


def get(session_id: str) -> GameSession:
    if session_id not in _store:
        _store[session_id] = GameSession()
    return _store[session_id]


def exists(session_id: str) -> bool:
    return session_id in _store
