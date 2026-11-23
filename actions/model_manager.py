"""
actions/model_manager.py — Local AI Engine, Model Router & Personality Profile Controller for JARVIS H3.1
Contributed by Aman Kumar (@iamTechieAman).

Supports commands:
  - "JARVIS, enable local private mode" / "Switch to cloud assisted mode"
  - "JARVIS, set AI personality to coding expert" / "Set profile to advanced reasoning"
  - "JARVIS, stop generation" / "Cancel AI output"
  - "JARVIS, switch model to deepseek-r1:8b"
  - "JARVIS, list local models" / "Show AI model catalog"
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from core import local_ai_engine, model_router
from core.model_router import OperationMode, PersonalityProfile

ROOT_DIR = Path(__file__).resolve().parent.parent


def model_manager(parameters: dict, player=None, session_memory=None) -> str:
    """
    Manages local inference engine, model router, personality profiles, and stop generation.
    """
    router = model_router.get_model_router()
    local_ai = local_ai_engine.get_local_ai()

    action = (parameters.get("action") or "status").lower().strip()
    target = parameters.get("target") or parameters.get("model") or parameters.get("profile")

    if action in ("status", "info"):
        st = router.get_router_status()
        mem_ok, mem_str = local_ai.check_memory_headroom(4.0)

        lines = [
            "# 🧠 JARVIS H3.1 Model Router & Local AI Status",
            f"**Operation Mode:** `{st['operation_mode']}`",
            f"**Personality Profile:** `{st['personality_profile']}`",
            f"**Active Local Model:** `{st['local_active_model']}`",
            f"**Local Inference Speed:** `{st['local_tps']} tokens/sec`",
            f"**Memory Headroom:** {mem_str}",
            "",
            "### 🔒 Privacy Boundary:",
            f"- **100% On-Device Local Private:** `{'YES — Zero external egress' if st['is_pure_private'] else 'NO — Cloud Assisted Active'}`",
            f"- **Configured Cloud Provider:** `{st['cloud_provider']}`",
            "",
            "> [!TIP]",
            "> Say `JARVIS, enable local private mode` to lock all AI processing strictly to on-device neural hardware."
        ]
        md_text = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("AI Model Router Status", md_text)

        mode_desc = "Local Private Mode (100% on-device)" if st["is_pure_private"] else f"Cloud Assisted Mode ({st['cloud_provider']})"
        return f"AI Model Router is active in {mode_desc}, running profile {st['personality_profile']} with model {st['local_active_model']}."

    elif action in ("set_mode", "mode", "toggle_privacy"):
        if not target:
            target = "local_private" if router.get_mode() == OperationMode.CLOUD_ASSISTED else "cloud_assisted"

        if "local" in target.lower() or "private" in target.lower():
            router.set_mode(OperationMode.LOCAL_PRIVATE)
            if player and hasattr(player, "write_log"):
                player.write_log("SYS: Switched to 100% On-Device LOCAL PRIVATE MODE.")
            return "Switched to Local Private Mode, sir. All neural inference, speech processing, and memory are now restricted 100% to your local Apple Silicon machine."
        else:
            router.set_mode(OperationMode.CLOUD_ASSISTED)
            if player and hasattr(player, "write_log"):
                player.write_log("SYS: Switched to CLOUD ASSISTED MODE.")
            return "Switched to Cloud Assisted Mode, sir. Cloud model providers are now enabled with transparent telemetry."

    elif action in ("set_profile", "profile", "personality"):
        if not target:
            return (
                "Please specify a personality profile: general, reasoning, coding, "
                "research, creative, unrestricted, or privacy."
            )

        t_clean = target.lower()
        if "reason" in t_clean:
            prof = PersonalityProfile.ADVANCED_REASONING
        elif "code" in t_clean or "coding" in t_clean or "dev" in t_clean:
            prof = PersonalityProfile.CODING_EXPERT
        elif "research" in t_clean:
            prof = PersonalityProfile.RESEARCH_EXPERT
        elif "unrestricted" in t_clean:
            prof = PersonalityProfile.UNRESTRICTED_CREATIVE
        elif "creative" in t_clean:
            prof = PersonalityProfile.CREATIVE_ASSISTANT
        elif "privacy" in t_clean:
            prof = PersonalityProfile.LOCAL_PRIVACY
        else:
            prof = PersonalityProfile.GENERAL_ASSISTANT

        router.set_profile(prof)
        return f"AI personality profile updated to {prof.value}, sir."

    elif action in ("stop", "stop_generation", "cancel", "abort"):
        local_ai.stop_generation()
        if player and hasattr(player, "write_log"):
            player.write_log("SYS: Inference cancelled by user. Resources safely released.")
        return "Ongoing AI generation has been stopped immediately, sir. Local buffers released."

    elif action in ("set_model", "switch", "switch_model"):
        if not target:
            return "Please specify the local model ID to switch to (e.g., 'qwen2.5:7b', 'llama3.2:3b', 'deepseek-r1:8b')."
        ok, msg = local_ai.set_active_model(target.strip())
        return msg

    elif action in ("list", "models", "installed"):
        models = local_ai.list_installed_models()
        if not models:
            return "No local Ollama or GGUF models were detected. Ensure Ollama is running (`ollama serve`) or models are placed in `models/`."
        table = [
            "# 📦 Installed Local Models",
            "| Model ID | Source | Size (GB) | Status |",
            "|---|---|---|---|"
        ]
        for m in models:
            status = "🟢 ACTIVE" if m.get("is_active") else "Available"
            table.append(f"| `{m['model_id']}` | {m['source']} | {m['size_gb']} GB | {status} |")
        md_text = "\n".join(table)
        if player and hasattr(player, "show_content"):
            player.show_content("Installed Local Models", md_text)
        return f"Found {len(models)} local models installed on your machine. Active model is {local_ai.get_active_model()}."

    elif action in ("catalog", "available"):
        cat = local_ai.get_model_catalog()
        table = [
            "# 🛒 Tested Local AI Models for Apple Silicon",
            "| Model | Family | Param | Quant | Min RAM | Compatible | Installed |",
            "|---|---|---|---|---|---|---|"
        ]
        for m in cat:
            compat = "✅ Yes" if m.get("memory_compatible") else "❌ Low RAM"
            inst = "Installed" if m.get("is_installed") else "Available"
            table.append(
                f"| `{m['model_id']}` | {m['family']} | {m['parameter_size']} | "
                f"{m['quantization']} | {m['min_ram_gb']} GB | {compat} | {inst} |"
            )
        md_text = "\n".join(table)
        if player and hasattr(player, "show_content"):
            player.show_content("Local Model Catalog", md_text)
        return f"Listed {len(cat)} tested local models calibrated for Apple Silicon unified memory."

    return "Supported actions: status | set_mode | set_profile | set_model | stop | list | catalog"


TOOL = {
    "name": "model_manager",
    "description": (
        "Local AI engine, model router, and personality profile manager for JARVIS H3.1. "
        "Allows toggling between 100% on-device Local Private Mode and Cloud Assisted Mode, "
        "selecting AI personality profiles (General, Reasoning, Coding, Research, Creative, Unrestricted, Privacy), "
        "listing installed local GGUF/Ollama models, and stopping generation immediately."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | set_mode | set_profile | set_model | stop | list | catalog (default: status)"
            },
            "target": {
                "type": "STRING",
                "description": "Model ID, mode name (local_private / cloud_assisted), or profile name"
            }
        }
    },
    "handler": model_manager,
}
