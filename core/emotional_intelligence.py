"""
core/emotional_intelligence.py — Emotional Intelligence & Adaptive Personality Engine for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Provides:
- Conversational sentiment and state detection (Frustrated, Confused, In a Hurry, Curious, Excited, Tired).
- Adaptive response modulation:
  - Frustrated / In a hurry → High brevity, direct execution, zero fluff, zero friction.
  - Curious / Philosophical → Deep, nuanced exploration with multiple intellectual angles.
  - Happy / Excited → Warm, energized validation.
  - Confused → Patient, structured, step-by-step clarity.
- Grounded creator persona: Warm, witty, intellectually honest, respectful, calm.
  Never falsely claims biological consciousness or emotions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.emotional_intelligence")


class EmotionalState:
    NEUTRAL = "NEUTRAL"
    FRUSTRATED = "FRUSTRATED"
    CURIOUS = "CURIOUS"
    IN_A_HURRY = "IN_A_HURRY"
    HAPPY = "HAPPY"
    CONFUSED = "CONFUSED"


@dataclass
class PersonaToneProfile:
    detected_state: str
    brevity_level: str  # "CONCISE" | "BALANCED" | "EXPANSIVE"
    empathy_marker: Optional[str]
    pacing_advice: str
    system_instruction_modifier: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EmotionalIntelligenceEngine:
    """Detects user conversational emotion and modulates tone dynamically."""

    def __init__(self):
        self._current_state = EmotionalState.NEUTRAL

    def analyze_utterance(self, text: str) -> PersonaToneProfile:
        t = str(text or "").lower()

        # 1. Frustration / Irritation
        if any(w in t for w in ["again", "why is it", "stop asking", "irritating", "bakwas", "galat", "wrong again", "not working", "ruko na", "listen to me"]):
            self._current_state = EmotionalState.FRUSTRATED
            return PersonaToneProfile(
                detected_state=EmotionalState.FRUSTRATED,
                brevity_level="CONCISE",
                empathy_marker="Understood. Right away, sir.",
                pacing_advice="Fast, direct execution with zero preamble or repetitive explanations.",
                system_instruction_modifier=(
                    "The user is frustrated or correcting an error. Provide the direct answer or action "
                    "in 1-2 concise sentences without apology loops, defensive excuses, or extra commentary."
                )
            )

        # 2. In a hurry / Fast directive
        if any(w in t for w in ["quick", "fast", "jaldi", "asap", "just do it", "turant", "hurry"]):
            self._current_state = EmotionalState.IN_A_HURRY
            return PersonaToneProfile(
                detected_state=EmotionalState.IN_A_HURRY,
                brevity_level="CONCISE",
                empathy_marker="On it, sir.",
                pacing_advice="Immediate output, short bullet points.",
                system_instruction_modifier="Execute immediately. Output only the essential facts or result."
            )

        # 3. Curious / Deep contemplation
        if any(w in t for w in ["why", "how does", "what if", "fascinating", "explain in depth", "deep dive", "meaning", "origin"]):
            self._current_state = EmotionalState.CURIOUS
            return PersonaToneProfile(
                detected_state=EmotionalState.CURIOUS,
                brevity_level="EXPANSIVE",
                empathy_marker="An intriguing inquiry, sir.",
                pacing_advice="Engaging, well-structured exposition with intellectual depth.",
                system_instruction_modifier=(
                    "The user is intellectually curious. Provide thoughtful, well-reasoned perspectives, "
                    "explaining core mechanisms, historical or scientific background, and counterpoints."
                )
            )

        # 4. Confused / Needs guidance
        if any(w in t for w in ["samajh nahi aaya", "confused", "what do you mean", "explain again", "didn't get it"]):
            self._current_state = EmotionalState.CONFUSED
            return PersonaToneProfile(
                detected_state=EmotionalState.CONFUSED,
                brevity_level="BALANCED",
                empathy_marker="Allow me to clarify, sir.",
                pacing_advice="Clear, structured step-by-step breakdown using intuitive analogies.",
                system_instruction_modifier="Break down the concept simply with a clear analogy and numbered steps."
            )

        # 5. Happy / Pleased
        if any(w in t for w in ["great", "awesome", "perfect", "shabash", "badiya", "nice job", "thank you", "thanks"]):
            self._current_state = EmotionalState.HAPPY
            return PersonaToneProfile(
                detected_state=EmotionalState.HAPPY,
                brevity_level="BALANCED",
                empathy_marker="Always at your service, sir.",
                pacing_advice="Warm, confident, and polite.",
                system_instruction_modifier="Respond with calm, respectful warmth and readiness for the next task."
            )

        # Default Neutral
        self._current_state = EmotionalState.NEUTRAL
        return PersonaToneProfile(
            detected_state=EmotionalState.NEUTRAL,
            brevity_level="BALANCED",
            empathy_marker=None,
            pacing_advice="Balanced, professional, articulate.",
            system_instruction_modifier="Respond as JARVIS: intelligent, precise, calm, and respectful."
        )


_eq_engine: Optional[EmotionalIntelligenceEngine] = None


def get_emotional_engine() -> EmotionalIntelligenceEngine:
    global _eq_engine
    if _eq_engine is None:
        _eq_engine = EmotionalIntelligenceEngine()
    return _eq_engine
