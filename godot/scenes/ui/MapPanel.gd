extends PanelContainer

@onready var close_btn: Button = $VBox/HeaderRow/CloseButton
@onready var world_name_label: Label = $VBox/WorldNameLabel
@onready var tone_label: Label = $VBox/ToneLabel
@onready var regions_list: VBoxContainer = $VBox/RegionsScroll/RegionsList
@onready var factions_list: VBoxContainer = $VBox/FactionsList

func _ready() -> void:
	hide()
	close_btn.pressed.connect(hide)


func load_map() -> void:
	_rebuild()
	show()


func _rebuild() -> void:
	var world: Dictionary = GameState.world

	world_name_label.text = GameState.world_name
	tone_label.text = world.get("tone", "")

	# Regions
	for child in regions_list.get_children():
		child.queue_free()

	var ws = GameState.world_state
	var regions: Array = world.get("regions", [])
	for region in regions:
		var rname: String = region.get("name", "?")
		var rdesc: String = region.get("description", "")

		var tension: float = 0.0
		if ws and ws.has_method("region_tension"):
			tension = ws.region_tension(rname)

		var container := VBoxContainer.new()
		container.add_theme_constant_override("separation", 2)

		var name_label := Label.new()
		name_label.text = "◈  %s" % rname
		name_label.add_theme_color_override("font_color", _tension_color(tension))
		name_label.add_theme_font_size_override("font_size", 13)

		var desc_label := Label.new()
		desc_label.text = rdesc
		desc_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		desc_label.add_theme_color_override("font_color", Color(0.6, 0.62, 0.7))
		desc_label.add_theme_font_size_override("font_size", 11)

		container.add_child(name_label)
		container.add_child(desc_label)
		regions_list.add_child(container)

	# Factions
	for child in factions_list.get_children():
		child.queue_free()

	var factions: Array = world.get("factions", [])
	for faction in factions:
		var fname: String = faction.get("name", "?")
		var fdesc: String = faction.get("description", "")

		var row := Label.new()
		row.text = "▸ %s — %s" % [fname, fdesc]
		row.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		row.add_theme_color_override("font_color", Color(0.75, 0.72, 0.62))
		row.add_theme_font_size_override("font_size", 11)
		factions_list.add_child(row)


func _tension_color(tension: float) -> Color:
	if tension > 0.7:
		return Color(0.9, 0.35, 0.35)
	if tension > 0.4:
		return Color(0.9, 0.75, 0.35)
	return Color(0.35, 0.85, 0.55)
