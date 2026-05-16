import json
import os
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from core.player_profile import PlayerProfile

SAVES_DIR = Path("saves")

@dataclass
class SaveData:
    save_id: str
    world_seed: int
    created_at: float
    last_played: float
    profile: dict
    world_state: dict = field(default_factory=dict)
    active_missions: list = field(default_factory=list)
    completed_missions: list = field(default_factory=list)
    npc_dialogue_history: dict = field(default_factory=dict)
    current_area_id: str = "mill"
    campaign_act: int = 0

def _save_path(save_id: str) -> Path:
    return SAVES_DIR / f"{save_id}.json"

def generate_save_id() -> str:
    return hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]

def generate_world_seed(save_id: str) -> int:
    return int(hashlib.sha256(save_id.encode()).hexdigest(), 16) % (10**9)

def new_save() -> SaveData:
    save_id = generate_save_id()
    seed = generate_world_seed(save_id)
    profile = PlayerProfile(save_id=save_id)
    now = time.time()
    return SaveData(
        save_id=save_id,
        world_seed=seed,
        created_at=now,
        last_played=now,
        profile=profile.to_dict(),
    )

def save_game(save_data: SaveData) -> None:
    SAVES_DIR.mkdir(exist_ok=True)
    save_data.last_played = time.time()
    path = _save_path(save_data.save_id)
    with open(path, "w") as f:
        json.dump(asdict(save_data), f, indent=2)

def load_game(save_id: str) -> SaveData | None:
    path = _save_path(save_id)
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    return SaveData(**data)

def list_saves() -> list[dict]:
    SAVES_DIR.mkdir(exist_ok=True)
    saves = []
    for path in SAVES_DIR.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        profile = data.get("profile", {})
        saves.append({
            "save_id": data["save_id"],
            "world_seed": data["world_seed"],
            "level": profile.get("level", 1),
            "archetype": profile.get("archetype", ""),
            "last_played": data["last_played"],
            "checkpoint_reached": profile.get("checkpoint_reached", False),
        })
    return sorted(saves, key=lambda x: x["last_played"], reverse=True)

def delete_save(save_id: str) -> bool:
    path = _save_path(save_id)
    if path.exists():
        path.unlink()
        return True
    return False
