import json
import anthropic
from config import MODEL, CAMPAIGN_ACTS, MISSIONS_PER_ACT, MISSIONS_TO_UNLOCK_ACT
from core.player_profile import PlayerProfile

async def generate_archetype(profile: PlayerProfile, client: anthropic.AsyncAnthropic) -> tuple[str, str]:
    """Crystallize the player profile into an archetype name and description."""

    prompt = f"""Based on this player profile, create a personal archetype — a poetic title and brief description.

{profile.get_summary_for_ai()}

The archetype should:
- Feel earned, not generic
- Reference their actual patterns (not just "The Warrior" or "The Mage")
- Sound like something meaningful, not a stats label
- Be 2-5 words for the title

Return ONLY valid JSON:
{{
  "archetype": "The [Something Specific]",
  "description": "One evocative sentence capturing who this player is in this world."
}}"""

    response = await client.messages.create(
        model=MODEL,
        max_tokens=256,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}]
    )

    text = next((b.text for b in response.content if b.type == "text"), "{}")

    try:
        data = json.loads(text)
        return data.get("archetype", "The Undefined"), data.get("description", "Your story is your own.")
    except Exception:
        return "The Wandering Question", "Someone who came looking for answers and found better questions instead."

def check_act_unlock(completed_missions: list[dict], current_act: int) -> bool:
    """Check if the player has completed enough missions to unlock the next act."""
    campaign_completions = [
        m for m in completed_missions
        if m.get("is_campaign") and m.get("act") == current_act
    ]
    return len(campaign_completions) >= MISSIONS_TO_UNLOCK_ACT

def get_campaign_progress(completed_missions: list[dict]) -> dict:
    act_progress = {}
    for act in range(CAMPAIGN_ACTS):
        done = [m for m in completed_missions if m.get("is_campaign") and m.get("act") == act]
        act_progress[f"act_{act}"] = {
            "completed": len(done),
            "required": MISSIONS_PER_ACT,
            "unlocked": act == 0 or check_act_unlock(completed_missions, act - 1)
        }
    return act_progress
