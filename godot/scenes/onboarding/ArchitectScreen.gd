extends Control

## The Architect intake facility.
## Attach to a Control node that fills the screen.
##
## Scene tree expected:
##   ArchitectScreen (Control, full rect)
##   ├── Background (ColorRect — dark, #0a0a0f)
##   ├── VBoxContainer
##   │   ├── HeaderLabel (Label — "ARCHITECT" in small caps, dim)
##   │   ├── ScrollContainer
##   │   │   └── ConversationLog (VBoxContainer — messages appear here)
##   │   └── InputRow (HBoxContainer)
##   │       ├── PlayerInput (LineEdit)
##   │       └── SendButton (Button — "→")
##   └── ReadyBanner (Panel — hidden by default, shown when ready)
##       └── ReadyLabel (Label)
##       └── GenerateButton (Button — "GENERATE WORLDS")

@onready var conversation_log: VBoxContainer = $VBoxContainer/ScrollContainer/ConversationLog
@onready var scroll_container: ScrollContainer = $VBoxContainer/ScrollContainer
@onready var player_input: LineEdit = $VBoxContainer/InputRow/PlayerInput
@onready var send_button: Button = $VBoxContainer/InputRow/SendButton
@onready var ready_banner: PanelContainer = $ReadyBanner
@onready var generate_button: Button = $ReadyBanner/VBoxContainer/GenerateButton

var _waiting := false
var _ready_to_generate := false

func _ready() -> void:
	ready_banner.hide()
	player_input.grab_focus()
	send_button.pressed.connect(_on_send)
	generate_button.pressed.connect(_on_generate)
	player_input.text_submitted.connect(func(_t): _on_send())

	_start_session()


func _start_session() -> void:
	_set_waiting(true)
	var data = await APIManager.onboarding_start()
	_set_waiting(false)

	if data == null:
		_add_system_message("CONNECTION FAILED. Is the backend running on localhost:8000?")
		return

	GameState.session_id = data["session_id"]
	GameState.onboarding_stage = "facility"

	_add_architect_message(data["message"])


func _on_send() -> void:
	var text := player_input.text.strip_edges()
	if text.is_empty() or _waiting:
		return

	player_input.clear()
	_add_player_message(text)
	_set_waiting(true)

	var data = await APIManager.onboarding_respond(GameState.session_id, text)
	_set_waiting(false)

	if data == null:
		_add_system_message("[error: no response from server]")
		return

	_add_architect_message(data["reply"])

	if data.get("ready", false) and not _ready_to_generate:
		_ready_to_generate = true
		ready_banner.show()


func _on_generate() -> void:
	if _waiting:
		return

	_set_waiting(true)
	generate_button.disabled = true
	generate_button.text = "BUILDING WORLDS..."
	_add_system_message("Crystallizing profile. Generating two worlds. This takes a moment.")

	var data = await APIManager.onboarding_generate_options(GameState.session_id)
	_set_waiting(false)

	if data == null:
		generate_button.disabled = false
		generate_button.text = "GENERATE WORLDS"
		_add_system_message("[error: world generation failed]")
		return

	GameState.onboarding_stage = "options"

	# Set transfer data BEFORE changing scene
	_WorldTransfer.options = data["options"]
	_WorldTransfer.facility_message = data["facility_message"]

	get_tree().change_scene_to_file("res://scenes/onboarding/WorldChoiceScreen.tscn")


# ── Message builders ──────────────────────────────────────────────────────────

func _add_architect_message(text: String) -> void:
	var label := _make_label(text, Color(0.85, 0.85, 0.95))
	label.add_theme_color_override("font_color", Color(0.85, 0.85, 0.95))
	var row := _make_row("ARCHITECT", Color(0.4, 0.4, 0.7), label)
	conversation_log.add_child(row)
	_scroll_to_bottom()


func _add_player_message(text: String) -> void:
	var label := _make_label(text, Color(0.95, 0.95, 0.95))
	var row := _make_row("YOU", Color(0.6, 0.6, 0.6), label)
	conversation_log.add_child(row)
	_scroll_to_bottom()


func _add_system_message(text: String) -> void:
	var label := _make_label(text, Color(0.5, 0.5, 0.5))
	label.add_theme_font_size_override("font_size", 11)
	conversation_log.add_child(label)
	_scroll_to_bottom()


func _make_label(text: String, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", color)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return label


func _make_row(speaker: String, speaker_color: Color, content: Label) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)

	var tag := Label.new()
	tag.text = speaker
	tag.custom_minimum_size = Vector2(90, 0)
	tag.add_theme_color_override("font_color", speaker_color)
	tag.add_theme_font_size_override("font_size", 11)
	tag.vertical_alignment = VERTICAL_ALIGNMENT_TOP

	row.add_child(tag)
	row.add_child(content)
	return row


func _set_waiting(waiting: bool) -> void:
	_waiting = waiting
	player_input.editable = not waiting
	send_button.disabled = waiting
	if not waiting:
		player_input.grab_focus()


func _scroll_to_bottom() -> void:
	await get_tree().process_frame
	scroll_container.scroll_vertical = scroll_container.get_v_scroll_bar().max_value
