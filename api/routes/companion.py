"""
Companion app routes:
  GET  /companion/{session_id}   — serves the companion HTML page
  WS   /companion/{session_id}/ws — WebSocket for live inventory updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from core import session as sessions
from core.events_ws import manager

router = APIRouter(prefix="/companion", tags=["companion"])


@router.get("/{session_id}", response_class=HTMLResponse)
def companion_page(session_id: str):
    if not sessions.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return HTMLResponse(_build_page(session_id))


@router.websocket("/{session_id}/ws")
async def companion_ws(session_id: str, websocket: WebSocket):
    await manager.connect(session_id, websocket)
    try:
        # Send current state immediately on connect
        if sessions.exists(session_id):
            gs = sessions.get(session_id)
            await manager.broadcast(session_id, "full_state", _state_payload(gs))
        while True:
            # Keep connection alive; client sends pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)


def _state_payload(gs) -> dict:
    world = gs.generated_world or {}
    return {
        "world_name": world.get("name", gs.world_name or "Unknown World"),
        "day": gs.in_game_day,
        "currency": gs.inventory.currency,
        "currency_name": gs.inventory.currency_name,
        "items": gs.inventory.items,
        "stats": gs.stats.to_dict(),
        "stat_flavors": world.get("stat_flavors", {}),
        "faction_tokens": gs.inventory.faction_tokens,
        "stage": gs.onboarding_stage,
    }


def _build_page(session_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Companion — RPG AI</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #0a0b0f;
    --panel: #12141a;
    --border: #2a2d3a;
    --accent: #4a9eff;
    --gold: #c8a84b;
    --text: #d0d4e0;
    --muted: #5a6070;
    --green: #4caf7d;
    --red: #e05c5c;
    --orange: #e09050;
  }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Courier New', monospace;
    font-size: 13px;
    min-height: 100vh;
    padding: 12px;
  }}
  h1 {{ font-size: 16px; color: var(--accent); letter-spacing: 2px; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 11px; margin-bottom: 16px; }}
  .status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%;
                 background: var(--red); margin-right: 6px; transition: background 0.3s; }}
  .status-dot.connected {{ background: var(--green); }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  @media (max-width: 500px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .panel {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
  }}
  .panel-title {{
    font-size: 10px;
    letter-spacing: 2px;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }}
  .currency {{
    font-size: 28px;
    color: var(--gold);
    font-weight: bold;
  }}
  .currency-name {{ color: var(--muted); font-size: 11px; margin-top: 2px; }}
  .stat-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid #1a1c24;
  }}
  .stat-row:last-child {{ border-bottom: none; }}
  .stat-name {{ color: var(--text); }}
  .stat-bar-wrap {{ display: flex; align-items: center; gap: 6px; }}
  .stat-bar {{
    width: 60px; height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
  }}
  .stat-bar-fill {{
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.4s ease;
  }}
  .stat-val {{ color: var(--accent); width: 20px; text-align: right; }}
  .faction-row {{
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid #1a1c24;
  }}
  .faction-row:last-child {{ border-bottom: none; }}
  .token-count {{ color: var(--orange); }}
  .items-list {{ max-height: 320px; overflow-y: auto; }}
  .item-card {{
    background: #0e1016;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 10px;
    margin-bottom: 6px;
    animation: slideIn 0.3s ease;
  }}
  .item-card.new {{ border-color: var(--accent); }}
  @keyframes slideIn {{
    from {{ opacity: 0; transform: translateY(-6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .item-name {{ color: var(--accent); font-weight: bold; font-size: 12px; }}
  .item-type {{ color: var(--muted); font-size: 10px; text-transform: uppercase;
               letter-spacing: 1px; float: right; }}
  .item-desc {{ color: var(--text); font-size: 11px; margin-top: 4px; line-height: 1.5; }}
  .empty {{ color: var(--muted); font-style: italic; font-size: 11px; }}
  .day-badge {{
    display: inline-block;
    background: #1a1c26;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    color: var(--muted);
    float: right;
  }}
  .toast {{
    position: fixed; bottom: 16px; right: 16px;
    background: var(--panel);
    border: 1px solid var(--accent);
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 12px;
    color: var(--accent);
    animation: toastIn 0.3s ease;
    z-index: 100;
  }}
  @keyframes toastIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
</style>
</head>
<body>
<h1><span class="status-dot" id="dot"></span>COMPANION SYSTEM</h1>
<div class="subtitle" id="world-subtitle">Connecting…</div>

<div class="grid">
  <div class="panel">
    <div class="panel-title">Resources <span class="day-badge" id="day-badge">Day —</span></div>
    <div class="currency" id="currency">—</div>
    <div class="currency-name" id="currency-name">—</div>
    <br>
    <div id="faction-tokens"><div class="empty">No faction tokens yet</div></div>
  </div>

  <div class="panel">
    <div class="panel-title">Ship Stats</div>
    <div id="stats-list"><div class="empty">Awaiting world data…</div></div>
  </div>

  <div class="panel" style="grid-column: 1 / -1;">
    <div class="panel-title">Inventory</div>
    <div class="items-list" id="items-list"><div class="empty">Nothing acquired yet.</div></div>
  </div>
</div>

<script>
const SESSION = "{session_id}";
const WS_URL  = `ws://${{location.host}}/companion/${{SESSION}}/ws`;

let state = {{ items: [], stats: {{}}, faction_tokens: {{}}, currency: 0,
               currency_name: "—", day: 1, world_name: "" }};

function connect() {{
  const dot = document.getElementById("dot");
  const ws  = new WebSocket(WS_URL);

  ws.onopen = () => {{
    dot.classList.add("connected");
    // Keep alive
    setInterval(() => {{ if (ws.readyState === 1) ws.send("ping"); }}, 20000);
  }};

  ws.onclose = () => {{
    dot.classList.remove("connected");
    setTimeout(connect, 3000);  // reconnect
  }};

  ws.onmessage = (e) => {{
    const msg = JSON.parse(e.data);
    if (msg.type === "full_state") {{
      state = msg.data;
      render();
    }} else if (msg.type === "inventory_update") {{
      Object.assign(state, msg.data);
      render();
    }} else if (msg.type === "item_gained") {{
      state.items = [msg.data.item, ...state.items];
      render();
      toast(`New item: ${{msg.data.item.name}}`);
    }} else if (msg.type === "stat_update") {{
      state.stats = msg.data.stats;
      render();
    }}
  }};
}}

function render() {{
  // World / day
  document.getElementById("world-subtitle").textContent =
    state.world_name ? `${{state.world_name}} · Session ${{SESSION.slice(0,8)}}` : `Session ${{SESSION.slice(0,8)}}`;
  document.getElementById("day-badge").textContent = `Day ${{state.day}}`;

  // Currency
  document.getElementById("currency").textContent =
    Number(state.currency).toLocaleString(undefined, {{maximumFractionDigits: 0}});
  document.getElementById("currency-name").textContent = state.currency_name;

  // Stats
  const statFlavors = state.stat_flavors || {{}};
  const STAT_KEYS = ["combat","stealth","persuasion","intellect","endurance","luck"];
  const statsEl = document.getElementById("stats-list");
  if (Object.keys(state.stats).length === 0) {{
    statsEl.innerHTML = `<div class="empty">Awaiting world data…</div>`;
  }} else {{
    statsEl.innerHTML = STAT_KEYS.map(k => {{
      const val = state.stats[k] || 1;
      const name = statFlavors[k] || k.charAt(0).toUpperCase() + k.slice(1);
      const pct = (val / 10) * 100;
      return `<div class="stat-row">
        <span class="stat-name">${{name}}</span>
        <span class="stat-bar-wrap">
          <span class="stat-bar"><span class="stat-bar-fill" style="width:${{pct}}%"></span></span>
          <span class="stat-val">${{val}}</span>
        </span>
      </div>`;
    }}).join("");
  }}

  // Faction tokens
  const factEl = document.getElementById("faction-tokens");
  const tokens = state.faction_tokens || {{}};
  if (Object.keys(tokens).length === 0) {{
    factEl.innerHTML = `<div class="empty">No faction tokens yet</div>`;
  }} else {{
    factEl.innerHTML = Object.entries(tokens).map(([f, n]) =>
      `<div class="faction-row"><span>${{f}}</span><span class="token-count">${{n}} tokens</span></div>`
    ).join("");
  }}

  // Items
  const itemsEl = document.getElementById("items-list");
  if (!state.items || state.items.length === 0) {{
    itemsEl.innerHTML = `<div class="empty">Nothing acquired yet.</div>`;
  }} else {{
    itemsEl.innerHTML = state.items.map(item =>
      `<div class="item-card">
        <span class="item-name">${{item.name}}</span>
        <span class="item-type">${{item.type || "item"}}</span>
        <div class="item-desc">${{item.description || ""}}</div>
      </div>`
    ).join("");
  }}
}}

function toast(msg) {{
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}}

connect();
render();
</script>
</body>
</html>"""
