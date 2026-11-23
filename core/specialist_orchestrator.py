"""
core/specialist_orchestrator.py — Central AI Orchestrator & Multi-Specialist Router for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Orchestrates the 9 Specialist GPTs:
1. Astro & Horoscope GPT
2. Space GPT
3. Mythology GPT
4. Facial Recognition GPT
5. Age GPT
6. Voice Intelligence GPT
7. Universal Identification GPT
8. Suggestion & Advisory GPT
9. Philosopher GPT

Features:
- Automated semantic intent classification & specialist selection.
- Multi-specialist coordination (e.g. Space GPT + Mythology GPT for black holes).
- Lazy-loading of specialist modules to preserve RAM and eliminate UI lag.
- Fallback handling and source attribution.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.orchestrator")


class SpecialistOrchestrator:
    """Central Orchestrator coordinating all 9 domain intelligence engines."""

    def __init__(self):
        # Lazy loaded instances
        self._specialists: Dict[str, Any] = {}

    def _get_specialist(self, domain: str) -> Any:
        """Lazy-loads a specialist on first access to keep memory footprint minimal."""
        if domain in self._specialists:
            return self._specialists[domain]

        if domain == "ASTRO":
            from core.specialists.astro_gpt import AstroGPT
            self._specialists[domain] = AstroGPT()
        elif domain == "SPACE":
            from core.specialists.space_gpt import SpaceGPT
            self._specialists[domain] = SpaceGPT()
        elif domain == "MYTHOLOGY":
            from core.specialists.mythology_gpt import MythologyGPT
            self._specialists[domain] = MythologyGPT()
        elif domain == "FACE":
            from core.specialists.face_gpt import FaceGPT
            self._specialists[domain] = FaceGPT()
        elif domain == "AGE":
            from core.specialists.age_gpt import AgeGPT
            self._specialists[domain] = AgeGPT()
        elif domain == "VOICE":
            from core.specialists.voice_gpt import VoiceGPT
            self._specialists[domain] = VoiceGPT()
        elif domain == "UNIVERSAL_ID":
            from core.specialists.universal_id_gpt import UniversalIdentificationGPT
            self._specialists[domain] = UniversalIdentificationGPT()
        elif domain == "ADVISOR":
            from core.specialists.advisor_gpt import AdvisorGPT
            self._specialists[domain] = AdvisorGPT()
        elif domain == "PHILOSOPHER":
            from core.specialists.philosopher_gpt import PhilosopherGPT
            self._specialists[domain] = PhilosopherGPT()

        return self._specialists.get(domain)

    def classify_intent(self, text: str) -> List[str]:
        """Identifies which domain specialists are relevant to the query."""
        t = str(text or "").lower()
        matched: List[str] = []

        # Astro & Horoscope
        if any(w in t for w in ["zodiac", "horoscope", "kundli", "birth chart", "rashi", "nakshatra", "astrology", "astrological", "rashifal"]):
            matched.append("ASTRO")

        # Space & Astronomy
        if any(w in t for w in ["black hole", "galaxy", "nebula", "planet", "solar system", "cosmology", "astronomy", "astrophysics", "jwst", "telescope", "star", "hubble", "exoplanet"]):
            matched.append("SPACE")

        # Mythology & Ancient Texts
        if any(w in t for w in ["mythology", "mythological", "ramayana", "mahabharata", "gita", "vedas", "purana", "zeus", "odin", "thor", "greek myth", "norse", "egyptian myth", "itihasa"]):
            matched.append("MYTHOLOGY")

        # Facial Recognition
        if any(w in t for w in ["recognize face", "face detection", "owner face", "camera face", "who is in front"]):
            matched.append("FACE")

        # Age Intelligence
        if any(w in t for w in ["how old", "approximate age", "estimate age", "age of this", "what is his age", "what is her age", "age estimation"]):
            matched.append("AGE")

        # Voice Intelligence
        if any(w in t for w in ["voice intelligence", "who is speaking", "diarization", "barge in", "interruption", "mic status", "background noise"]):
            matched.append("VOICE")

        # Universal Identification
        if any(w in t for w in ["identify this", "what is this object", "what product", "identify object", "what plant", "what landmark", "what device"]):
            matched.append("UNIVERSAL_ID")

        # Suggestion & Advisory
        if any(w in t for w in ["suggest", "advice", "recommend", "how should i plan", "planning", "study plan", "career advice", "what should i do"]):
            matched.append("ADVISOR")

        # Philosophy
        if any(w in t for w in ["philosophy", "philosophical", "meaning of life", "existential", "stoicism", "free will", "consciousness", "ethics", "moral dilemma", "vedanta", "epistemology"]):
            matched.append("PHILOSOPHER")

        return matched

    def route_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Routes the query to the appropriate specialist(s) and synthesizes the response.
        If multiple specialists are matched, coordinates across them.
        """
        domains = self.classify_intent(query)
        if not domains:
            return {
                "handled": False,
                "domains": [],
                "response": None,
                "message": "Query does not require domain specialist handling; continuing with general model pipeline."
            }

        # Multi-domain synthesis (e.g. Space + Mythology)
        if len(domains) > 1:
            responses = []
            for d in domains:
                spec = self._get_specialist(d)
                if spec and hasattr(spec, "query"):
                    responses.append(spec.query(query))
            combined_text = "\n\n---\n\n".join(responses)
            return {
                "handled": True,
                "domains": domains,
                "multi_specialist": True,
                "response": combined_text,
                "source": f"Cross-domain collaboration: {', '.join(domains)}"
            }

        # Single domain execution
        primary_domain = domains[0]
        spec = self._get_specialist(primary_domain)
        if spec and hasattr(spec, "query"):
            res = spec.query(query)
            return {
                "handled": True,
                "domains": [primary_domain],
                "multi_specialist": False,
                "response": res,
                "source": primary_domain
            }

        return {
            "handled": False,
            "domains": domains,
            "response": None,
            "message": "Specialist matched but execution handler unavailable."
        }


_orchestrator: Optional[SpecialistOrchestrator] = None


def get_specialist_orchestrator() -> SpecialistOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SpecialistOrchestrator()
    return _orchestrator
