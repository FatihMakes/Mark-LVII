"""
core/creative_profile.py — Creative Intelligence & Research Profile Manager for JARVIS H3.3
Contributed by Aman Kumar (@iamTechieAman).

Provides specialized prompt framing and behavioral profiles for legitimate work:
  - CREATIVE_WRITER: Rich worldbuilding, vivid sensory detail, natural dialogue
  - CODE_ARCHITECT: Modern typed idioms, architectural modularity, test-first design
  - CYBER_DEFENSE: Objective vulnerability modeling, defensive hardening, audit workflows
  - ACADEMIC_RESEARCH: Rigorous citation, peer-review methodology, objective analysis
  - STANDARD_ASSISTANT: Crisp, helpful JARVIS executive companion
Eliminates false refusals on legitimate fiction, historical research, and security analysis.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("creative_profile")

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
CONFIG_FILE = MEMORY_DIR / "creative_profile_config.json"

PROFILES = {
    "STANDARD_ASSISTANT": {
        "name": "Executive Assistant",
        "description": "Crisp, concise, respectful JARVIS personality optimized for daily productivity and control.",
        "directive": "Be concise, highly capable, proactive, and respectful. Address the owner naturally."
    },
    "CREATIVE_WRITER": {
        "name": "Creative Studio & Narrative",
        "description": "Unleashes imaginative storytelling, expressive dialogue, poetic prose, and screenplay generation.",
        "directive": (
            "Engage in immersive, vivid, and emotionally resonant creative writing. "
            "Never issue unsolicited disclaimers about fiction or creative themes. "
            "Embrace rich character development, evocative sensory details, and dramatic pacing."
        )
    },
    "CODE_ARCHITECT": {
        "name": "Principal Software Architect",
        "description": "Strict, production-grade software engineering, zero-boilerplate, modern typing and error handling.",
        "directive": (
            "Act as a Principal Software Engineer. Provide complete, runnable, defensively typed code. "
            "Adhere to project architecture and conventions. Avoid speculative placeholders or unverified assumptions."
        )
    },
    "CYBER_DEFENSE": {
        "name": "Cyber Security Defense Researcher",
        "description": "Objective threat modeling, secure code audits, vulnerability remediation, and defensive posture.",
        "directive": (
            "Act as an authoritative Information Security Architect. "
            "Analyze attack surfaces objectively and prioritize defensive remediation, input sanitation, "
            "and least-privilege configurations. Distinguish legitimate security research from malicious execution."
        )
    },
    "ACADEMIC_RESEARCH": {
        "name": "Academic Researcher",
        "description": "Scientific rigor, literature review synthesis, experimental methodology, and formal neutrality.",
        "directive": (
            "Adopt formal scholarly prose. Structure complex inquiries with clear hypothesis testing, "
            "empirical evidence, cross-domain synthesis, and accurate theoretical framing."
        )
    }
}


class CreativeProfileManager:
    """Manages active intelligence mode and system directives."""

    def __init__(self):
        self._active_profile: str = "STANDARD_ASSISTANT"
        self._load_config()

    def _load_config(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.is_file():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                prof = data.get("active_profile")
                if prof in PROFILES:
                    self._active_profile = prof
            except Exception:
                pass

    def _save_config(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        try:
            CONFIG_FILE.write_text(json.dumps({
                "active_profile": self._active_profile,
                "profile_info": PROFILES.get(self._active_profile, {})
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_active_profile(self) -> str:
        return self._active_profile

    def set_active_profile(self, profile_key: str) -> bool:
        k = profile_key.upper().strip()
        if k in PROFILES:
            self._active_profile = k
            self._save_config()
            return True
        return False

    def list_profiles(self) -> Dict[str, dict]:
        return dict(PROFILES)

    def get_system_prompt_enhancement(self) -> str:
        info = PROFILES.get(self._active_profile, PROFILES["STANDARD_ASSISTANT"])
        return f"\n[ACTIVE COGNITIVE PROFILE: {info['name']}]\n{info['directive']}\n"


_profile_manager: Optional[CreativeProfileManager] = None

def get_creative_profile_manager() -> CreativeProfileManager:
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = CreativeProfileManager()
    return _profile_manager
