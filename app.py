"""
RPG-AI-FRAMEWORK — Terminal App
Run: python app.py
Server must be running: python -m uvicorn main:app --port 8000
"""

import asyncio
import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, Footer, Input, Label, RichLog, Static, Rule

BASE = "http://localhost:8000"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def _post(path: str, **body) -> dict:
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{BASE}{path}", json=body or None)
        return r.json() if r.status_code in (200, 201) else {"_error": r.text, "_status": r.status_code}

async def _get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(f"{BASE}{path}")
        return r.json() if r.status_code in (200, 201) else {"_error": r.text}

def _ok(data: dict) -> bool:
    return "_error" not in data


# ── Shared CSS ────────────────────────────────────────────────────────────────

APP_CSS = """
Screen {
    background: #08090e;
}
RichLog {
    background: #08090e;
    color: #c8cad8;
    border: solid #1c1f2e;
    height: 1fr;
    scrollbar-color: #2a2d3e;
    scrollbar-color-hover: #3a3d4e;
}
.panel {
    background: #0d0f18;
    border: solid #1c1f2e;
    height: 1fr;
    padding: 1 2;
}
.panel-title {
    color: #4a6ab0;
    text-style: bold;
}
.action-bar {
    height: 3;
    background: #0a0b12;
    border-top: solid #1c1f2e;
}
.action-bar Button {
    width: 1fr;
    height: 3;
    background: #0d0f18;
    color: #4a5a80;
    border: solid #1c1f2e;
    text-style: none;
}
.action-bar Button:hover {
    background: #14172a;
    color: #7090c0;
}
.action-bar Button:focus {
    background: #14172a;
    color: #8ab0e0;
    border: solid #2a3d6e;
}
.top-bar {
    height: 1;
    background: #0a0b12;
    color: #2a3a5a;
    padding: 0 2;
}
.top-bar Label {
    color: #2a3a5a;
}
.top-bar #world-label {
    color: #3a6aaa;
    text-style: bold;
    width: 1fr;
}
.top-bar #day-label {
    color: #3a4a6a;
}
Input {
    background: #0d0f18;
    border: solid #1c1f2e;
    color: #c8cad8;
}
Input:focus {
    border: solid #2a4a8a;
}
Button {
    background: #12141e;
    border: solid #1c1f2e;
    color: #6080a8;
}
Button:hover {
    background: #181b2a;
    color: #8ab0d8;
}
Button.-danger {
    color: #a04040;
}
Button.-success {
    color: #40a060;
}
Button.-primary {
    color: #4a80c0;
    border: solid #2a4a8a;
}
.modal-bg {
    background: #08090e 80%;
    align: center middle;
}
.modal-box {
    background: #0d0f18;
    border: solid #2a3a5e;
    width: 80;
    max-height: 40;
    padding: 1 2;
}
.modal-title {
    color: #4a6ab0;
    text-style: bold;
    padding-bottom: 1;
}
.modal-scroll {
    height: 1fr;
    border: solid #1c1f2e;
    background: #08090e;
    padding: 0 1;
}
.npc-msg {
    color: #7090b8;
}
.player-msg {
    color: #909098;
}
.dim {
    color: #3a3d52;
}
.gold {
    color: #b89040;
}
.green {
    color: #408060;
}
.red {
    color: #904040;
}
.accent {
    color: #4a70b0;
}
"""


# ── Narrative helpers ─────────────────────────────────────────────────────────

def _nar(log: RichLog, text: str, style: str = "narrative") -> None:
    styles = {
        "header":    "[bold #4a80d0]",
        "system":    "[#2e3248]",
        "lore":      "[#50507a]",
        "result":    "[#409060]",
        "item":      "[bold #b89040]",
        "warning":   "[#906040]",
        "narrative": "[#b0b2c0]",
        "npc":       "[#607898]",
        "error":     "[#804040]",
    }
    tag = styles.get(style, styles["narrative"])
    end = tag.replace("[", "[/").replace("bold ", "")
    log.write(f"{tag}{text}{end}")


# ══════════════════════════════════════════════════════════════════════════════
# MODAL SCREENS
# ══════════════════════════════════════════════════════════════════════════════

class MissionModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, session_id: str, narrative_log: RichLog):
        super().__init__()
        self._sid = session_id
        self._log = narrative_log
        self._pool: list[dict] = []
        self._selected: dict = {}
        self._outcome = "success"

    def compose(self) -> ComposeResult:
        with Container(classes="modal-bg"):
            with Vertical(classes="modal-box"):
                yield Static("MISSION BOARD", classes="modal-title")
                yield Static("[ loading... ]", id="mission-status", classes="dim")
                with ScrollableContainer(classes="modal-scroll", id="mission-scroll"):
                    yield Vertical(id="mission-list")
                with Vertical(id="complete-section"):
                    yield Static("", id="selected-title", classes="accent")
                    yield Input(placeholder="How do you approach this?", id="approach-input")
                    with Horizontal(classes="action-bar"):
                        yield Button("SUCCESS", id="btn-success", classes="-success")
                        yield Button("PARTIAL", id="btn-partial")
                        yield Button("FAILURE", id="btn-failure", classes="-danger")
                    yield Button("COMMIT MISSION", id="btn-commit", classes="-primary")
                with Horizontal(classes="action-bar"):
                    yield Button("CLOSE [esc]", id="btn-close")

    def on_mount(self) -> None:
        self.query_one("#complete-section").display = False
        self._load()

    @work(exclusive=True)
    async def _load(self) -> None:
        status = self.query_one("#mission-status", Static)
        status.update("[ generating mission pool... ]")
        data = await _post(f"/missions/{self._sid}/generate", pool_size=3)
        if not _ok(data):
            status.update(f"[error] {data.get('_error','')[:80]}")
            return
        self._pool = data.get("pool", [])
        status.update(f"{len(self._pool)} missions available — select one")
        lst = self.query_one("#mission-list", Vertical)
        await lst.remove_children()
        for m in self._pool:
            diff_color = {"low": "#40a060", "high": "#a04040"}.get(m.get("difficulty",""), "#a08040")
            btn = Button(
                f"[{m.get('type','?').upper()}]  {m.get('title','?')}  ·  {m.get('difficulty','?')}",
                id=f"mission-{m['id']}",
            )
            btn.styles.color = diff_color
            await lst.mount(btn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-close":
            self.dismiss()
        elif bid == "btn-success":
            self._outcome = "success"
        elif bid == "btn-partial":
            self._outcome = "partial"
        elif bid == "btn-failure":
            self._outcome = "failure"
        elif bid == "btn-commit":
            self._commit()
        elif bid and bid.startswith("mission-"):
            mid = bid[len("mission-"):]
            self._selected = next((m for m in self._pool if m["id"] == mid), {})
            if self._selected:
                self.query_one("#selected-title", Static).update(self._selected.get("title", ""))
                self.query_one("#complete-section").display = True
                self.query_one("#approach-input", Input).focus()

    @work(exclusive=True)
    async def _commit(self) -> None:
        if not self._selected:
            return
        approach = self.query_one("#approach-input", Input).value.strip()
        if not approach:
            self.query_one("#approach-input", Input).placeholder = "You need to describe your approach."
            return
        self.query_one("#btn-commit", Button).label = "COMMITTING..."
        data = await _post(
            f"/missions/{self._sid}/complete",
            mission_id=self._selected["id"],
            outcome=self._outcome,
            approach_used=approach,
        )
        if not _ok(data):
            _nar(self._log, f"Mission error: {data.get('_error','')[:120]}", "error")
            self.dismiss()
            return
        reward = data.get("reward", {})
        item = data.get("item_found")
        _nar(self._log, f"── {self._selected.get('title','Mission')} · {self._outcome.upper()} ──", "header")
        if reward.get("currency", 0):
            _nar(self._log, f"Reward: {reward['currency']} currency earned.", "result")
        if item:
            _nar(self._log, f"Item found: {item['name']} — {item.get('description','')}", "item")
        self.dismiss()


class TalkModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, session_id: str, narrative_log: RichLog):
        super().__init__()
        self._sid = session_id
        self._log = narrative_log
        self._npcs: list[dict] = []
        self._current_npc: dict = {}
        self._npc_id: str = ""

    def compose(self) -> ComposeResult:
        with Container(classes="modal-bg"):
            with Vertical(classes="modal-box"):
                yield Static("CONTACTS", classes="modal-title")
                with ScrollableContainer(classes="modal-scroll", id="roster-scroll"):
                    yield Vertical(id="roster-list")
                with Horizontal(id="spawn-row"):
                    yield Input(placeholder="Role (merchant, engineer, alien diplomat...)", id="role-input")
                    yield Button("MAKE CONTACT", id="btn-spawn", classes="-primary")
                with Vertical(id="dialogue-section"):
                    yield Static("", id="npc-header", classes="accent")
                    with ScrollableContainer(classes="modal-scroll", id="chat-scroll"):
                        yield Vertical(id="chat-log")
                    with Horizontal(classes="action-bar"):
                        yield Input(placeholder="Say something...", id="chat-input")
                        yield Button("→", id="btn-send")
                    yield Button("BACK TO ROSTER", id="btn-back")
                with Horizontal(classes="action-bar"):
                    yield Button("CLOSE [esc]", id="btn-close")

    def on_mount(self) -> None:
        self.query_one("#dialogue-section").display = False
        self._load_roster()

    @work(exclusive=True)
    async def _load_roster(self) -> None:
        data = await _get(f"/npcs/{self._sid}")
        self._npcs = data.get("npcs", []) if _ok(data) else []
        lst = self.query_one("#roster-list", Vertical)
        await lst.remove_children()
        if not self._npcs:
            await lst.mount(Static("No contacts yet — make one below.", classes="dim"))
        for npc in self._npcs:
            standing = npc.get("standing", {})
            btn = Button(
                f"{npc.get('name','?')}  ·  {npc.get('role','?')}  [{npc.get('faction','?')}]",
                id=f"npc-{npc['id']}",
            )
            await lst.mount(btn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-close":
            self.dismiss()
        elif bid == "btn-back":
            self.query_one("#dialogue-section").display = False
            self.query_one("#roster-scroll").display = True
            self.query_one("#spawn-row").display = True
        elif bid == "btn-spawn":
            self._spawn()
        elif bid == "btn-send":
            self._send_message()
        elif bid and bid.startswith("npc-"):
            nid = bid[len("npc-"):]
            npc = next((n for n in self._npcs if n["id"] == nid), {})
            if npc:
                self._open_dialogue(npc)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            self._send_message()

    def _open_dialogue(self, npc: dict) -> None:
        self._current_npc = npc
        self._npc_id = npc["id"]
        self.query_one("#npc-header", Static).update(
            f"{npc.get('name','?')}  ·  {npc.get('role','?')}  [{npc.get('faction','?')}]"
        )
        self.query_one("#roster-scroll").display = False
        self.query_one("#spawn-row").display = False
        self.query_one("#dialogue-section").display = True
        opening = npc.get("opening_line", "")
        if opening:
            self._add_chat(npc.get("name", "NPC"), opening, is_npc=True)
        self.query_one("#chat-input", Input).focus()

    @work(exclusive=True)
    async def _spawn(self) -> None:
        role = self.query_one("#role-input", Input).value.strip()
        if not role:
            return
        self.query_one("#btn-spawn", Button).label = "SCANNING..."
        data = await _post(f"/npcs/{self._sid}/spawn", role=role, faction="independent")
        self.query_one("#btn-spawn", Button).label = "MAKE CONTACT"
        if not _ok(data):
            return
        npc = data.get("npc", {})
        self._npcs.append(npc)
        self.query_one("#role-input", Input).value = ""
        _nar(self._log, f"New contact: {npc.get('name','?')} ({npc.get('role','?')})", "result")
        self._open_dialogue(npc)

    @work(exclusive=True)
    async def _send_message(self) -> None:
        inp = self.query_one("#chat-input", Input)
        text = inp.value.strip()
        if not text or not self._npc_id:
            return
        inp.value = ""
        self._add_chat("YOU", text, is_npc=False)
        inp.disabled = True
        data = await _post(f"/npcs/{self._sid}/{self._npc_id}/talk", message=text)
        inp.disabled = False
        inp.focus()
        if not _ok(data):
            return
        reply = data.get("reply", "")
        name = self._current_npc.get("name", "NPC")
        self._add_chat(name, reply, is_npc=True)
        if reply:
            _nar(self._log, f"{name}: {reply[:120]}{'…' if len(reply) > 120 else ''}", "npc")

    def _add_chat(self, speaker: str, text: str, is_npc: bool) -> None:
        cl = "npc-msg" if is_npc else "player-msg"
        label = Static(f"[bold]{speaker}[/bold]  {text}", classes=cl)
        self.query_one("#chat-log", Vertical).mount(label)
        self.call_after_refresh(self._scroll_chat)

    def _scroll_chat(self) -> None:
        sc = self.query_one("#chat-scroll", ScrollableContainer)
        sc.scroll_end(animate=False)


class EventModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, session_id: str, narrative_log: RichLog):
        super().__init__()
        self._sid = session_id
        self._log = narrative_log
        self._events: list[dict] = []
        self._current: dict = {}
        self._selected_option: dict = {}

    def compose(self) -> ComposeResult:
        with Container(classes="modal-bg"):
            with Vertical(classes="modal-box"):
                yield Static("WORLD EVENTS", classes="modal-title")
                yield Static("[ scanning... ]", id="event-status", classes="dim")
                with ScrollableContainer(classes="modal-scroll"):
                    yield Vertical(id="event-body")
                with Vertical(id="respond-section"):
                    yield Input(placeholder="How do you do it?", id="approach-input")
                    yield Button("COMMIT", id="btn-commit", classes="-primary")
                with Horizontal(classes="action-bar"):
                    yield Button("CLOSE [esc]", id="btn-close")

    def on_mount(self) -> None:
        self.query_one("#respond-section").display = False
        self._tick()

    @work(exclusive=True)
    async def _tick(self) -> None:
        status = self.query_one("#event-status", Static)
        data = await _post(f"/events/{self._sid}/tick")
        if not _ok(data):
            status.update("[error] Could not tick events.")
            return
        self._events = data.get("active_events", data.get("events", []))
        if not self._events:
            status.update("All quiet. No anomalies detected.")
            return
        self._current = self._events[0]
        status.update(f"{len(self._events)} active event(s)")
        body = self.query_one("#event-body", Vertical)
        await body.remove_children()
        await body.mount(Static(f"[bold #4a6ab0]{self._current.get('title','')}[/bold #4a6ab0]"))
        await body.mount(Static(self._current.get("description", ""), classes="narrative"))
        hook = self._current.get("narrative_hook", "")
        if hook:
            await body.mount(Static(hook, classes="dim"))
        await body.mount(Rule())
        for opt in self._current.get("player_options", self._current.get("options", [])):
            btn = Button(
                f"{opt.get('label','?')} — {opt.get('description','')}",
                id=f"opt-{opt.get('id', opt.get('option_id',''))}",
            )
            await body.mount(btn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-close":
            self.dismiss()
        elif bid == "btn-commit":
            self._respond()
        elif bid and bid.startswith("opt-"):
            oid = bid[len("opt-"):]
            opts = self._current.get("player_options", self._current.get("options", []))
            self._selected_option = next(
                (o for o in opts if str(o.get("id", o.get("option_id",""))) == oid), {}
            )
            if self._selected_option:
                self.query_one("#respond-section").display = True
                self.query_one("#approach-input", Input).focus()

    @work(exclusive=True)
    async def _respond(self) -> None:
        approach = self.query_one("#approach-input", Input).value.strip()
        if not approach or not self._selected_option or not self._current:
            return
        self.query_one("#btn-commit", Button).label = "..."
        data = await _post(
            f"/events/{self._sid}/respond",
            event_id=self._current.get("id", ""),
            option_id=str(self._selected_option.get("id", self._selected_option.get("option_id",""))),
            approach=approach,
        )
        if _ok(data):
            narrative = data.get("narrative", data.get("message", ""))
            if narrative:
                _nar(self._log, narrative, "narrative")
        self.dismiss()


class StatsModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, session_id: str):
        super().__init__()
        self._sid = session_id

    def compose(self) -> ComposeResult:
        with Container(classes="modal-bg"):
            with Vertical(classes="modal-box"):
                yield Static("STATUS", classes="modal-title")
                with ScrollableContainer(classes="modal-scroll"):
                    yield Vertical(id="stats-body")
                with Horizontal(classes="action-bar"):
                    yield Button("CLOSE [esc]", id="btn-close")

    def on_mount(self) -> None:
        self._load()

    @work(exclusive=True)
    async def _load(self) -> None:
        data = await _get(f"/resources/{self._sid}")
        body = self.query_one("#stats-body", Vertical)
        await body.remove_children()
        if not _ok(data):
            await body.mount(Static("[error] Could not load resources.", classes="red"))
            return
        inv = data.get("inventory", {})
        stats = data.get("stats", {})
        flavors = data.get("stat_flavors", {})
        cur = inv.get("currency", 0)
        cur_name = inv.get("currency_name", "credits")
        await body.mount(Static(f"[bold #b89040]{cur:,.0f} {cur_name}[/bold #b89040]"))
        await body.mount(Rule())
        await body.mount(Static("[bold]STATS[/bold]", classes="dim"))
        for key, val in stats.items():
            display = val.get("display_name", key.title()) if isinstance(val, dict) else key.title()
            level = val.get("level", val) if isinstance(val, dict) else val
            bar = "█" * level + "░" * (10 - level)
            cost = val.get("upgrade_cost") if isinstance(val, dict) else None
            cost_str = f"  upgrade: {cost}" if cost else ""
            await body.mount(Static(f"[#4a6ab0]{display:<16}[/#4a6ab0] {bar} {level}{cost_str}"))
        tokens = inv.get("faction_tokens", {})
        if tokens:
            await body.mount(Rule())
            await body.mount(Static("[bold]FACTION TOKENS[/bold]", classes="dim"))
            for faction, count in tokens.items():
                await body.mount(Static(f"  {faction}: {count}"))
        items = inv.get("items", [])
        if items:
            await body.mount(Rule())
            await body.mount(Static("[bold]INVENTORY[/bold]", classes="dim"))
            for item in items:
                await body.mount(Static(f"[#b89040]{item.get('name','?')}[/#b89040]  {item.get('type','')}"))
                await body.mount(Static(f"  {item.get('description','')}", classes="dim"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()


class SaveModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, session_id: str, narrative_log: RichLog):
        super().__init__()
        self._sid = session_id
        self._log = narrative_log

    def compose(self) -> ComposeResult:
        with Container(classes="modal-bg"):
            with Vertical(classes="modal-box"):
                yield Static("SAVE / LOAD", classes="modal-title")
                yield Static("", id="save-status", classes="dim")
                with ScrollableContainer(classes="modal-scroll"):
                    yield Vertical(id="save-body")
                with Horizontal(classes="action-bar"):
                    yield Button("SAVE NOW  (slot 1)", id="btn-save-1", classes="-primary")
                    yield Button("SAVE NOW  (slot 2)", id="btn-save-2")
                    yield Button("SAVE NOW  (slot 3)", id="btn-save-3")
                with Horizontal(classes="action-bar"):
                    yield Button("CLOSE [esc]", id="btn-close")

    def on_mount(self) -> None:
        self._load_saves()

    @work(exclusive=True)
    async def _load_saves(self) -> None:
        data = await _get(f"/saves/{self._sid}")
        body = self.query_one("#save-body", Vertical)
        await body.remove_children()
        if not _ok(data):
            await body.mount(Static("Could not load save data.", classes="red"))
            return
        saves = data.get("saves", {})
        day = data.get("in_game_day", 1)
        difficulty = data.get("difficulty", "casual")
        self.query_one("#save-status", Static).update(
            f"Day {day}  ·  {difficulty} mode  ·  {data.get('world_name','?')}"
        )
        slot_labels = {
            "slot_1": "Slot 1", "slot_2": "Slot 2", "slot_3": "Slot 3",
            "auto": "Auto-save", "day_start": "Day start",
        }
        for slot, label in slot_labels.items():
            meta = saves.get(slot)
            if meta:
                ts = meta.get("saved_at", "")[:16].replace("T", "  ")
                info = f"[#4a6ab0]{label}[/#4a6ab0]  ·  Day {meta.get('in_game_day','?')}  ·  {ts}"
                row = Horizontal(
                    Static(info),
                    Button("LOAD", id=f"load-{slot}"),
                )
                await body.mount(row)
            else:
                await body.mount(Static(f"[#2a2d40]{label}  ·  empty[/#2a2d40]"))

    @work(exclusive=True)
    async def _save(self, slot: str) -> None:
        self.query_one("#save-status", Static).update("Saving...")
        await _post(f"/saves/{self._sid}/configure", difficulty="casual")
        data = await _post(f"/saves/{self._sid}", slot=slot)
        if _ok(data):
            self.query_one("#save-status", Static).update(f"Saved to {slot}.")
            _nar(self._log, f"Game saved to {slot}.", "system")
            self._load_saves()
        else:
            self.query_one("#save-status", Static).update(f"Save failed: {data.get('_error','')[:80]}")

    @work(exclusive=True)
    async def _load(self, slot: str) -> None:
        self.query_one("#save-status", Static).update(f"Loading {slot}...")
        data = await _post(f"/saves/{self._sid}/load", slot=slot)
        if _ok(data):
            _nar(self._log, f"Game loaded from {slot}.", "system")
            self.dismiss()
        else:
            self.query_one("#save-status", Static).update(f"Load failed: {data.get('_error','')[:80]}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-close":
            self.dismiss()
        elif bid == "btn-save-1":
            self._save("slot_1")
        elif bid == "btn-save-2":
            self._save("slot_2")
        elif bid == "btn-save-3":
            self._save("slot_3")
        elif bid and bid.startswith("load-"):
            self._load(bid[len("load-"):])


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING SCREEN
# ══════════════════════════════════════════════════════════════════════════════

class OnboardingScreen(Screen):
    def __init__(self):
        super().__init__()
        self._sid = ""
        self._ready = False
        self._options: list[dict] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="ob-log", wrap=True, markup=True, highlight=False)
        yield Input(placeholder="Your response...", id="ob-input")
        with Horizontal(classes="action-bar"):
            yield Button("SEND [enter]", id="btn-send", classes="-primary")
            yield Button("GENERATE WORLDS", id="btn-generate", disabled=True)

    def on_mount(self) -> None:
        self.query_one("#ob-input", Input).focus()
        self._start()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ob-input":
            self._send()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-send":
            self._send()
        elif event.button.id == "btn-generate":
            self._generate()

    @work(exclusive=True)
    async def _start(self) -> None:
        log = self.query_one("#ob-log", RichLog)
        data = await _post("/onboarding/start")
        if not _ok(data):
            _nar(log, "Cannot reach server. Is it running?", "error")
            return
        self._sid = data["session_id"]
        self.app.session_id = self._sid
        _nar(log, f"Session: {self._sid[:16]}...", "system")
        _nar(log, "", "system")
        for line in data.get("message", "").splitlines():
            _nar(log, line, "lore" if line.startswith("Begin") else "narrative")

    @work(exclusive=True)
    async def _send(self) -> None:
        inp = self.query_one("#ob-input", Input)
        text = inp.value.strip()
        if not text or not self._sid:
            return
        inp.value = ""
        inp.disabled = True
        log = self.query_one("#ob-log", RichLog)
        _nar(log, f"YOU  {text}", "system")
        data = await _post(f"/onboarding/{self._sid}/respond", message=text)
        inp.disabled = False
        inp.focus()
        if not _ok(data):
            _nar(log, f"Error: {data.get('_error','')[:100]}", "error")
            return
        _nar(log, "", "system")
        _nar(log, data.get("reply", ""), "narrative")
        _nar(log, "", "system")
        if data.get("ready") and not self._ready:
            self._ready = True
            _nar(log, "── The Architect has learned enough. ──", "lore")
            self.query_one("#btn-generate", Button).disabled = False
            self.query_one("#btn-generate", Button).focus()

    @work(exclusive=True)
    async def _generate(self) -> None:
        log = self.query_one("#ob-log", RichLog)
        self.query_one("#btn-generate", Button).disabled = True
        self.query_one("#ob-input", Input).disabled = True
        _nar(log, "", "system")
        _nar(log, "Building your worlds. This takes 20-30 seconds...", "system")
        data = await _post(f"/onboarding/{self._sid}/generate-options")
        if not _ok(data):
            _nar(log, f"Error: {data.get('_error','')[:100]}", "error")
            self.query_one("#btn-generate", Button).disabled = False
            return
        self._options = data.get("options", [])
        msg = data.get("facility_message", "")
        if msg:
            _nar(log, "", "system")
            for line in msg.splitlines():
                _nar(log, line, "lore" if line else "system")
        _nar(log, "", "system")
        for i, opt in enumerate(self._options):
            label = ["A", "B"][i]
            _nar(log, f"── WORLD {label}: {opt.get('name','?')} ──", "header")
            _nar(log, f'"{opt.get("tagline","")}"', "lore")
            _nar(log, opt.get("setting_preview", "")[:200], "narrative")
            _nar(log, "", "system")
        await self.app.push_screen(WorldChoiceScreen(self._sid, self._options))


# ══════════════════════════════════════════════════════════════════════════════
# WORLD CHOICE SCREEN
# ══════════════════════════════════════════════════════════════════════════════

class WorldChoiceScreen(Screen):
    def __init__(self, session_id: str, options: list[dict]):
        super().__init__()
        self._sid = session_id
        self._options = options

    def compose(self) -> ComposeResult:
        yield Static("CHOOSE YOUR WORLD", classes="modal-title")
        with Horizontal():
            with Vertical(classes="panel", id="card-a"):
                yield Static("[bold #4a80d0]WORLD A — THE WORLD YOU DESCRIBED[/bold #4a80d0]")
                yield Rule()
                a = self._options[0] if self._options else {}
                yield Static(f"[bold]{a.get('name','?')}[/bold]")
                yield Static(f'"{a.get("tagline","")}"', classes="dim")
                yield Static(f"Tone: {a.get('tone','')}", classes="dim")
                yield Static(a.get("setting_preview", "")[:300])
                yield Button("ENTER THIS WORLD", id="btn-a", classes="-primary")
            with Vertical(classes="panel", id="card-b"):
                yield Static("[bold #806040]WORLD B — THE WORLD WE THINK YOU NEED[/bold #806040]")
                yield Rule()
                b = self._options[1] if len(self._options) > 1 else {}
                yield Static(f"[bold]{b.get('name','?')}[/bold]")
                yield Static(f'"{b.get("tagline","")}"', classes="dim")
                yield Static(f"Tone: {b.get('tone','')}", classes="dim")
                yield Static(b.get("setting_preview", "")[:300])
                yield Button("ENTER THIS WORLD", id="btn-b")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-a":
            self._choose("A")
        elif event.button.id == "btn-b":
            self._choose("B")

    @work(exclusive=True)
    async def _choose(self, choice: str) -> None:
        self.query_one("#btn-a", Button).disabled = True
        self.query_one("#btn-b", Button).disabled = True
        data = await _post(f"/onboarding/{self._sid}/choose", choice=choice)
        if not _ok(data):
            self.query_one("#btn-a", Button).disabled = False
            self.query_one("#btn-b", Button).disabled = False
            return
        self.app.world_data = data.get("world", {})
        self.app.archetype = data.get("archetype", {})
        await _post(f"/saves/{self._sid}/configure", difficulty="casual")
        await self.app.switch_screen(GameScreen(self._sid))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN GAME SCREEN
# ══════════════════════════════════════════════════════════════════════════════

class GameScreen(Screen):
    BINDINGS = [
        Binding("m", "missions", "Missions"),
        Binding("t", "talk", "Talk"),
        Binding("e", "events", "Events"),
        Binding("s", "stats", "Stats"),
        Binding("ctrl+s", "save", "Save"),
        Binding("d", "advance_day", "Day"),
        Binding("q", "quit_game", "Quit"),
    ]

    def __init__(self, session_id: str):
        super().__init__()
        self._sid = session_id
        self._day = 1

    def compose(self) -> ComposeResult:
        with Horizontal(classes="top-bar"):
            yield Label("LOADING...", id="world-label")
            yield Label("DAY 1", id="day-label")
            yield Label(
                f"  ⬡ companion → localhost:8000/companion/{self._sid}",
                id="companion-label",
            )
        yield RichLog(id="narrative", wrap=True, markup=True, highlight=False)
        with Horizontal(classes="action-bar"):
            yield Button("MISSIONS [m]", id="btn-missions")
            yield Button("TALK [t]", id="btn-talk")
            yield Button("EVENTS [e]", id="btn-events")
            yield Button("STATS [s]", id="btn-stats")
            yield Button("SAVE [^s]", id="btn-save")
            yield Button("DAY [d]", id="btn-day")
            yield Button("QUIT [q]", id="btn-quit", classes="-danger")
        yield Footer()

    def on_mount(self) -> None:
        self._init_world()

    def _log(self) -> RichLog:
        return self.query_one("#narrative", RichLog)

    @work(exclusive=True)
    async def _init_world(self) -> None:
        log = self._log()
        world = getattr(self.app, "world_data", {})
        world_name = world.get("name", "Unknown Sector")
        self.query_one("#world-label", Label).update(world_name)
        _nar(log, f"[ {world_name.upper()} ]", "header")
        setting = world.get("setting", "")
        if setting:
            _nar(log, setting[:400], "lore")
        opening = world.get("starting_context", {}).get("opening_scene", "")
        if opening:
            _nar(log, opening, "narrative")
        _nar(log, f"  ⬡ companion app → http://localhost:8000/companion/{self._sid}", "system")
        _nar(log, "── All systems nominal. ──", "system")

    def _refresh_day(self) -> None:
        self.query_one("#day-label", Label).update(f"DAY {self._day}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "btn-missions": self.action_missions,
            "btn-talk": self.action_talk,
            "btn-events": self.action_events,
            "btn-stats": self.action_stats,
            "btn-save": self.action_save,
            "btn-day": self.action_advance_day,
            "btn-quit": self.action_quit_game,
        }
        fn = actions.get(event.button.id)
        if fn:
            fn()

    def action_missions(self) -> None:
        self.app.push_screen(MissionModal(self._sid, self._log()))

    def action_talk(self) -> None:
        self.app.push_screen(TalkModal(self._sid, self._log()))

    def action_events(self) -> None:
        self.app.push_screen(EventModal(self._sid, self._log()))

    def action_stats(self) -> None:
        self.app.push_screen(StatsModal(self._sid))

    def action_save(self) -> None:
        self.app.push_screen(SaveModal(self._sid, self._log()))

    def action_advance_day(self) -> None:
        self._do_advance_day()

    def action_quit_game(self) -> None:
        self.app.exit()

    @work(exclusive=True)
    async def _do_advance_day(self) -> None:
        log = self._log()
        _nar(log, "[ Advancing day... ]", "system")
        data = await _post(f"/saves/{self._sid}/advance-day")
        if _ok(data):
            self._day = data.get("in_game_day", self._day)
            self._refresh_day()
            summary = data.get("day_summary", "")
            _nar(log, f"── Day {self._day} ──", "header")
            if summary:
                _nar(log, summary, "narrative")
            else:
                _nar(log, "The void counts another rotation.", "narrative")
        else:
            _nar(log, f"Day advance failed: {data.get('_error','')[:100]}", "error")


# ══════════════════════════════════════════════════════════════════════════════
# APP
# ══════════════════════════════════════════════════════════════════════════════

class RPGApp(App):
    CSS = APP_CSS
    TITLE = "RPG-AI-FRAMEWORK"
    SUB_TITLE = "text terminal"

    session_id: str = ""
    world_data: dict = {}
    archetype: dict = {}

    async def on_mount(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                await c.get(f"{BASE}/health")
        except Exception:
            self.exit(message="Cannot reach server on localhost:8000.\nRun: python -m uvicorn main:app --port 8000")
            return
        await self.push_screen(OnboardingScreen())


if __name__ == "__main__":
    RPGApp().run()
