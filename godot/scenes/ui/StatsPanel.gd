extends PanelContainer

## Player stats and inventory panel.
##
## Scene tree expected:
##   StatsPanel (PanelContainer)
##   ├── VBoxContainer
##   │   ├── HeaderRow (HBoxContainer)
##   │   │   ├── Title (Label — "STATS & INVENTORY")
##   │   │   └── CloseButton (Button — "✕")
##   │   ├── CurrencyLabel (Label)
##   │   ├── StatsGrid (GridContainer — columns: 2)
##   │   └── FactionTokensContainer (VBoxContainer)

@onready var currency_label: Label = $VBoxContainer/CurrencyLabel
@onready var stats_grid: GridContainer = $VBoxContainer/StatsGrid
@onready var faction_tokens_container: VBoxContainer = $VBoxContainer/FactionTokensContainer
@onready var close_btn: Button = $VBoxContainer/HeaderRow/CloseButton

func _ready() -> void:
	hide()
	close_btn.pressed.connect(hide)
	GameState.resources_updated.connect(func(_s, _i): _refresh())


func show_stats() -> void:
	_refresh()
	show()


func _refresh() -> void:
	# Currency
	currency_label.text = "%s %.0f %s" % [
		GameState.currency_symbol,
		GameState.currency,
		GameState.currency_name,
	]

	# Stats grid — clear and rebuild
	for child in stats_grid.get_children():
		child.queue_free()

	var stat_keys := ["combat", "stealth", "persuasion", "intellect", "endurance", "luck"]
	for key in stat_keys:
		var display_name := GameState.stat_display_name(key)
		var level: int = GameState.stat(key)

		var name_label := Label.new()
		name_label.text = display_name
		name_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.9))

		var bar_label := Label.new()
		bar_label.text = "█".repeat(level) + "░".repeat(10 - level) + " %d" % level
		bar_label.add_theme_font_size_override("font_size", 11)

		stats_grid.add_child(name_label)
		stats_grid.add_child(bar_label)

	# Faction tokens
	for child in faction_tokens_container.get_children():
		child.queue_free()

	var tokens: Dictionary = GameState.faction_tokens
	if tokens.is_empty():
		var empty := Label.new()
		empty.text = "No faction tokens yet."
		empty.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
		faction_tokens_container.add_child(empty)
	else:
		for faction_name in tokens:
			var label := Label.new()
			label.text = "%s: %d tokens" % [faction_name, tokens[faction_name]]
			faction_tokens_container.add_child(label)
