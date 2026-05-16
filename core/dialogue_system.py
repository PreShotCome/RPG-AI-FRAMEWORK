import json
import anthropic
from config import MODEL
from core.player_profile import PlayerProfile

async def generate_dialogue_options(
    npc_id: str,
    npc_last_statement: str,
    dialogue_history: list[dict],
    profile: PlayerProfile,
    client: anthropic.AsyncAnthropic,
) -> list[dict]:
    """Generate 4 dialogue options that fit the player's voice profile. Unlocked at level 11+."""

    voice = profile.get_dominant_voice()
    moral = profile.get_moral_label()
    social = profile.get_dominant_social_role()
    depth = "deeply immersed" if profile.roleplay_depth > 0.6 else "casually engaged"

    recent_history = dialogue_history[-6:] if len(dialogue_history) > 6 else dialogue_history
    history_text = "\n".join([f"{t['role'].upper()}: {t['content']}" for t in recent_history])

    prompt = f"""Generate 4 dialogue response options for a player to say to an NPC.

NPC just said: "{npc_last_statement}"

Recent conversation:
{history_text}

Player profile:
- Voice style: {voice} (their actual way of speaking)
- Moral tendency: {moral}
- Social role: {social}
- Roleplay depth: {depth}

Generate 4 options that:
1. Feel like they come from THIS specific player
2. Cover different approaches (but all feel authentic to their voice)
3. Are natural dialogue, not gamey choices
4. Option 4 should always be slightly unexpected or reveal character

Return ONLY valid JSON:
{{
  "options": [
    {{"id": 1, "text": "what the player would say", "tone": "direct/curious/guarded/warm/etc", "implication": "what this signals about the player"}},
    {{"id": 2, "text": "...", "tone": "...", "implication": "..."}},
    {{"id": 3, "text": "...", "tone": "...", "implication": "..."}},
    {{"id": 4, "text": "...", "tone": "...", "implication": "..."}}
  ]
}}"""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )

    text = next((b.text for b in response.content if b.type == "text"), "{}")

    try:
        data = json.loads(text)
        return data.get("options", [])
    except Exception:
        return [
            {"id": 1, "text": "Tell me more.", "tone": "curious", "implication": "open"},
            {"id": 2, "text": "I understand.", "tone": "neutral", "implication": "neutral"},
            {"id": 3, "text": "That's not my concern.", "tone": "dismissive", "implication": "distant"},
            {"id": 4, "text": "...", "tone": "silent", "implication": "watchful"},
        ]
