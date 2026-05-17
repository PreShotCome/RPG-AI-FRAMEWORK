extends Node

## Lightweight data bus for passing world options between onboarding scenes.
## Add as autoload named "_WorldTransfer".

var options: Array = []
var facility_message: String = ""

func clear() -> void:
	options = []
	facility_message = ""
