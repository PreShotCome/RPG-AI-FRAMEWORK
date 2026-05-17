extends PanelContainer

## Mission board panel. Shows current pool; lets player complete a mission.
##
## Scene tree expected:
##   MissionPanel (PanelContainer)
##   ├── VBoxContainer
##   │   ├── HeaderRow (HBoxContainer)
##   │   │   ├── Title (Label — "MISSIONS")
##   │   │   └── CloseButton (Button — "✕")
##   │   ├── MissionList (VBoxContainer — populated dynamically)
##   │   └── CompletionSection (VBoxContainer — shown when a mission is selected)
##   │       ├── SelectedTitle (Label)
##   │       ├── ApproachInput (LineEdit — "How did you do it?")
##   │       ├── OutcomeRow (HBoxContainer)
##   │       │   ├── SuccessBtn (Button — "SUCCESS")
##   │       │   ├── PartialBtn (Button — "PARTIAL")
##   │       │   └── FailureBtn (Button — "FAILURE")
##   │       └── CompleteButton (Button — "COMPLETE MISSION")

@onready var mission_list: VBoxContainer = $VBoxContainer/MissionList
@onready var completion_section: VBoxContainer = $VBoxContainer/CompletionSection
@onready var selected_title: Label = $VBoxContainer/CompletionSection/SelectedTitle
@onready var approach_input: LineEdit = $VBoxContainer/CompletionSection/ApproachInput
@onready var complete_btn: Button = $VBoxContainer/CompletionSection/CompleteButton
@onready var close_btn: Button = $VBoxContainer/HeaderRow/CloseButton

var _selected_mission: Dictionary = {}
var _selected_outcome: String = "success"
var _completing := false

func _ready() -> void:
	hide()
	completion_section.hide()
	close_btn.pressed.connect(hide)

	$VBoxContainer/CompletionSection/OutcomeRow/SuccessBtn.pressed.connect(func(): _set_outcome("success"))
	$VBoxContainer/CompletionSection/OutcomeRow/PartialBtn.pressed.connect(func(): _set_outcome("partial"))
	$VBoxContainer/CompletionSection/OutcomeRow/FailureBtn.pressed.connect(func(): _set_outcome("failure"))
	complete_btn.pressed.connect(_complete_mission)


func show_missions(pool: Array) -> void:
	_clear_list()
	completion_section.hide()
	_selected_mission = {}

	for mission in pool:
		var btn := Button.new()
		btn.text = "[%s] %s" % [mission.get("type", "?").to_upper(), mission.get("title", "")]
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.add_theme_color_override("font_color", _difficulty_color(mission.get("difficulty", "medium")))
		btn.pressed.connect(func(): _select_mission(mission))
		mission_list.add_child(btn)

	show()


func _select_mission(mission: Dictionary) -> void:
	_selected_mission = mission
	selected_title.text = mission.get("title", "")
	approach_input.clear()
	approach_input.placeholder_text = "Describe your approach..."
	completion_section.show()
	approach_input.grab_focus()


func _set_outcome(outcome: String) -> void:
	_selected_outcome = outcome


func _complete_mission() -> void:
	if _completing or _selected_mission.is_empty():
		return

	var approach := approach_input.text.strip_edges()
	if approach.is_empty():
		approach_input.placeholder_text = "You need to describe your approach."
		return

	_completing = true
	complete_btn.disabled = true
	complete_btn.text = "COMPLETING..."

	var data = await APIManager.complete_mission(
		GameState.session_id,
		_selected_mission["id"],
		_selected_outcome,
		approach,
	)

	_completing = false
	complete_btn.disabled = false
	complete_btn.text = "COMPLETE MISSION"

	if data == null:
		return

	GameState.apply_mission_result(data)

	# Refresh pool
	var pool_data = await APIManager.generate_missions(GameState.session_id)
	if pool_data:
		GameState.apply_missions(pool_data)
		show_missions(GameState.mission_pool)

	# Tick world events after mission completion
	var event_data = await APIManager.tick_events(GameState.session_id)
	if event_data:
		GameState.apply_events(event_data)


func _clear_list() -> void:
	for child in mission_list.get_children():
		child.queue_free()


func _difficulty_color(difficulty: String) -> Color:
	match difficulty:
		"low":    return Color(0.5, 0.9, 0.5)
		"high":   return Color(0.9, 0.4, 0.4)
		_:        return Color(0.9, 0.85, 0.5)
