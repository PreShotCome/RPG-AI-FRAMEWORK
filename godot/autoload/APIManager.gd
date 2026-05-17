extends Node

## Central HTTP layer. Every backend call goes through here.
## Add this as an autoload named "APIManager" in Project → Project Settings → Autoload.

const BASE_URL := "http://localhost:8000"

signal error_occurred(code: int, message: String)

# ── Internal HTTP helper ──────────────────────────────────────────────────────

func _request(method: int, endpoint: String, body: Dictionary = {}) -> Variant:
	var http := HTTPRequest.new()
	add_child(http)

	var headers := ["Content-Type: application/json", "Accept: application/json"]
	var body_str := JSON.stringify(body) if not body.is_empty() else ""

	var err := http.request(BASE_URL + endpoint, headers, method, body_str)
	if err != OK:
		http.queue_free()
		push_error("APIManager: failed to send request to %s (err %d)" % [endpoint, err])
		return null

	var result: Array = await http.request_completed
	http.queue_free()

	var response_code: int = result[1]
	var raw: String = (result[3] as PackedByteArray).get_string_from_utf8()

	if response_code < 200 or response_code >= 300:
		push_error("APIManager: %s returned %d — %s" % [endpoint, response_code, raw])
		error_occurred.emit(response_code, raw)
		return null

	return JSON.parse_string(raw)


func _api_get(endpoint: String) -> Variant:
	return await _request(HTTPClient.METHOD_GET, endpoint)


func _api_post(endpoint: String, body: Dictionary = {}) -> Variant:
	return await _request(HTTPClient.METHOD_POST, endpoint, body)


# ── Onboarding ────────────────────────────────────────────────────────────────

func onboarding_start() -> Variant:
	return await _api_post("/onboarding/start")


func onboarding_respond(session_id: String, message: String) -> Variant:
	return await _api_post("/onboarding/%s/respond" % session_id, {"message": message})


func onboarding_generate_options(session_id: String) -> Variant:
	return await _api_post("/onboarding/%s/generate-options" % session_id)


func onboarding_choose(session_id: String, choice: String) -> Variant:
	return await _api_post("/onboarding/%s/choose" % session_id, {"choice": choice})


# ── World ─────────────────────────────────────────────────────────────────────

func get_world(session_id: String) -> Variant:
	return await _api_get("/world/%s" % session_id)


# ── Missions ──────────────────────────────────────────────────────────────────

func generate_missions(session_id: String, pool_size: int = 4) -> Variant:
	return await _api_post("/missions/%s/generate" % session_id, {"pool_size": pool_size})


func complete_mission(session_id: String, mission_id: String, outcome: String, approach: String, notes: String = "") -> Variant:
	var body := {
		"mission_id": mission_id,
		"outcome": outcome,
		"approach_used": approach,
	}
	if not notes.is_empty():
		body["notes"] = notes
	return await _api_post("/missions/%s/complete" % session_id, body)


func get_missions(session_id: String) -> Variant:
	return await _api_get("/missions/%s" % session_id)


# ── NPCs ──────────────────────────────────────────────────────────────────────

func spawn_npc(session_id: String, role: String, faction: String = "independent", region: String = "", context_hint: String = "") -> Variant:
	var body := {"role": role, "faction": faction}
	if not region.is_empty():
		body["region"] = region
	if not context_hint.is_empty():
		body["context_hint"] = context_hint
	return await _api_post("/npcs/%s/spawn" % session_id, body)


func talk_to_npc(session_id: String, npc_id: String, message: String, update_profile: bool = true) -> Variant:
	return await _api_post("/npcs/%s/%s/talk" % [session_id, npc_id], {
		"message": message,
		"update_profile": update_profile,
	})


func get_npcs(session_id: String) -> Variant:
	return await _api_get("/npcs/%s" % session_id)


# ── Events ────────────────────────────────────────────────────────────────────

func tick_events(session_id: String) -> Variant:
	return await _api_post("/events/%s/tick" % session_id)


func respond_to_event(session_id: String, event_id: String, option_id: String, approach: String) -> Variant:
	return await _api_post("/events/%s/respond" % session_id, {
		"event_id": event_id,
		"option_id": option_id,
		"approach": approach,
	})


func get_events(session_id: String) -> Variant:
	return await _api_get("/events/%s" % session_id)


# ── Lore ──────────────────────────────────────────────────────────────────────

func discover_lore(session_id: String, trigger: String, context: String, region: String = "", faction: String = "") -> Variant:
	var body := {"trigger": trigger, "context": context}
	if not region.is_empty():
		body["region"] = region
	if not faction.is_empty():
		body["faction"] = faction
	return await _api_post("/lore/%s/discover" % session_id, body)


func get_lore(session_id: String) -> Variant:
	return await _api_get("/lore/%s" % session_id)


# ── Resources ─────────────────────────────────────────────────────────────────

func get_resources(session_id: String) -> Variant:
	return await _api_get("/resources/%s" % session_id)


# ── Mirror ────────────────────────────────────────────────────────────────────

func generate_mirror(session_id: String) -> Variant:
	return await _api_post("/mirror/%s" % session_id)


func get_latest_mirror(session_id: String) -> Variant:
	return await _api_get("/mirror/%s/latest" % session_id)


# ── Saves ─────────────────────────────────────────────────────────────────────

func save_game(session_id: String, slot: String) -> Variant:
	return await _api_post("/saves/%s/save" % session_id, {"slot": slot})


func load_game(session_id: String, slot: String) -> Variant:
	return await _api_post("/saves/%s/load" % session_id, {"slot": slot})


func advance_day(session_id: String) -> Variant:
	return await _api_post("/saves/%s/advance-day" % session_id)


# ── Profile ───────────────────────────────────────────────────────────────────

func get_profile(session_id: String) -> Variant:
	return await _api_get("/profile/%s" % session_id)


func reset_profile(session_id: String, method: String) -> Variant:
	return await _api_post("/profile/%s/reset" % session_id, {
		"method": method,
		"confirmed": true,
	})
