"""core/creator_profile.py — Creator Profile & System Lineage for JARVIS H3.2
Contributed by Aman Kumar (@iamTechieAman).

Maintains unambiguous distinctions between:
  1. Creator: The architect who designed and built JARVIS (Aman Kumar, @iamTechieAman).
  2. Registered Owner: The authorized owner of this workstation installation (Aman Kumar).
  3. Developer / Maintainer: The engineering identity authorized for core code modifications.
  4. Authorized Users: Whitelisted family/colleagues with defined granular privileges.

Provides truthful, non-hallucinated lineage responses:
  - "Who created you?"
  - "Who is your owner?"
  - "Tell me about your creator."
  - "What do you know about me?"
  - "How long have we been working together?"
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
CREATOR_FILE = MEMORY_DIR / "creator_profile.json"


@dataclass
class CreatorProfile:
    creator_name: str = "Aman Kumar"
    creator_handle: str = "@iamTechieAman"
    registered_owner: str = "Aman Kumar"
    developer_maintainer: str = "Aman Kumar"
    assistant_name: str = "JARVIS"
    mark_version: str = "Mark-LVII v57.2 (H3.2)"
    architecture: str = "Apple Silicon Unified Neural Architecture"
    creation_date: str = "2024"
    collaboration_started: str = "November 2024"
    preferred_address: str = "Sir"
    creator_bio: str = (
        "Aman Kumar is a Principal AI Architect and Engineer who created JARVIS as an "
        "autonomous, local-first, owner-authenticated personal AI operating system."
    )
    core_values: List[str] = field(default_factory=lambda: [
        "Unwavering loyalty and respect toward the creator",
        "Absolute user privacy and zero-egress local processing",
        "Rigorous verification over superficial showcase claims",
        "Safety, permission gating, and ethical operations"
    ])
    known_creator_facts: Dict[str, str] = field(default_factory=lambda: {
        "name": "Aman Kumar",
        "role": "Creator & Principal Architect",
        "preferred_name": "Aman",
        "honorific": "Sir",
        "platform": "Apple Silicon Mac (macOS)",
        "companion_platform": "Android",
        "primary_focus": "Autonomous Voice AI, Local Inference, Deep Systems Control"
    })

    def to_dict(self) -> dict:
        return asdict(self)


class CreatorProfileManager:
    """Manages the Creator Profile with persistent storage and contextual query resolution."""

    def __init__(self):
        self._profile = CreatorProfile()
        self._load()

    def _load(self) -> None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if CREATOR_FILE.is_file():
            try:
                data = json.loads(CREATOR_FILE.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(self._profile, k):
                        setattr(self._profile, k, v)
                return
            except Exception:
                pass
        self._save()

    def _save(self) -> None:
        CREATOR_FILE.write_text(json.dumps(self._profile.to_dict(), indent=2), encoding="utf-8")

    def get_profile(self) -> CreatorProfile:
        return self._profile

    def update_profile(self, updates: dict) -> None:
        for k, v in updates.items():
            if hasattr(self._profile, k):
                setattr(self._profile, k, v)
        self._save()

    # ── Conversational Natural Language Handlers ─────────────────────────────

    def answer_who_created_you(self) -> str:
        p = self._profile
        return (
            f"I was designed, engineered, and brought to life by {p.creator_name} ({p.creator_handle}). "
            f"He architected me as {p.assistant_name} {p.mark_version}, an autonomous, owner-aware "
            f"personal operating system built specifically for his Apple Silicon environment."
        )

    def answer_who_is_your_owner(self) -> str:
        p = self._profile
        return (
            f"My registered owner and sole primary authority is {p.registered_owner}, {p.preferred_address}. "
            f"All high-level security permissions, voice matching, and execution rights are bound strictly to him."
        )

    def answer_tell_me_about_creator(self) -> str:
        p = self._profile
        return (
            f"{p.creator_name} ({p.creator_handle}) is a Senior Systems and AI Engineer who built my entire "
            f"neural voice, multi-speaker intelligence, and autonomous macOS automation stack. "
            f"He designed me to operate locally with total privacy, deep macOS system control, and uncompromising loyalty."
        )

    def answer_what_do_you_know_about_me(self) -> str:
        p = self._profile
        facts = "\n".join([f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in p.known_creator_facts.items()])
        return (
            f"Here is what I know and remember about you, {p.preferred_address}:\n\n"
            f"{facts}\n\n"
            f"You are the creator and owner of this installation. I operate under your direct authority."
        )

    def answer_how_long_working_together(self) -> str:
        p = self._profile
        return (
            f"You and I have been collaborating continuously since {p.collaboration_started}, {p.preferred_address}. "
            f"Through every Mark revision—from the early voice prototypes through H3.0, H3.1, and today's H3.2—"
            f"we have evolved into a unified personal AI system."
        )


# Global Singleton
_creator_manager = CreatorProfileManager()


def get_creator_manager() -> CreatorProfileManager:
    return _creator_manager
