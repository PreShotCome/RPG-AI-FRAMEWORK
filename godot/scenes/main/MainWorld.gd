extends Node3D

## Root of the main game world.
## Handles: initial mission fetch, event tick, and coordinating UI panels.
##
## Scene tree expected:
##   MainWorld (Node3D)
##   ├── Environment (WorldEnvironment)
##   ├── DirectionalLight3D
##   ├── Player (CharacterBody3D — res://scenes/main/Player.tscn)
##   ├── WorldUI (CanvasLayer)
##   │   ├── HUD (Control)
##   │   │   ├── WorldNameLabel (Label — top-left)
##   │   │   ├── DayLabel (Label — top-left below world name)
##   │   │   └── CurrencyLabel (Label — top-right)
##   │   ├── MissionPanel (res://scenes/ui/MissionPanel.tscn — hidden by default)
##   │   ├── DialoguePanel (res://scenes/ui/DialoguePanel.tscn — hidden by default)
##   │   ├── EventPanel (res://scenes/ui/EventPanel.tscn — hidden by default)
##   │   └── StatsPanel (res://scenes/ui/StatsPanel.tscn — hidden by default)

@onready var world_name_label: Label = $WorldUI/HUD/WorldNameLabel
@onready var day_label: Label = $WorldUI/HUD/DayLabel
@onready var currency_label: Label = $WorldUI/HUD/CurrencyLabel
@onready var mission_panel = $WorldUI/MissionPanel
@onready var dialogue_panel = $WorldUI/DialoguePanel
@onready var event_panel = $WorldUI/EventPanel

func _ready() -> void:
	_update_hud()
	GameState.resources_updated.connect(_on_resources_updated)
	GameState.world_state_updated.connect(func(_s): _update_hud())

	await _initial_load()


func _initial_load() -> void:
	# Generate starting mission pool
	var mission_data = await APIManager.generate_missions(GameState.session_id)
	if mission_data:
		GameState.apply_missions(mission_data)

	# Tick world events (may return nothing on a fresh start — that's fine)
	var event_data = await APIManager.tick_events(GameState.session_id)
	if event_data:
		GameState.apply_events(event_data)
		if GameState.active_events.size() > 0:
			event_panel.show_events(GameState.active_events)


func _update_hud() -> void:
	world_name_label.text = GameState.world_name
	day_label.text = "Day %d" % GameState.in_game_day
	var sym := GameState.currency_symbol
	currency_label.text = "%s %.0f" % [sym, GameState.currency]


func _on_resources_updated(_stats: Dictionary, _inventory: Dictionary) -> void:
	_update_hud()


# ── Called by Player or UI to open panels ────────────────────────────────────

func open_missions() -> void:
	mission_panel.show_missions(GameState.mission_pool)


func open_dialogue(npc_id: String) -> void:
	var npc: Dictionary = GameState.npc_registry.get(npc_id, {})
	if npc.is_empty():
		push_error("MainWorld: NPC %s not in registry" % npc_id)
		return
	dialogue_panel.open(npc)


func open_stats() -> void:
	$WorldUI/StatsPanel.show_stats()
