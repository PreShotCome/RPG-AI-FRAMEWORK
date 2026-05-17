extends Node

## Global game state. Persists across scene changes.
## Add as autoload named "GameState" in Project → Project Settings → Autoload.

# ── Session ───────────────────────────────────────────────────────────────────

var session_id: String = ""
var onboarding_stage: String = "facility"   # "facility" | "options" | "complete"

# ── World ─────────────────────────────────────────────────────────────────────

var world: Dictionary = {}
var archetype: Dictionary = {}
var preferences: Dictionary = {}

# Quick accessors (populated after world is chosen)
var world_name: String:
	get: return world.get("name", "")

var currency_name: String:
	get: return world.get("currency", {}).get("name", "Gold")

var currency_symbol: String:
	get: return world.get("currency", {}).get("symbol", "G")

var stat_flavors: Dictionary:
	get: return world.get("stat_flavors", {})

# ── Player ────────────────────────────────────────────────────────────────────

var stats: Dictionary = {}
var inventory: Dictionary = {}
var profile: Dictionary = {}

# Convenience
var currency: float:
	get: return inventory.get("currency", 0.0)

var faction_tokens: Dictionary:
	get: return inventory.get("faction_tokens", {})

func stat(key: String) -> int:
	return stats.get(key, 1)

func stat_display_name(key: String) -> String:
	return stat_flavors.get(key, key.capitalize())

# ── Missions ──────────────────────────────────────────────────────────────────

var mission_pool: Array = []
var mission_history: Array = []

# ── NPCs ──────────────────────────────────────────────────────────────────────

var npc_registry: Dictionary = {}   # npc_id → npc dict

# ── Events ────────────────────────────────────────────────────────────────────

var active_events: Array = []

# ── World state snapshot ──────────────────────────────────────────────────────

var world_state: Dictionary = {}
var in_game_day: int = 1

# ── Signals (broadcast to any scene that cares) ───────────────────────────────

signal world_loaded(world: Dictionary)
signal resources_updated(stats: Dictionary, inventory: Dictionary)
signal missions_updated(pool: Array)
signal npc_spawned(npc: Dictionary)
signal active_events_updated(events: Array)
signal world_state_updated(state: Dictionary)

# ── Mutators ──────────────────────────────────────────────────────────────────

func apply_world_choice(data: Dictionary) -> void:
	world = data.get("world", {})
	archetype = data.get("archetype", {})
	onboarding_stage = "complete"
	world_loaded.emit(world)


func apply_resources(data: Dictionary) -> void:
	stats = data.get("stats", stats)
	inventory = data.get("inventory", inventory)
	resources_updated.emit(stats, inventory)


func apply_mission_result(data: Dictionary) -> void:
	if data.has("inventory"):
		inventory = data["inventory"]
	if data.has("reward"):
		pass  # reward already in inventory
	resources_updated.emit(stats, inventory)


func apply_missions(data: Dictionary) -> void:
	mission_pool = data.get("pool", [])
	if data.has("history"):
		mission_history = data["history"]
	if data.has("world_state"):
		world_state = data["world_state"]
		world_state_updated.emit(world_state)
	missions_updated.emit(mission_pool)


func apply_world_state(state: Dictionary) -> void:
	world_state = state
	world_state_updated.emit(world_state)


func register_npc(npc: Dictionary) -> void:
	npc_registry[npc["id"]] = npc
	npc_spawned.emit(npc)


func apply_events(data: Dictionary) -> void:
	active_events = data.get("active_events", [])
	if data.has("world_state"):
		apply_world_state(data["world_state"])
	active_events_updated.emit(active_events)


func has_world() -> bool:
	return not world.is_empty()


func clear() -> void:
	session_id = ""
	onboarding_stage = "facility"
	world = {}
	archetype = {}
	preferences = {}
	stats = {}
	inventory = {}
	profile = {}
	mission_pool = []
	mission_history = []
	npc_registry = {}
	active_events = []
	world_state = {}
	in_game_day = 1
