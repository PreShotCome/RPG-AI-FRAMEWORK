import json
import re
import logging
import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-7"

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = (
    "You are an atmospheric Dungeon Master narrating a living world. "
    "Describe scenes with vivid, grounded detail. Keep the player at the centre. "
    "Output ONLY valid JSON — no markdown fences, no explanation, no extra text."
)


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def _world_summary(world: dict) -> str:
    name = world.get("name", "Unknown World")
    tagline = world.get("tagline", "")
    setting = (world.get("setting") or "")[:300]
    parts = [f"World: {name}"]
    if tagline:
        parts.append(f"Tagline: {tagline}")
    if setting:
        parts.append(f"Setting: {setting}")
    return "\n".join(parts)


def _profile_summary(profile) -> str:
    axes = {
        "aggression": profile.aggression,
        "morality": profile.morality,
        "lawfulness": profile.lawfulness,
        "empathy": profile.empathy,
        "immersion": profile.immersion,
        "deliberateness": profile.deliberateness,
        "sociability": profile.sociability,
        "deference": profile.deference,
    }
    significant = {k: round(v, 2) for k, v in axes.items() if v is not None and abs(v) > 0.3}
    if not significant:
        return "No strong behavioral tendencies yet."
    return "Tendencies: " + ", ".join(f"{k}={v}" for k, v in significant.items())


def _stats_summary(stats) -> str:
    if stats is None:
        return ""
    d = stats.to_dict() if hasattr(stats, "to_dict") else {}
    parts = []
    for key, val in d.items():
        if isinstance(val, dict):
            level = val.get("level", "?")
            parts.append(f"{key}:{level}")
        elif isinstance(val, (int, float)):
            parts.append(f"{key}:{val}")
    return "Stats: " + ", ".join(parts) if parts else ""


def _history_summary(scene_history: list) -> str:
    recent = scene_history[-6:] if len(scene_history) > 6 else scene_history
    if not recent:
        return ""
    lines = []
    for sc in recent:
        loc = sc.get("location", "")
        desc = (sc.get("description") or "")[:120]
        lines.append(f"[{loc}] {desc}")
    return "Recent scenes:\n" + "\n".join(lines)


def generate_scene(
    world: dict,
    world_state,
    profile,
    archetype: dict,
    scene_history: list,
    location: str,
    mode: str,
    mission: dict | None,
    stats,
) -> dict | None:
    try:
        factions_text = ""
        if world_state and world_state.factions:
            faction_labels = [
                f"{name}: {f.label()}" for name, f in world_state.factions.items()
            ]
            factions_text = "Factions: " + ", ".join(faction_labels)

        archetype_label = (archetype or {}).get("label", "unknown archetype")

        mission_text = ""
        if mode == "mission" and mission:
            mission_text = (
                f"Mission: {mission.get('title','')}\n"
                f"Description: {mission.get('description','')}\n"
                f"Difficulty: {mission.get('difficulty','medium')}"
            )

        prompt_parts = [
            _world_summary(world),
            factions_text,
            f"Player archetype: {archetype_label}",
            _profile_summary(profile),
            f"Current location: {location or 'unknown'}",
            f"Mode: {mode}",
        ]
        if mission_text:
            prompt_parts.append(mission_text)
        history = _history_summary(scene_history)
        if history:
            prompt_parts.append(history)

        prompt_parts.append(
            'Generate a scene. Return JSON: {"description": "...", "location": "...", '
            '"suggestions": ["...", "...", "...", "..."], "dm_note": "..."}'
        )

        prompt = "\n".join(p for p in prompt_parts if p)

        resp = _client.messages.create(
            model=MODEL,
            max_tokens=700,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _parse_json(resp.content[0].text)
        # Ensure suggestions is always a non-empty list
        if not isinstance(result.get("suggestions"), list) or not result["suggestions"]:
            result["suggestions"] = ["Look around", "Listen carefully", "Move forward", "Check your surroundings"]
        return result
    except Exception as e:
        logger.error("generate_scene failed: %s", e, exc_info=True)
        return None


def resolve_action(
    scene: dict,
    player_action: str,
    world: dict,
    world_state,
    profile,
    archetype: dict,
    scene_history: list,
    stats,
    mode: str,
    mission: dict | None,
    scenes_in_mission: int,
) -> dict | None:
    try:
        factions_text = ""
        if world_state and world_state.factions:
            faction_labels = [
                f"{name}: {f.label()}" for name, f in world_state.factions.items()
            ]
            factions_text = "Factions: " + ", ".join(faction_labels)

        archetype_label = (archetype or {}).get("label", "unknown archetype")

        mission_text = ""
        if mode == "mission" and mission:
            mission_text = (
                f"Mission: {mission.get('title','')}\n"
                f"Description: {mission.get('description','')}\n"
                f"Difficulty: {mission.get('difficulty','medium')}"
            )

        wrap_up_hint = ""
        if mode == "mission" and scenes_in_mission > 5:
            wrap_up_hint = (
                f"This mission has had {scenes_in_mission} scenes. "
                "If a natural conclusion is reached, resolve it now."
            )

        scene_text = (
            f"Current scene:\n"
            f"Location: {scene.get('location','')}\n"
            f"Description: {scene.get('description','')}\n"
            f"DM note: {scene.get('dm_note','')}"
        )

        stats_text = _stats_summary(stats)

        prompt_parts = [
            _world_summary(world),
            factions_text,
            f"Player archetype: {archetype_label}",
            _profile_summary(profile),
            stats_text,
            f"Mode: {mode}",
        ]
        if mission_text:
            prompt_parts.append(mission_text)
        if wrap_up_hint:
            prompt_parts.append(wrap_up_hint)
        prompt_parts.append(scene_text)
        prompt_parts.append(f"Player action: {player_action}")

        schema = (
            "Return JSON:\n"
            "{\n"
            '  "narrative": "3-5 sentences of what happened",\n'
            '  "next_scene": {"description": "...", "location": "...", '
            '"suggestions": ["...", "...", "...", "..."], "dm_note": "..."},\n'
            '  "mission_outcome": null,\n'
            '  "quest_discovered": null,\n'
            '  "npc_encountered": null,\n'
            '  "world_impacts": {},\n'
            '  "profile_signal": "brief behavioral observation"\n'
            "}\n"
            "mission_outcome (only if mode=mission and there is a natural conclusion): "
            '{"result": "success|failure|partial", "summary": "2-3 sentences"}\n'
            "quest_discovered (exploration mode only, occasionally): "
            '{"title": "...", "description": "...", "type": "heist|rescue|investigation|delivery|confrontation|exploration", '
            '"difficulty": "easy|medium|hard|deadly", "giver": {"name": "...", "faction": "..."}}\n'
            "npc_encountered (exploration mode only, occasionally): "
            '{"name": "...", "role": "...", "faction": "...", "description": "..."}\n'
            "world_impacts: dict of faction name to float (-1.0 to 1.0)"
        )
        prompt_parts.append(schema)

        prompt = "\n".join(p for p in prompt_parts if p)

        resp = _client.messages.create(
            model=MODEL,
            max_tokens=1400,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _parse_json(resp.content[0].text)
        # Ensure next_scene.suggestions is always a list
        ns = result.get("next_scene")
        if isinstance(ns, dict):
            if not isinstance(ns.get("suggestions"), list) or not ns["suggestions"]:
                ns["suggestions"] = ["Look around", "Listen carefully", "Move forward", "Check your surroundings"]
        return result
    except Exception as e:
        logger.error("resolve_action failed: %s", e, exc_info=True)
        return None
