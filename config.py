import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
MODEL = "claude-opus-4-7"

# Campaign structure
CAMPAIGN_ACTS = 3
MISSIONS_PER_ACT = 3
MISSIONS_TO_UNLOCK_ACT = 3
TRAINING_WORLD_MAX_LEVEL = 10

# Profile dimensions
PROFILE_DIMENSIONS = [
    "playstyle",       # combat / stealth / diplomacy / exploration
    "moral_axis",      # good / neutral / evil (-1.0 to 1.0)
    "law_axis",        # lawful / neutral / chaotic (-1.0 to 1.0)
    "voice",           # verbose / brief / poetic / direct
    "roleplay_depth",  # deep / casual / meta (0.0 to 1.0)
    "decision_speed",  # deliberate / impulsive (0.0 to 1.0)
    "social_role",     # lone_wolf / collaborative / leader
    "authority_stance",# respectful / defiant / pragmatic
    "preferred_themes",# list: mystery/action/politics/survival/horror/comedy
]
