"""
Text-mode simulator for the RPG-AI-FRAMEWORK backend.
Run the server first:  python -m uvicorn main:app --reload --port 8000
Then in a second terminal:  python sim.py
"""

import httpx
import sys
import textwrap
import json

BASE = "http://localhost:8000"
WIDTH = 80


# ── helpers ──────────────────────────────────────────────────────────────────

def hr(char="─"):
    print(char * WIDTH)

def wrap(text: str, indent: int = 0):
    prefix = " " * indent
    for line in text.splitlines():
        if line.strip():
            print(textwrap.fill(line, WIDTH, initial_indent=prefix, subsequent_indent=prefix))
        else:
            print()

def header(title: str):
    print()
    hr("═")
    print(f"  {title.upper()}")
    hr("═")

def section(title: str):
    print()
    hr()
    print(f"  {title}")
    hr()

def prompt(label: str) -> str:
    try:
        return input(f"\n{label}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\n[simulator exited]")
        sys.exit(0)

def choose(options: list[str], label: str = "Choice") -> int:
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    while True:
        raw = prompt(label)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("  Enter a number from the list.")

def post(path: str, **body) -> dict:
    r = httpx.post(f"{BASE}{path}", json=body, timeout=120)
    if r.status_code not in (200, 201):
        print(f"\n[HTTP {r.status_code}] {r.text[:300]}")
        sys.exit(1)
    return r.json()

def get(path: str) -> dict:
    r = httpx.get(f"{BASE}{path}", timeout=60)
    if r.status_code not in (200, 201):
        print(f"\n[HTTP {r.status_code}] {r.text[:300]}")
        sys.exit(1)
    return r.json()


# ── onboarding ────────────────────────────────────────────────────────────────

def run_onboarding() -> str:
    header("The Architect's Facility")

    data = post("/onboarding/start")
    session_id: str = data["session_id"]

    print(f"\n  Session: {session_id}\n")
    wrap(data["message"], indent=4)

    while True:
        user_msg = prompt("You")
        if not user_msg:
            continue

        resp = post(f"/onboarding/{session_id}/respond", message=user_msg)
        print()
        wrap(resp.get("reply", ""), indent=4)

        if resp.get("ready"):
            print("\n  [The Architect has learned enough.]\n")
            break

    # generate world options
    section("Generating Your Worlds…")
    print("  (This may take 20-30 seconds while the AI builds two worlds for you)\n")

    opts = post(f"/onboarding/{session_id}/generate-options")

    facility_msg = opts.get("facility_message", "")
    if facility_msg:
        print()
        wrap(facility_msg, indent=4)
        print()

    worlds: list[dict] = opts.get("options", [])

    section("Choose Your World")
    for i, w in enumerate(worlds):
        label = ["A", "B"][i]
        wd = w.get("world", {})
        print(f"\n  ── WORLD {label} ──")
        print(f"  {wd.get('name', '?')}")
        wrap(wd.get("description", ""), indent=4)

        arch = w.get("archetype", {})
        if arch:
            print(f"\n  Archetype: {arch.get('name','?')}  |  {arch.get('tagline','')}")

        starter = w.get("starting_context", {})
        if starter:
            print(f"\n  Opening: {starter.get('opening_scene', '')[:120]}…")

    choice_idx = choose(["World A", "World B", "Let me think about it (re-read)"])
    if choice_idx == 2:
        # re-read then pick
        print()
        for i, w in enumerate(worlds):
            print(json.dumps(w, indent=2)[:600])
            print()
        choice_idx = choose(["World A", "World B"])

    chosen_label = ["A", "B"][choice_idx]
    result = post(f"/onboarding/{session_id}/choose", choice=chosen_label)

    section("World Locked In")
    wrap(result.get("confirmation_message", "Your journey begins."), indent=4)
    print(f"\n  Session ID: {session_id}")

    return session_id


# ── main game loop ─────────────────────────────────────────────────────────────

def show_status(session_id: str):
    res = get(f"/resources/{session_id}")
    inv = res.get("inventory", {})
    stats = res.get("stats", {})

    section("Status")
    currency = inv.get("currency", 0)
    cur_name = res.get("currency_name", "Gold")
    print(f"  {cur_name}: {currency}")

    if stats:
        print("  Stats:", "  ".join(f"{k}:{v}" for k, v in stats.items()))

    tokens = inv.get("faction_tokens", {})
    if tokens:
        print("  Faction tokens:", "  ".join(f"{k}:{v}" for k, v in tokens.items()))


def run_missions(session_id: str):
    section("Missions")
    data = post(f"/missions/{session_id}/generate", pool_size=3)
    pool: list[dict] = data.get("pool", [])

    if not pool:
        print("  No missions generated.")
        return

    for i, m in enumerate(pool, 1):
        print(f"\n  [{i}] {m.get('title','?')}")
        wrap(m.get("description", ""), indent=6)
        print(f"      Difficulty: {m.get('difficulty','?')}  |  Reward: {m.get('reward_preview','?')}")

    idx = choose([m.get("title", f"Mission {i}") for i, m in enumerate(pool, 1)] + ["Skip"], "Pick a mission")
    if idx == len(pool):
        return

    mission = pool[idx]
    mission_id = mission.get("id") or mission.get("mission_id", "")

    print(f"\n  You accepted: {mission.get('title')}")
    approach = prompt("How do you approach this? (brief description)")

    outcome_idx = choose(["Success", "Partial success", "Failure"], "Outcome")
    outcomes = ["success", "partial", "failure"]

    result = post(
        f"/missions/{session_id}/complete",
        mission_id=mission_id,
        outcome=outcomes[outcome_idx],
        approach_used=approach,
    )

    section("Mission Result")
    wrap(result.get("narrative", result.get("message", "Done.")), indent=4)
    if result.get("rewards"):
        print(f"\n  Rewards: {result['rewards']}")


def run_npc(session_id: str):
    section("Talk to an NPC")

    npcs_data = get(f"/npcs/{session_id}")
    existing: list[dict] = npcs_data.get("npcs", [])

    if existing:
        print("  Known NPCs:")
        options = [f"{n.get('name','?')} ({n.get('role','?')})" for n in existing]
        options.append("Spawn a new NPC")
        idx = choose(options, "Select")
        if idx < len(existing):
            npc = existing[idx]
            npc_id = npc.get("id") or npc.get("npc_id", "")
        else:
            npc = None
    else:
        npc = None

    if npc is None:
        role = prompt("NPC role (e.g. merchant, guard, elder)")
        faction = prompt("Faction (leave blank for 'independent')")
        spawn = post(f"/npcs/{session_id}/spawn",
                     role=role,
                     faction=faction or "independent")
        npc = spawn.get("npc", spawn)
        npc_id = npc.get("id") or npc.get("npc_id", "")
        section(f"Met: {npc.get('name','?')}")
        wrap(npc.get("background", ""), indent=4)

    print(f"\n  Talking to {npc.get('name','?')} [{npc.get('role','?')}]\n")

    while True:
        msg = prompt("You (blank to leave)")
        if not msg:
            break

        resp = post(f"/npcs/{session_id}/{npc_id}/talk", message=msg)
        print()
        wrap(f"{npc.get('name','NPC')}: {resp.get('reply', '')}", indent=4)

        if resp.get("relationship_update"):
            print(f"\n  [Relationship: {resp['relationship_update']}]")


def run_events(session_id: str):
    section("World Events")
    print("  Ticking the world clock…")

    data = post(f"/events/{session_id}/tick")
    events: list[dict] = data.get("active_events", data.get("events", []))

    if not events:
        print("  The world is quiet for now.")
        return

    for ev in events[:3]:  # show up to 3
        print(f"\n  ── {ev.get('title','Event')} ──")
        wrap(ev.get("description", ""), indent=4)

        options: list[dict] = ev.get("options", [])
        if not options:
            continue

        opt_labels = [f"{o.get('label','?')} — {o.get('description','')}" for o in options]
        opt_labels.append("Ignore this event")
        idx = choose(opt_labels, "Your response")

        if idx == len(options):
            continue

        opt = options[idx]
        approach = prompt("How do you do it?")

        result = post(
            f"/events/{session_id}/respond",
            event_id=ev.get("id", ev.get("event_id", "")),
            option_id=opt.get("id", opt.get("option_id", str(idx))),
            approach=approach,
        )
        print()
        wrap(result.get("narrative", result.get("message", "")), indent=4)


def run_lore(session_id: str):
    section("Discover Lore")
    trigger = prompt("What triggered this discovery? (e.g. found an old book, heard a rumour)")
    context = prompt("Context (where are you, what were you doing?)")

    result = post(f"/lore/{session_id}/discover", trigger=trigger, context=context)
    print()
    lore = result.get("lore", result)
    wrap(lore.get("content", str(lore)), indent=4)


def run_mirror(session_id: str):
    section("The Mirror — Your Psychological Profile")
    print("  Generating mirror reflection… (may take a moment)\n")
    data = post(f"/mirror/{session_id}")
    mirror = data.get("mirror", data)
    wrap(mirror.get("reflection", str(mirror)), indent=4)


def advance_day(session_id: str):
    section("Advance Day")
    data = post(f"/saves/{session_id}/advance-day")
    day = data.get("in_game_day", "?")
    print(f"  Day advanced. Now: Day {day}")
    summary = data.get("day_summary", "")
    if summary:
        wrap(summary, indent=4)


def main_menu(session_id: str):
    header("RPG-AI-FRAMEWORK  ·  Text Simulator")

    actions = [
        ("Missions", run_missions),
        ("Talk to NPC", run_npc),
        ("World Events", run_events),
        ("Discover Lore", run_lore),
        ("Mirror (profile reflection)", run_mirror),
        ("Advance Day", advance_day),
        ("Show Status", show_status),
        ("Quit", None),
    ]

    while True:
        section("What do you do?")
        idx = choose([a[0] for a in actions])
        label, fn = actions[idx]

        if fn is None:
            print("\n  Farewell, traveller.\n")
            break

        try:
            fn(session_id)
        except httpx.ConnectError:
            print("\n  [Cannot reach backend — is the server running on port 8000?]")
        except Exception as e:
            print(f"\n  [Error: {e}]")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        httpx.get(f"{BASE}/docs", timeout=5)
    except httpx.ConnectError:
        print("Cannot connect to http://localhost:8000")
        print("Start the server first:  python -m uvicorn main:app --reload --port 8000")
        sys.exit(1)

    session_id = run_onboarding()
    main_menu(session_id)
