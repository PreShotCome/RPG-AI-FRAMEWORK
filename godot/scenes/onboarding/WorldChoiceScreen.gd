extends Control

## World choice screen — the 4th wall moment.
## Shows two worlds side by side. Player picks one.
##
## Scene tree expected:
##   WorldChoiceScreen (Control, full rect)
##   ├── Background (ColorRect — very dark)
##   ├── VBoxContainer
##   │   ├── FacilityMessage (RichTextLabel — the Architect's reveal text)
##   │   └── WorldsContainer (HBoxContainer)
##   │       ├── WorldCardA (PanelContainer)
##   │       │   └── VBoxContainer
##   │       │       ├── LabelA (Label — "THE WORLD YOU DESCRIBED")
##   │       │       ├── NameA (Label — world name)
##   │       │       ├── TaglineA (Label)
##   │       │       ├── ToneA (Label)
##   │       │       ├── SettingA (Label — setting preview)
##   │       │       └── ChooseA (Button — "ENTER THIS WORLD")
##   │       └── WorldCardB (PanelContainer)
##   │           └── VBoxContainer
##   │               ├── LabelB (Label — "THE WORLD WE THINK YOU NEED")
##   │               ├── NameB (Label)
##   │               ├── TaglineB (Label)
##   │               ├── ToneB (Label)
##   │               ├── SettingB (Label)
##   │               └── ChooseB (Button — "ENTER THIS WORLD")

@onready var facility_message: RichTextLabel = $VBoxContainer/FacilityMessage
@onready var name_a: Label = $VBoxContainer/WorldsContainer/WorldCardA/VBoxContainer/NameA
@onready var tagline_a: Label = $VBoxContainer/WorldsContainer/WorldCardA/VBoxContainer/TaglineA
@onready var tone_a: Label = $VBoxContainer/WorldsContainer/WorldCardA/VBoxContainer/ToneA
@onready var setting_a: Label = $VBoxContainer/WorldsContainer/WorldCardA/VBoxContainer/SettingA
@onready var choose_a: Button = $VBoxContainer/WorldsContainer/WorldCardA/VBoxContainer/ChooseA

@onready var name_b: Label = $VBoxContainer/WorldsContainer/WorldCardB/VBoxContainer/NameB
@onready var tagline_b: Label = $VBoxContainer/WorldsContainer/WorldCardB/VBoxContainer/TaglineB
@onready var tone_b: Label = $VBoxContainer/WorldsContainer/WorldCardB/VBoxContainer/ToneB
@onready var setting_b: Label = $VBoxContainer/WorldsContainer/WorldCardB/VBoxContainer/SettingB
@onready var choose_b: Button = $VBoxContainer/WorldsContainer/WorldCardB/VBoxContainer/ChooseB

var _choosing := false

func _ready() -> void:
	var options: Array = _WorldTransfer.options
	var message: String = _WorldTransfer.facility_message

	if options.size() < 2:
		push_error("WorldChoiceScreen: no world options in _WorldTransfer")
		return

	facility_message.text = message

	var opt_a: Dictionary = options[0]
	var opt_b: Dictionary = options[1]

	name_a.text = opt_a.get("name", "World A")
	tagline_a.text = opt_a.get("tagline", "")
	tone_a.text = "Tone: " + opt_a.get("tone", "")
	setting_a.text = opt_a.get("setting_preview", "")

	name_b.text = opt_b.get("name", "World B")
	tagline_b.text = opt_b.get("tagline", "")
	tone_b.text = "Tone: " + opt_b.get("tone", "")
	setting_b.text = opt_b.get("setting_preview", "")

	choose_a.pressed.connect(func(): _choose("A"))
	choose_b.pressed.connect(func(): _choose("B"))


func _choose(choice: String) -> void:
	if _choosing:
		return
	_choosing = true
	choose_a.disabled = true
	choose_b.disabled = true

	var data = await APIManager.onboarding_choose(GameState.session_id, choice)

	if data == null:
		_choosing = false
		choose_a.disabled = false
		choose_b.disabled = false
		push_error("WorldChoiceScreen: choose request failed")
		return

	GameState.apply_world_choice(data)
	_WorldTransfer.clear()

	# Immediately pull resources so GameState has stats + inventory
	var resources = await APIManager.get_resources(GameState.session_id)
	if resources:
		GameState.apply_resources(resources)

	get_tree().change_scene_to_file("res://scenes/main/MainGame.tscn")
