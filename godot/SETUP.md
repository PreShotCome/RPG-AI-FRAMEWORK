# Godot Project Setup

## 1. Create the Project

Open Godot 4. Create a new project called `RPG-AI-Game` (or whatever you want).
Set renderer to **Forward+** (needed for good 3D lighting).

Copy the `godot/` folder contents into your project root.

---

## 2. Register Autoloads

Go to **Project → Project Settings → Globals → Autoload** and add:

| Path | Name |
|------|------|
| `res://autoload/APIManager.gd` | `APIManager` |
| `res://autoload/GameState.gd` | `GameState` |
| `res://autoload/WorldTransfer.gd` | `_WorldTransfer` |

Order matters: APIManager first, then GameState, then _WorldTransfer.

---

## 3. Create the Architect Scene

**Scene: `res://scenes/onboarding/ArchitectScreen.tscn`**

```
ArchitectScreen              ← Control, Layout: Full Rect, script: ArchitectScreen.gd
├── Background               ← ColorRect, color: #0a0a0f, Layout: Full Rect
├── VBoxContainer            ← Layout: Full Rect, margin 40px all sides
│   ├── HeaderLabel          ← Label, text: "ARCHITECT INTAKE SYSTEM", font small/dim
│   ├── ScrollContainer      ← size_flags: Expand+Fill, custom_minimum_size: (0, 400)
│   │   └── ConversationLog  ← VBoxContainer, size_flags: Expand+Fill
│   └── InputRow             ← HBoxContainer
│       ├── PlayerInput      ← LineEdit, size_flags: Expand+Fill, placeholder: "Speak."
│       └── SendButton       ← Button, text: "→", custom_minimum_size: (40, 0)
└── ReadyBanner              ← Panel, anchor: bottom-center, hidden by default
    ├── ReadyLabel           ← Label, text: "We have enough. Ready to build your worlds."
    └── GenerateButton       ← Button, text: "GENERATE WORLDS"
```

Set **ArchitectScreen.tscn as the Main Scene** in Project Settings.

---

## 4. Create the World Choice Scene

**Scene: `res://scenes/onboarding/WorldChoiceScreen.tscn`**

```
WorldChoiceScreen            ← Control, Layout: Full Rect, script: WorldChoiceScreen.gd
├── Background               ← ColorRect, color: #08080d
└── VBoxContainer            ← Layout: Full Rect, margin 40px
    ├── FacilityMessage      ← RichTextLabel, custom_minimum_size: (0, 120)
    └── WorldsContainer      ← HBoxContainer, size_flags: Expand+Fill
        ├── WorldCardA       ← PanelContainer, size_flags: Expand+Fill
        │   └── VBoxContainer
        │       ├── LabelA   ← Label, text: "THE WORLD YOU DESCRIBED"
        │       ├── NameA    ← Label (large)
        │       ├── TaglineA ← Label (italic)
        │       ├── ToneA    ← Label (small, dim)
        │       ├── SettingA ← Label (wrapped, smaller)
        │       └── ChooseA  ← Button, text: "ENTER THIS WORLD"
        └── WorldCardB       ← PanelContainer, size_flags: Expand+Fill
            └── VBoxContainer
                ├── LabelB   ← Label, text: "THE WORLD WE THINK YOU NEED"
                ├── NameB    ← Label (large)
                ├── TaglineB ← Label (italic)
                ├── ToneB    ← Label (small, dim)
                ├── SettingB ← Label (wrapped, smaller)
                └── ChooseB  ← Button, text: "ENTER THIS WORLD"
```

---

## 5. Create the Main World Scene

**Scene: `res://scenes/main/MainWorld.tscn`**

```
MainWorld                    ← Node3D, script: MainWorld.gd
├── WorldEnvironment         ← WorldEnvironment (add an Environment resource)
├── DirectionalLight3D       ← DirectionalLight3D
├── Player                   ← CharacterBody3D (build this out as you go)
│   ├── CollisionShape3D
│   ├── MeshInstance3D       ← capsule for now
│   └── Camera3D
└── WorldUI                  ← CanvasLayer
    ├── HUD                  ← Control, Layout: Full Rect
    │   ├── WorldNameLabel   ← Label, anchored top-left
    │   ├── DayLabel         ← Label, below WorldNameLabel
    │   └── CurrencyLabel    ← Label, anchored top-right
    ├── MissionPanel         ← instance of MissionPanel.tscn
    ├── DialoguePanel        ← instance of DialoguePanel.tscn
    ├── EventPanel           ← instance of EventPanel.tscn
    └── StatsPanel           ← instance of StatsPanel.tscn
```

---

## 6. Create UI Panel Scenes

For each panel (`MissionPanel`, `DialoguePanel`, `EventPanel`, `StatsPanel`):

1. Create a new scene with a **PanelContainer** as root
2. Build the node tree described in the comments at the top of each `.gd` file
3. Attach the corresponding script
4. Save as `res://scenes/ui/<PanelName>.tscn`

Each panel starts hidden (`hide()` called in `_ready()`). MainWorld shows them on demand.

---

## 7. Backend

Make sure the Python backend is running before launching Godot:

```bash
cd /path/to/RPG-AI-FRAMEWORK
uvicorn main:app --reload --port 8000
```

The `BASE_URL` in `APIManager.gd` points to `http://localhost:8000` by default.

---

## Flow Summary

```
Godot launches
→ ArchitectScreen loads
→ POST /onboarding/start (no Claude call, instant)
→ Player chats with The Architect (each message hits /onboarding/{id}/respond)
→ When ready=true, "GENERATE WORLDS" button appears
→ POST /onboarding/{id}/generate-options (two worlds generated in parallel — takes ~15s)
→ WorldChoiceScreen loads, shows both worlds
→ Player picks A or B → POST /onboarding/{id}/choose
→ MainWorld loads, initial mission fetch + event tick fires
→ Game begins
```
