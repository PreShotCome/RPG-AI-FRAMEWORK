extends CharacterBody3D

const SPEED := 5.0
const JUMP_VELOCITY := 4.5
const MOUSE_SENSITIVITY := 0.002

@onready var camera: Camera3D = $Camera3D

var _mouse_captured := false

func _ready() -> void:
	_capture_mouse()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and _mouse_captured:
		rotate_y(-event.relative.x * MOUSE_SENSITIVITY)
		camera.rotate_x(-event.relative.y * MOUSE_SENSITIVITY)
		camera.rotation.x = clamp(camera.rotation.x, -deg_to_rad(80), deg_to_rad(80))

	if event.is_action_pressed("ui_cancel"):
		if _mouse_captured:
			_release_mouse()
		else:
			_capture_mouse()

	if event.is_action_pressed("interact"):
		_try_interact()

	if event.is_action_pressed("open_missions"):
		get_node("/root/MainWorld").open_missions()

	if event.is_action_pressed("open_stats"):
		get_node("/root/MainWorld").open_stats()


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta

	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = JUMP_VELOCITY

	if not _mouse_captured:
		return

	var input_dir := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var direction := (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()

	if direction:
		velocity.x = direction.x * SPEED
		velocity.z = direction.z * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0, SPEED)
		velocity.z = move_toward(velocity.z, 0, SPEED)

	move_and_slide()


func _try_interact() -> void:
	# Raycast forward from camera to detect NPCs
	var space := get_world_3d().direct_space_state
	var origin := camera.global_position
	var target := origin + (-camera.global_transform.basis.z * 3.0)
	var query := PhysicsRayQueryParameters3D.create(origin, target)
	var result := space.intersect_ray(query)

	if result and result.collider.has_meta("npc_id"):
		var npc_id: String = result.collider.get_meta("npc_id")
		get_node("/root/MainWorld").open_dialogue(npc_id)


func _capture_mouse() -> void:
	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	_mouse_captured = true


func _release_mouse() -> void:
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	_mouse_captured = false
