extends Node2D
## Game — the vertical-slice level: the ground floor of Cape Marrow Light.
## Builds the room, player, interactables, HUD prompt, dialogue box, and a
## pause overlay in code.

const DIALOGUE := "res://data/dialogue/keeper_intro.json"
const LAMP_ROOM_DIALOGUE := "res://data/dialogue/lamp_room.json"
const ENDINGS_DIALOGUE := "res://data/dialogue/endings.json"
const INTERACT_RADIUS := 90.0
const ROOM := Rect2(120, 140, 1040, 460)

var _player: Player
var _interactables: Array[Interactable] = []
var _prompt: Label
var _nearest: Interactable = null
var _paused: bool = false
var _pending_dialogue_transition: String = ""


func _ready() -> void:
	_build_room()
	_build_player()
	_build_interactables()
	_build_hud()

	var dialogue_box := preload("res://scenes/ui/dialogue_box.tscn").instantiate()
	add_child(dialogue_box)

	DialogueManager.dialogue_started.connect(func(): _set_movement(false))
	DialogueManager.dialogue_finished.connect(_on_dialogue_finished)


func _build_room() -> void:
	var bg := ColorRect.new()
	bg.color = Color("#0f1a22")
	bg.size = Vector2(1280, 720)
	add_child(bg)

	var floor_rect := ColorRect.new()
	floor_rect.color = Color("#1c2b34")
	floor_rect.position = ROOM.position
	floor_rect.size = ROOM.size
	add_child(floor_rect)

	var title := Label.new()
	title.text = "Cape Marrow Light — ground floor"
	title.position = Vector2(ROOM.position.x, ROOM.position.y - 34)
	title.modulate = Color(1, 1, 1, 0.5)
	add_child(title)


func _build_player() -> void:
	_player = Player.new()
	_player.bounds = ROOM.grow(-30)
	_player.position = Vector2(ROOM.position.x + ROOM.size.x * 0.5, ROOM.position.y + ROOM.size.y - 60)
	add_child(_player)

	var camera := Camera2D.new()
	camera.position_smoothing_enabled = true
	_player.add_child(camera)
	camera.make_current()


func _build_interactables() -> void:
	_add_interactable("Logbook", "Read the keeper's log", "logbook",
		Vector2(ROOM.position.x + 160, ROOM.position.y + 120), Color("#8a6f4b"))
	_add_interactable("Radio set", "Call the mainland", "radio",
		Vector2(ROOM.position.x + ROOM.size.x - 180, ROOM.position.y + 130), Color("#4b6f8a"))
	_add_interactable("Lamp-room stair", "Climb toward the light", "door",
		Vector2(ROOM.position.x + ROOM.size.x * 0.5, ROOM.position.y + 60), Color("#3a4a54"))


func _add_interactable(label: String, prompt: String, start_id: String, pos: Vector2, color: Color) -> void:
	var item := Interactable.new()
	item.label = label
	item.prompt_text = prompt
	item.dialogue_path = DIALOGUE
	item.dialogue_start = start_id
	item.color = color
	item.position = pos
	add_child(item)
	item.setup()
	item.interacted.connect(_on_interactable_interacted)
	_interactables.append(item)


func _on_dialogue_finished() -> void:
	_set_movement(true)

	match _pending_dialogue_transition:
		"lamp_room":
			_pending_dialogue_transition = "endings"
			if not DialogueManager.start(LAMP_ROOM_DIALOGUE, "start"):
				_pending_dialogue_transition = ""
				push_error("Game: could not start the lamp-room dialogue.")
		"endings":
			_pending_dialogue_transition = ""
			_start_ending_dialogue()
		_:
			_pending_dialogue_transition = ""


func _start_ending_dialogue() -> void:
	var is_believer := _read_boolean_flag("believer", false)
	var is_skeptic := _read_boolean_flag("skeptic", false)

	if is_believer and is_skeptic:
		push_warning("GameState: both 'believer' and 'skeptic' are true; defaulting to believer.")
		is_skeptic = false
		GameState.set_flag("skeptic", false)
	elif not is_believer and not is_skeptic:
		push_warning("GameState: neither 'believer' nor 'skeptic' is true; defaulting to skeptic.")
		is_believer = false
		is_skeptic = true
		GameState.set_flag("believer", false)
		GameState.set_flag("skeptic", true)

	var trusted_edith := _read_boolean_flag("trusted_edith", false, true)
	var radioed_tom := _read_boolean_flag("radioed_tom", false)

	# The belief/trust pair chooses one of exactly four leaves.
	# radioed_tom changes only the epilogue entry variant, never the ending.
	var ending_number := 4
	if is_believer:
		ending_number = 1 if trusted_edith else 2
	else:
		ending_number = 3 if trusted_edith else 4

	var epilogue_variant := "tom" if radioed_tom else "silent"
	var entry_id := "ending_%d_%s" % [ending_number, epilogue_variant]
	if not DialogueManager.start(ENDINGS_DIALOGUE, entry_id):
		push_error("Game: could not start ending dialogue at '%s'." % entry_id)


func _read_boolean_flag(flag_name: String, default_value: bool, warn_if_missing: bool = false) -> bool:
	if not GameState.flags.has(flag_name):
		if warn_if_missing:
			push_warning("GameState: flag '%s' is missing; defaulting to %s." % [flag_name, str(default_value)])
			GameState.set_flag(flag_name, default_value)
		return default_value

	var stored_value: Variant = GameState.get_flag(flag_name, default_value)
	if typeof(stored_value) != TYPE_BOOL:
		push_warning("GameState: flag '%s' is not Boolean; defaulting to %s." % [flag_name, str(default_value)])
		GameState.set_flag(flag_name, default_value)
		return default_value

	return bool(stored_value)


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)

	_prompt = Label.new()
	_prompt.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_prompt.offset_top = -70
	_prompt.offset_left = -200
	_prompt.offset_right = 200
	_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_prompt.add_theme_font_size_override("font_size", 20)
	_prompt.modulate = Color("#ffd466")
	_prompt.hide()
	layer.add_child(_prompt)


func _process(_delta: float) -> void:
	if _paused or DialogueManager.is_active:
		_prompt.hide()
		return
	_nearest = _find_nearest()
	if _nearest != null:
		_prompt.text = "[ Enter ] %s" % _nearest.prompt_text
		_prompt.show()
	else:
		_prompt.hide()


func _find_nearest() -> Interactable:
	var best: Interactable = null
	var best_dist := INTERACT_RADIUS
	for item in _interactables:
		if not item.can_interact():
			continue
		var dist := _player.position.distance_to(item.position)
		if dist <= best_dist:
			best_dist = dist
			best = item
	return best


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		_toggle_pause()
		get_viewport().set_input_as_handled()
		return
	if _paused or DialogueManager.is_active:
		return
	if event.is_action_pressed("ui_accept") and _nearest != null:
		var interacted_item := _nearest
		interacted_item.interact()
		# Mark the transition only if the door dialogue actually started.
		_pending_dialogue_transition = "lamp_room" if interacted_item.dialogue_path == DIALOGUE and interacted_item.dialogue_start == "door" and DialogueManager.is_active else ""
		get_viewport().set_input_as_handled()


func _set_movement(enabled: bool) -> void:
	if _player != null:
		_player.can_move = enabled and not _paused


func _toggle_pause() -> void:
	if DialogueManager.is_active:
		return
	_paused = not _paused
	_set_movement(not _paused)
	if _paused:
		_show_pause_menu()


func _show_pause_menu() -> void:
	var overlay := Control.new()
	overlay.name = "PauseOverlay"
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	var layer := CanvasLayer.new()
	layer.layer = 20
	layer.name = "PauseLayer"
	layer.add_child(overlay)
	add_child(layer)

	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.add_child(dim)

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.add_child(center)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	center.add_child(vbox)

	var resume := _menu_button("Resume")
	resume.pressed.connect(func():
		layer.queue_free()
		_paused = false
		_set_movement(true))
	vbox.add_child(resume)

	var save := _menu_button("Save")
	save.pressed.connect(func():
		GameState.current_scene = scene_file_path
		var ok := GameState.save_game()
		save.text = "Saved ✓" if ok else "Save failed")
	vbox.add_child(save)

	var settings := _menu_button("Settings")
	settings.pressed.connect(func():
		overlay.add_child(preload("res://scenes/ui/settings.tscn").instantiate()))
	vbox.add_child(settings)

	var menu := _menu_button("Main Menu")
	menu.pressed.connect(func(): get_tree().change_scene_to_file("res://scenes/main_menu.tscn"))
	vbox.add_child(menu)

	resume.grab_focus()


func _menu_button(text: String) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(200, 40)
	button.add_theme_font_size_override("font_size", 20)
	return button
