extends PanelContainer

## World event panel. Shows active events and lets player choose a response.
##
## Scene tree expected:
##   EventPanel (PanelContainer)
##   ├── VBoxContainer
##   │   ├── Title (Label — "WORLD EVENT")
##   │   ├── EventTitle (Label — large)
##   │   ├── EventDescription (Label — wrapped)
##   │   ├── NarrativeHook (Label — italic, dimmer)
##   │   ├── OptionsContainer (VBoxContainer — option buttons go here)
##   │   ├── ApproachInput (LineEdit — "How do you do this?")
##   │   └── ConfirmButton (Button — "COMMIT")

@onready var event_title: Label = $VBoxContainer/EventTitle
@onready var event_description: Label = $VBoxContainer/EventDescription
@onready var narrative_hook: Label = $VBoxContainer/NarrativeHook
@onready var options_container: VBoxContainer = $VBoxContainer/OptionsContainer
@onready var approach_input: LineEdit = $VBoxContainer/ApproachInput
@onready var confirm_btn: Button = $VBoxContainer/ConfirmButton

var _current_event: Dictionary = {}
var _selected_option: Dictionary = {}
var _responding := false
var _event_queue: Array = []

func _ready() -> void:
	hide()
	approach_input.hide()
	confirm_btn.hide()
	confirm_btn.pressed.connect(_on_confirm)


func show_events(events: Array) -> void:
	_event_queue = events.duplicate()
	_show_next_event()


func _show_next_event() -> void:
	if _event_queue.is_empty():
		hide()
		return

	_current_event = _event_queue.pop_front()
	_selected_option = {}

	event_title.text = _current_event.get("title", "")
	event_description.text = _current_event.get("description", "")
	narrative_hook.text = _current_event.get("narrative_hook", "")

	_clear_options()
	approach_input.hide()
	confirm_btn.hide()

	var options: Array = _current_event.get("player_options", [])
	for option in options:
		var btn := Button.new()
		btn.text = "%s — %s" % [option.get("label", ""), option.get("description", "")]
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		btn.pressed.connect(func(): _select_option(option))
		options_container.add_child(btn)

	show()


func _select_option(option: Dictionary) -> void:
	_selected_option = option
	approach_input.clear()
	approach_input.placeholder_text = "How exactly do you do this?"
	approach_input.show()
	confirm_btn.show()
	approach_input.grab_focus()


func _on_confirm() -> void:
	if _responding or _selected_option.is_empty():
		return

	var approach := approach_input.text.strip_edges()
	if approach.is_empty():
		approach_input.placeholder_text = "Describe your approach."
		return

	_responding = true
	confirm_btn.disabled = true
	confirm_btn.text = "..."

	var data = await APIManager.respond_to_event(
		GameState.session_id,
		_current_event["id"],
		_selected_option["id"],
		approach,
	)

	_responding = false
	confirm_btn.disabled = false
	confirm_btn.text = "COMMIT"

	if data:
		GameState.apply_world_state(data.get("world_state", {}))

	_show_next_event()


func _clear_options() -> void:
	for child in options_container.get_children():
		child.queue_free()


func load_events() -> void:
	var label := Label.new()
	label.text = "[ scanning for anomalies... ]"
	label.add_theme_color_override("font_color", Color(0.4, 0.4, 0.5))
	options_container.add_child(label)

	var data = await APIManager.tick_events(GameState.session_id)
	label.queue_free()
	if data:
		GameState.apply_events(data)
	if GameState.active_events.is_empty():
		event_title.text = "All Quiet"
		event_description.text = "No anomalies detected in your sector."
		narrative_hook.text = ""
		_clear_options()
		show()
	else:
		show_events(GameState.active_events)
