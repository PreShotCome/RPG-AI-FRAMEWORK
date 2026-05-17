extends PanelContainer

## NPC dialogue panel. Spawns the NPC on first open if needed.
##
## Scene tree expected:
##   DialoguePanel (PanelContainer)
##   ├── VBoxContainer
##   │   ├── HeaderRow (HBoxContainer)
##   │   │   ├── NPCNameLabel (Label)
##   │   │   ├── NPCRoleLabel (Label — smaller, dim)
##   │   │   └── CloseButton (Button — "✕")
##   │   ├── FactionLabel (Label — "Allied with X | Standing: Friendly")
##   │   ├── ScrollContainer
##   │   │   └── ConversationLog (VBoxContainer)
##   │   └── InputRow (HBoxContainer)
##   │       ├── PlayerInput (LineEdit)
##   │       └── SendButton (Button — "→")

@onready var npc_name_label: Label = $VBoxContainer/HeaderRow/NPCNameLabel
@onready var npc_role_label: Label = $VBoxContainer/HeaderRow/NPCRoleLabel
@onready var faction_label: Label = $VBoxContainer/FactionLabel
@onready var conversation_log: VBoxContainer = $VBoxContainer/ScrollContainer/ConversationLog
@onready var scroll_container: ScrollContainer = $VBoxContainer/ScrollContainer
@onready var player_input: LineEdit = $VBoxContainer/InputRow/PlayerInput
@onready var send_button: Button = $VBoxContainer/InputRow/SendButton
@onready var close_btn: Button = $VBoxContainer/HeaderRow/CloseButton

var _current_npc: Dictionary = {}
var _waiting := false

func _ready() -> void:
	hide()
	close_btn.pressed.connect(hide)
	send_button.pressed.connect(_on_send)
	player_input.text_submitted.connect(func(_t): _on_send())


func open(npc: Dictionary) -> void:
	_current_npc = npc
	_clear_log()

	npc_name_label.text = npc.get("name", "Unknown")
	npc_role_label.text = npc.get("role", "")

	var faction := npc.get("faction", "independent")
	faction_label.text = "Faction: %s" % faction

	show()
	player_input.grab_focus()

	# Show opening line if available
	var opening := npc.get("opening_line", "")
	if not opening.is_empty():
		_add_npc_message(opening)


func _on_send() -> void:
	var text := player_input.text.strip_edges()
	if text.is_empty() or _waiting or _current_npc.is_empty():
		return

	player_input.clear()
	_add_player_message(text)
	_set_waiting(true)

	var data = await APIManager.talk_to_npc(
		GameState.session_id,
		_current_npc["id"],
		text,
	)

	_set_waiting(false)

	if data == null:
		_add_system_message("[connection error]")
		return

	_add_npc_message(data["reply"])

	# Update faction standing display
	var standing: Dictionary = data.get("standing", {})
	if not standing.is_empty():
		faction_label.text = "Faction: %s | %s (%+.0f)" % [
			standing.get("faction", ""),
			standing.get("label", ""),
			standing.get("value", 0.0),
		]


# ── Message builders ──────────────────────────────────────────────────────────

func _add_npc_message(text: String) -> void:
	var row := _make_row(_current_npc.get("name", "NPC"), Color(0.7, 0.85, 1.0), text)
	conversation_log.add_child(row)
	_scroll_to_bottom()


func _add_player_message(text: String) -> void:
	var row := _make_row("YOU", Color(0.9, 0.9, 0.9), text)
	conversation_log.add_child(row)
	_scroll_to_bottom()


func _add_system_message(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
	conversation_log.add_child(label)
	_scroll_to_bottom()


func _make_row(speaker: String, color: Color, text: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)

	var tag := Label.new()
	tag.text = speaker
	tag.custom_minimum_size = Vector2(80, 0)
	tag.add_theme_color_override("font_color", color)
	tag.add_theme_font_size_override("font_size", 11)
	tag.vertical_alignment = VERTICAL_ALIGNMENT_TOP

	var content := Label.new()
	content.text = text
	content.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_color_override("font_color", Color(0.92, 0.92, 0.92))

	row.add_child(tag)
	row.add_child(content)
	return row


func _set_waiting(waiting: bool) -> void:
	_waiting = waiting
	player_input.editable = not waiting
	send_button.disabled = waiting
	if not waiting:
		player_input.grab_focus()


func _clear_log() -> void:
	for child in conversation_log.get_children():
		child.queue_free()


func _scroll_to_bottom() -> void:
	await get_tree().process_frame
	scroll_container.scroll_vertical = scroll_container.get_v_scroll_bar().max_value
