import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class ProfileDimension:
    value: float = 0.0      # -1.0 to 1.0 for axes, 0.0 to 1.0 for scales
    confidence: float = 0.0  # how many data points back this
    evidence: list[str] = field(default_factory=list)

@dataclass
class PlayerProfile:
    save_id: str = ""
    level: int = 1
    created_at: float = field(default_factory=time.time)

    # Core dimensions
    playstyle_scores: dict[str, float] = field(default_factory=lambda: {
        "combat": 0.0, "stealth": 0.0, "diplomacy": 0.0, "exploration": 0.0
    })
    moral_axis: float = 0.0        # -1.0 evil -> 1.0 good
    law_axis: float = 0.0          # -1.0 chaotic -> 1.0 lawful
    voice_scores: dict[str, float] = field(default_factory=lambda: {
        "verbose": 0.0, "brief": 0.0, "poetic": 0.0, "direct": 0.0
    })
    roleplay_depth: float = 0.5    # 0.0 meta/casual -> 1.0 deep immersion
    decision_speed: float = 0.5    # 0.0 deliberate -> 1.0 impulsive
    social_role_scores: dict[str, float] = field(default_factory=lambda: {
        "lone_wolf": 0.0, "collaborative": 0.0, "leader": 0.0
    })
    authority_scores: dict[str, float] = field(default_factory=lambda: {
        "respectful": 0.0, "defiant": 0.0, "pragmatic": 0.0
    })
    theme_scores: dict[str, float] = field(default_factory=lambda: {
        "mystery": 0.0, "action": 0.0, "politics": 0.0,
        "survival": 0.0, "horror": 0.0, "comedy": 0.0
    })

    # Crystallized archetype (set at checkpoint)
    archetype: str = ""
    archetype_description: str = ""

    # Raw interaction log for Claude to analyze
    interaction_log: list[dict] = field(default_factory=list)

    # NPC relationship scores
    npc_relationships: dict[str, int] = field(default_factory=dict)

    # Checkpoint flag
    checkpoint_reached: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerProfile":
        p = cls()
        for key, value in data.items():
            if hasattr(p, key):
                setattr(p, key, value)
        return p

    def log_interaction(self, npc_id: str, npc_statement: str, player_response: str, context: str = ""):
        self.interaction_log.append({
            "timestamp": time.time(),
            "level": self.level,
            "npc_id": npc_id,
            "npc_statement": npc_statement,
            "player_response": player_response,
            "context": context
        })

    def get_dominant_playstyle(self) -> str:
        return max(self.playstyle_scores, key=self.playstyle_scores.get)

    def get_dominant_voice(self) -> str:
        return max(self.voice_scores, key=self.voice_scores.get)

    def get_dominant_social_role(self) -> str:
        return max(self.social_role_scores, key=self.social_role_scores.get)

    def get_dominant_authority_stance(self) -> str:
        return max(self.authority_scores, key=self.authority_scores.get)

    def get_top_themes(self, n: int = 3) -> list[str]:
        sorted_themes = sorted(self.theme_scores.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_themes[:n]]

    def get_moral_label(self) -> str:
        if self.moral_axis > 0.4:
            return "good"
        elif self.moral_axis < -0.4:
            return "evil"
        return "neutral"

    def get_law_label(self) -> str:
        if self.law_axis > 0.4:
            return "lawful"
        elif self.law_axis < -0.4:
            return "chaotic"
        return "neutral"

    def get_summary_for_ai(self) -> str:
        """Compact summary for Claude to use in generation."""
        return f"""Player Profile Summary:
Level: {self.level}
Archetype: {self.archetype or "undetermined"}
Primary Playstyle: {self.get_dominant_playstyle()}
Alignment: {self.get_moral_label()} / {self.get_law_label()}
Communication Voice: {self.get_dominant_voice()}
Roleplay Depth: {"immersive" if self.roleplay_depth > 0.6 else "casual" if self.roleplay_depth < 0.4 else "moderate"}
Social Role: {self.get_dominant_social_role()}
Authority Stance: {self.get_dominant_authority_stance()}
Top Themes: {", ".join(self.get_top_themes())}
Interactions logged: {len(self.interaction_log)}"""


def apply_profile_analysis(profile: PlayerProfile, analysis: dict) -> PlayerProfile:
    """Apply Claude's structured analysis to the profile."""

    def clamp(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, val))

    def apply_delta(current: float, delta: float, confidence: float = 1.0) -> float:
        weight = 0.3 * confidence
        return clamp(current + delta * weight)

    if "moral_delta" in analysis:
        profile.moral_axis = apply_delta(profile.moral_axis, analysis["moral_delta"])

    if "law_delta" in analysis:
        profile.law_axis = apply_delta(profile.law_axis, analysis["law_delta"])

    if "playstyle" in analysis:
        for style, score in analysis["playstyle"].items():
            if style in profile.playstyle_scores:
                profile.playstyle_scores[style] = clamp(
                    profile.playstyle_scores[style] + score * 0.3, 0.0, 1.0
                )

    if "voice" in analysis:
        for v, score in analysis["voice"].items():
            if v in profile.voice_scores:
                profile.voice_scores[v] = clamp(
                    profile.voice_scores[v] + score * 0.3, 0.0, 1.0
                )

    if "roleplay_delta" in analysis:
        profile.roleplay_depth = clamp(
            profile.roleplay_depth + analysis["roleplay_delta"] * 0.2, 0.0, 1.0
        )

    if "decision_speed_delta" in analysis:
        profile.decision_speed = clamp(
            profile.decision_speed + analysis["decision_speed_delta"] * 0.2, 0.0, 1.0
        )

    if "social_role" in analysis:
        for role, score in analysis["social_role"].items():
            if role in profile.social_role_scores:
                profile.social_role_scores[role] = clamp(
                    profile.social_role_scores[role] + score * 0.3, 0.0, 1.0
                )

    if "authority" in analysis:
        for stance, score in analysis["authority"].items():
            if stance in profile.authority_scores:
                profile.authority_scores[stance] = clamp(
                    profile.authority_scores[stance] + score * 0.3, 0.0, 1.0
                )

    if "themes" in analysis:
        for theme, score in analysis["themes"].items():
            if theme in profile.theme_scores:
                profile.theme_scores[theme] = clamp(
                    profile.theme_scores[theme] + score * 0.3, 0.0, 1.0
                )

    return profile
