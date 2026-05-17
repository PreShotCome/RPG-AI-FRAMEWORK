extends Control

const TYPEWRITER_SPEED := 0.018

@onready var world_label: Label = $Layout/VBox/TopBar/WorldLabel
@onready var day_label: Label = $Layout/VBox/TopBar/DayLabel
@onready var companion_label: Label = $Layout/VBox/TopBar/CompanionLabel
@onready var narrative_scroll: ScrollContainer = $Layout/VBox/NarrativeScroll
@onready var narrative_log: VBoxContainer = $Layout/VBox/NarrativeScroll/NarrativeLog
@onready var missions_btn: Button = $Layout/VBox/BottomBar/MissionsBtn
@onready var talk_btn: Button = $Layout/VBox/BottomBar/TalkBtn
@onready var events_btn: Button = $Layout/VBox/BottomBar/EventsBtn
@onready var stats_btn: Button = $Layout/VBox/BottomBar/StatsBtn
@onready var map_btn: Button = $Layout/VBox/BottomBar/MapBtn
@onready var advance_btn: Button = $Layout/VBox/BottomBar/AdvanceDayBtn

@onready var mission_panel = $MissionPanel
@onready var npc_roster = $NPCRoster
@onready var npc_panel = $NPCPanel
@onready var event_panel = $EventPanel
@onready var stats_panel = $StatsPanel
@onready var map_panel = $MapPanel

# NPCRoster sub-nodes
@onready var roster_list: VBoxContainer = $NPCRoster/VBox/RosterScroll/RosterList
@onready var roster_role_input: LineEdit = $NPCRoster/VBox/SpawnRow/RoleInput
@onready var roster_spawn_btn: Button = $NPCRoster/VBox/SpawnRow/SpawnBtn
@onready var roster_close_btn: Button = $NPCRoster/VBox/RosterHeader/CloseButton

var _busy: bool = false

func _ready() -> void:
	if GameState.session_id.is_empty():
		get_tree().change_scene_to_file("res://scenes/onboarding/ArchitectScreen.tscn")
		return

	missions_btn.pressed.connect(_open_missions)
	talk_btn.pressed.connect(_open_talk)
	events_btn.pressed.connect(_open_events)
	stats_btn.pressed.connect(_open_stats)
	map_btn.pressed.connect(_open_map)
	advance_btn.pressed.connect(_advance_day)

	roster_spawn_btn.pressed.connect(_spawn_npc)
	roster_close_btn.pressed.connect(func(): npc_roster.visible = false)

	_close_all()
	companion_label.text = "⬡ companion: localhost:8000/companion/%s" % GameState.session_id

	await _init_world()


func _init_world() -> void:
	_set_busy(true)

	var world = GameState.world
	if world.is_empty():
		var wd = await APIManager.get_world(GameState.session_id)
		if wd:
			GameState.world = wd.get("world", wd)
			GameState.apply_world_choice({"world": GameState.world, "archetype": GameState.archetype})

	_refresh_header()

	var world_name := GameState.world_name
	var setting: String = GameState.world.get("setting", "")
	var opening: String = GameState.world.get("starting_context", {}).get("opening_scene", "")

	await _print("[ %s ]" % world_name.to_upper(), "header")
	if not setting.is_empty():
		await _print(setting, "lore")
	if not opening.is_empty():
		await _print(opening, "narrative")

	await _print("— All systems nominal. —", "system")
	_set_busy(false)


func _refresh_header() -> void:
	world_label.text = GameState.world_name if not GameState.world_name.is_empty() else "UNKNOWN SECTOR"
	day_label.text = "DAY %d" % GameState.in_game_day


# ── Typewriter ─────────────────────────────────────────────────────────────────

func _print(text: String, style: String = "narrative") -> void:
	var label := Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.text = ""
	match style:
		"header":
			label.add_theme_color_override("font_color", Color(0.29, 0.62, 1.0))
			label.add_theme_font_size_override("font_size", 15)
		"system":
			label.add_theme_color_override("font_color", Color(0.35, 0.38, 0.48))
			label.add_theme_font_size_override("font_size", 11)
		"lore":
			label.add_theme_color_override("font_color", Color(0.55, 0.55, 0.72))
			label.add_theme_font_size_override("font_size", 12)
		"result":
			label.add_theme_color_override("font_color", Color(0.3, 0.75, 0.5))
			label.add_theme_font_size_override("font_size", 13)
		"warning":
			label.add_theme_color_override("font_color", Color(0.88, 0.56, 0.31))
			label.add_theme_font_size_override("font_size", 13)
		_:
			label.add_theme_color_override("font_color", Color(0.82, 0.83, 0.89))
			label.add_theme_font_size_override("font_size", 13)

	narrative_log.add_child(label)

	for i in text.length():
		label.text = text.substr(0, i + 1)
		if i % 4 == 0:
			await get_tree().process_frame
			narrative_scroll.scroll_vertical = narrative_scroll.get_v_scroll_bar().max_value
		await get_tree().create_timer(TYPEWRITER_SPEED).timeout

	await get_tree().process_frame
	narrative_scroll.scroll_vertical = narrative_scroll.get_v_scroll_bar().max_value


# ── Panel control ──────────────────────────────────────────────────────────────

func _close_all() -> void:
	mission_panel.visible = false
	npc_roster.visible = false
	npc_panel.visible = false
	event_panel.visible = false
	stats_panel.visible = false
	map_panel.visible = false


func _set_busy(busy: bool) -> void:
	_busy = busy
	for btn in [missions_btn, talk_btn, events_btn, stats_btn, map_btn, advance_btn]:
		btn.disabled = busy


# ── Bottom bar actions ─────────────────────────────────────────────────────────

func _open_missions() -> void:
	if _busy: return
	_close_all()
	mission_panel.visible = true
	mission_panel.load_missions()


func _open_talk() -> void:
	if _busy: return
	_close_all()
	_populate_roster()
	npc_roster.visible = true


func _open_events() -> void:
	if _busy: return
	_close_all()
	event_panel.visible = true
	event_panel.load_events()


func _open_stats() -> void:
	if _busy: return
	_close_all()
	stats_panel.visible = true
	stats_panel.load_stats()


func _open_map() -> void:
	if _busy: return
	_close_all()
	map_panel.visible = true
	map_panel.load_map()


func _advance_day() -> void:
	if _busy: return
	_set_busy(true)
	_close_all()
	await _print("[ Advancing day... ]", "system")
	var result = await APIManager.advance_day(GameState.session_id)
	if result:
		GameState.in_game_day = result.get("in_game_day", GameState.in_game_day)
		_refresh_header()
		var summary: String = result.get("day_summary", "")
		if not summary.is_empty():
			await _print(summary, "narrative")
		else:
			await _print("The void counts another rotation. You endure.", "narrative")
	_set_busy(false)


# ── NPC Roster ─────────────────────────────────────────────────────────────────

func _populate_roster() -> void:
	for child in roster_list.get_children():
		child.queue_free()

	var npcs = GameState.npc_registry.values()
	if npcs.is_empty():
		var hint := Label.new()
		hint.text = "No contacts yet. Spawn one below."
		hint.add_theme_color_override("font_color", Color(0.45, 0.45, 0.55))
		roster_list.add_child(hint)
	else:
		for npc in npcs:
			var btn := Button.new()
			btn.text = "%s  ·  %s  [%s]" % [npc.get("name","?"), npc.get("role","?"), npc.get("faction","?")]
			btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
			btn.pressed.connect(func(): _open_npc_dialogue(npc))
			roster_list.add_child(btn)


func _spawn_npc() -> void:
	var role := roster_role_input.text.strip_edges()
	if role.is_empty():
		roster_role_input.placeholder_text = "Enter a role first."
		return
	roster_spawn_btn.disabled = true
	roster_spawn_btn.text = "SCANNING..."

	var data = await APIManager.spawn_npc(GameState.session_id, role)
	roster_spawn_btn.disabled = false
	roster_spawn_btn.text = "MAKE CONTACT"

	if data == null: return
	var npc: Dictionary = data.get("npc", data)
	GameState.register_npc(npc)
	roster_role_input.clear()
	_open_npc_dialogue(npc)


func _open_npc_dialogue(npc: Dictionary) -> void:
	npc_roster.visible = false
	npc_panel.visible = true
	npc_panel.open(npc)


# ── Called by panels to surface narrative text ─────────────────────────────────

func push_narrative(text: String, style: String = "narrative") -> void:
	_print(text, style)
