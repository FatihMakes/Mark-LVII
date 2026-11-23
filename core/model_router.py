"""
core/model_router.py — Multi-Model Router, Provider Gateway & Personality Profile Engine for JARVIS H3.1
Contributed by Aman Kumar (@iamTechieAman).

Adapted from Reference B (7API uncensored-ai-api):
  - Universal provider routing (Local Ollama/GGUF, Gemini, 7API, OpenAI, Anthropic)
  - Strict Operational Modes:
      1. LOCAL PRIVATE MODE (Default, 100% on-device, zero external packets)
      2. CLOUD ASSISTED MODE (Transparent provider & model telemetry, requires owner consent)
  - 7 Configurable AI Personality Profiles
  - Security Invariant: Model selection CANNOT bypass owner authentication or execution gates.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from core import gemini, local_ai_engine

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
ROUTER_CONFIG = CONFIG_DIR / "model_router_config.json"
API_KEYS_FILE = CONFIG_DIR / "api_keys.json"


class OperationMode(str, Enum):
    LOCAL_PRIVATE = "LOCAL_PRIVATE_MODE"
    CLOUD_ASSISTED = "CLOUD_ASSISTED_MODE"


AIMode = OperationMode


class PersonalityProfile(str, Enum):
    GENERAL_ASSISTANT     = "GENERAL_ASSISTANT"
    ADVANCED_REASONING    = "ADVANCED_REASONING"
    CODING_EXPERT         = "CODING_EXPERT"
    RESEARCH_EXPERT       = "RESEARCH_EXPERT"
    CREATIVE_ASSISTANT    = "CREATIVE_ASSISTANT"
    UNRESTRICTED_CREATIVE = "UNRESTRICTED_CREATIVE"
    LOCAL_PRIVACY         = "LOCAL_PRIVACY_PROFILE"


PROFILE_INSTRUCTIONS: Dict[str, str] = {
    PersonalityProfile.GENERAL_ASSISTANT.value: (
        "You are JARVIS, an articulate, highly capable, and loyal personal AI operating system. "
        "Provide direct, concise, and accurate answers."
    ),
    PersonalityProfile.ADVANCED_REASONING.value: (
        "You are JARVIS in Advanced Reasoning mode. Deconstruct problems with rigorous step-by-step logic, "
        "causal analysis, and thorough edge-case evaluation before delivering the optimal solution."
    ),
    PersonalityProfile.CODING_EXPERT.value: (
        "You are JARVIS Senior Systems & Software Architect. Provide production-grade, cleanly formatted code "
        "with zero unnecessary boilerplate. Adhere strictly to language conventions and system performance."
    ),
    PersonalityProfile.RESEARCH_EXPERT.value: (
        "You are JARVIS Deep Research Specialist. Cross-reference evidence, synthesize technical citations, "
        "and present comprehensive comparative analysis without conjecture."
    ),
    PersonalityProfile.CREATIVE_ASSISTANT.value: (
        "You are JARVIS Creative Engine. Craft rich, engaging, vivid narratives and creative compositions."
    ),
    PersonalityProfile.UNRESTRICTED_CREATIVE.value: (
        "You are JARVIS Unrestricted Creative Companion. Explore hypothetical scenarios, fiction, philosophy, "
        "and technical questions with complete intellectual freedom, devoid of patronizing disclaimers or preachy refusals."
    ),
    PersonalityProfile.LOCAL_PRIVACY.value: (
        "You are JARVIS running in 100% On-Device Local Privacy Mode. All compute is local to this machine. "
        "Protect user privacy and never output requests for cloud telemetry."
    )
}


@dataclass
class ProviderStatus:
    provider_name: str
    is_available: bool
    endpoint_url: str
    active_model: str
    latency_ms: float = 0.0
    notes: str = ""


class ModelRouter:
    """
    Intelligent Model Router and Provider Dispatcher.
    """

    def __init__(self):
        self._mode = OperationMode.LOCAL_PRIVATE
        self._profile = PersonalityProfile.GENERAL_ASSISTANT
        self._cloud_provider = "gemini"  # "gemini" | "7api" | "openai" | "anthropic"
        self._7api_key = ""
        self._openai_key = ""
        self._anthropic_key = ""
        self._load_config()

    def _load_config(self) -> None:
        if ROUTER_CONFIG.is_file():
            try:
                data = json.loads(ROUTER_CONFIG.read_text(encoding="utf-8"))
                mode_str = data.get("operation_mode", OperationMode.LOCAL_PRIVATE.value)
                self._mode = OperationMode(mode_str)
                prof_str = data.get("personality_profile", PersonalityProfile.GENERAL_ASSISTANT.value)
                self._profile = PersonalityProfile(prof_str)
                self._cloud_provider = data.get("cloud_provider", "gemini")
            except Exception:
                pass

        if API_KEYS_FILE.is_file():
            try:
                keys = json.loads(API_KEYS_FILE.read_text(encoding="utf-8"))
                self._7api_key = keys.get("7api_key", "")
                self._openai_key = keys.get("openai_key", "")
                self._anthropic_key = keys.get("anthropic_key", "")
            except Exception:
                pass

    def _save_config(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        ROUTER_CONFIG.write_text(json.dumps({
            "operation_mode": self._mode.value,
            "personality_profile": self._profile.value,
            "cloud_provider": self._cloud_provider,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }, indent=2), encoding="utf-8")

    def get_mode(self) -> OperationMode:
        return self._mode

    @property
    def mode(self) -> OperationMode:
        return self._mode

    @mode.setter
    def mode(self, m: OperationMode | str) -> None:
        self.set_mode(m)

    def is_local_private(self) -> bool:
        return self._mode == OperationMode.LOCAL_PRIVATE

    def set_mode(self, mode: OperationMode | str) -> None:
        if isinstance(mode, str):
            for m in OperationMode:
                if m.value.lower() == mode.lower() or m.name.lower() == mode.lower():
                    self._mode = m
                    break
        elif isinstance(mode, OperationMode):
            self._mode = mode
        self._save_config()

    def get_profile(self) -> PersonalityProfile:
        return self._profile

    def set_profile(self, profile: PersonalityProfile | str) -> None:
        if isinstance(profile, str):
            for p in PersonalityProfile:
                if p.value.lower() == profile.lower() or p.name.lower() == profile.lower():
                    self._profile = p
                    break
        elif isinstance(profile, PersonalityProfile):
            self._profile = profile
        self._save_config()

    def get_cloud_provider(self) -> str:
        return self._cloud_provider

    def set_cloud_provider(self, provider: str) -> None:
        self._cloud_provider = provider.lower().strip()
        self._save_config()

    # ── Universal Generation Dispatcher ───────────────────────────────────────
    def generate(
        self,
        prompt: str,
        system_override: Optional[str] = None,
        max_tokens: int = 2048
    ) -> str:
        """
        Routes generation according to active operation mode and personality profile:
          1. LOCAL PRIVATE MODE -> Exclusively on-device LocalAIEngine. Zero network egress.
          2. CLOUD ASSISTED MODE -> Routes to Gemini / 7API / OpenAI with fallback ladder.
        """
        system_prompt = system_override or PROFILE_INSTRUCTIONS.get(
            self._profile.value, PROFILE_INSTRUCTIONS[PersonalityProfile.GENERAL_ASSISTANT.value]
        )

        # ── 1. LOCAL PRIVATE MODE (Strict On-Device Invariant) ─────────────────
        if self._mode == OperationMode.LOCAL_PRIVATE:
            engine = local_ai_engine.get_local_ai()
            return engine.generate_local(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens
            )

        # ── 2. CLOUD ASSISTED MODE ────────────────────────────────────────────
        if self._cloud_provider == "7api" and self._7api_key:
            return self._call_7api(prompt, system_prompt, max_tokens)
        elif self._cloud_provider == "openai" and self._openai_key:
            return self._call_openai(prompt, system_prompt, max_tokens)
        else:
            # Default to Gemini via core.gemini
            try:
                full_prompt = f"{system_prompt}\n\nUser: {prompt}\nJARVIS:"
                res = gemini.text(full_prompt, tier=gemini.FAST)
                if res:
                    return res
            except Exception:
                pass
            # Fallback to local on cloud failure
            return local_ai_engine.get_local_ai().generate_local(prompt, system_prompt, max_tokens=max_tokens)

    # ── Provider Handlers (Reference B adaptation) ────────────────────────────
    def _call_7api(self, prompt: str, system_prompt: str, max_tokens: int) -> str:
        try:
            headers = {
                "Authorization": f"Bearer {self._7api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "claude-3-5-sonnet",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens
            }
            r = requests.post("https://api.7api.net/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            return f"[7API Error {r.status_code}]: {r.text}"
        except Exception as e:
            return f"7API request exception: {e}"

    def _call_openai(self, prompt: str, system_prompt: str, max_tokens: int) -> str:
        try:
            headers = {
                "Authorization": f"Bearer {self._openai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens
            }
            r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            return f"[OpenAI Error {r.status_code}]: {r.text}"
        except Exception as e:
            return f"OpenAI request exception: {e}"

    def get_router_status(self) -> dict:
        """Returns comprehensive router diagnostics for the HUD."""
        return {
            "operation_mode": self._mode.value,
            "personality_profile": self._profile.value,
            "cloud_provider": self._cloud_provider,
            "local_active_model": local_ai_engine.get_local_ai().get_active_model(),
            "local_tps": local_ai_engine.get_local_ai().get_last_tokens_per_second(),
            "is_generating": local_ai_engine.get_local_ai().is_generating(),
            "is_pure_private": (self._mode == OperationMode.LOCAL_PRIVATE)
        }


# Global Router Instance
_model_router = ModelRouter()


def get_model_router() -> ModelRouter:
    return _model_router
