"""
actions/speaker_manager.py — Multi-Speaker Intelligence, Active Speaker Lock & Diarization Manager for JARVIS H3.1
Contributed by Aman Kumar (@iamTechieAman).

Supports commands:
  - "JARVIS, who is speaking?" / "Speaker status" / "Show speaker intelligence"
  - "JARVIS, lock session to owner" / "Owner priority mode"
  - "JARVIS, call me Sir" / "Set preferred address to Aman"
  - "JARVIS, test multi speaker overlap"
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import numpy as np

from core import permissions
from core.speaker_intelligence import get_speaker_engine

ROOT_DIR = Path(__file__).resolve().parent.parent


def speaker_manager(parameters: dict, player=None, session_memory=None) -> str:
    """
    Manages multi-speaker intelligence, active speaker lock, diarization dashboard, and testing.
    """
    engine = get_speaker_engine()
    action = (parameters.get("action") or "status").lower().strip()
    preferred_name = parameters.get("preferred_name") or parameters.get("address")

    if action in ("status", "telemetry", "info"):
        telem = engine.get_speaker_telemetry()
        lines = [
            "# 🎙️ JARVIS H3.1 Multi-Speaker Intelligence Telemetry",
            f"**Active Speaker:** `{telem['current_speaker']}` | **Speaker ID:** `{telem['speaker_id']}`",
            f"**Preferred Form of Address:** `{telem['preferred_address']}`",
            f"**Authentication:** `{telem['authentication_status']}` ({int(telem['recognition_confidence'] * 100)}% Confidence)",
            "",
            "### 🔒 Active Session Lock & Diarization State:",
            f"- **Active Conversation Locked:** `{'YES — Locked to ' + telem['lock_owner'] if telem['active_conversation_locked'] else 'NO (Standby)'}`",
            f"- **Background Noise Level:** `{telem['background_noise_db']} dBFS`",
            f"- **Overlapping Speech Detected:** `{'YES (Suppression Active)' if telem['is_overlapping'] else 'NO'}`",
            f"- **Acoustic Echo Cancellation:** `{telem['echo_cancellation']}`",
            f"- **Microphone Calibration:** `{telem['mic_calibration_status']}`",
            "",
            "> [!NOTE]",
            "> While Active Speaker Lock is engaged, unrelated background voices are prevented from hijacking or interrupting the owner's conversation."
        ]
        md_content = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("Speaker Intelligence Dashboard", md_content)

        lock_str = "Active Speaker Lock is engaged for the owner." if telem["active_conversation_locked"] else "Ready and listening for authorized speech."
        return f"Multi-speaker intelligence is operational, {telem['preferred_address']}. {lock_str}"

    elif action in ("lock_owner", "lock", "priority_mode"):
        engine._lock_active = True
        engine._locked_speaker_id = "OWNER_001"
        engine._lock_timestamp = time.time()
        permissions.set_current_speaker(permissions.UserRole.OWNER)
        telem = engine.get_speaker_telemetry()
        if player and hasattr(player, "write_log"):
            player.write_log("SYS: Active Speaker Lock engaged for OWNER_001.")
        return f"Active Speaker Lock engaged, {telem['preferred_address']}. All background turns will be strictly isolated until your conversation turn concludes."

    elif action in ("unlock", "release"):
        engine.release_active_lock()
        return "Active Speaker Lock released. Listening for all recognized household members."

    elif action in ("set_address", "address", "nickname"):
        if not preferred_name:
            return "Please specify how you would like me to address you (e.g., 'Sir', 'Ma'am', or your name)."
        engine._owner_profile.preferred_address = preferred_name.strip()
        # Persist in memory/owner_identity.json
        from core import identity_engine
        prof = identity_engine.load_owner_profile() or {}
        prof["preferred_address"] = preferred_name.strip()
        identity_engine.save_owner_profile(prof)
        return f"Understood. I will address you as {preferred_name} from now on."

    elif action in ("test_overlap", "simulate_overlap"):
        # Generate two synthetic simultaneous audio voices (e.g. 120Hz + 220Hz)
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        v1 = 0.4 * np.sin(2 * np.pi * 125 * t)
        v2 = 0.4 * np.sin(2 * np.pi * 215 * t)
        overlap_audio = ((v1 + v2) * 32767).astype(np.int16)

        res = engine.process_speech_turn(overlap_audio, sr, "Simulated overlap")
        if res.is_overlapping:
            return f"Overlap detection test passed: {res.rejection_reason}"
        return "Overlap test completed."

    elif action in ("test_background_rejection", "test_lock"):
        # Engage lock
        engine._lock_active = True
        engine._locked_speaker_id = "OWNER_001"
        engine._lock_timestamp = time.time()

        # Simulate background non-owner speech
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        # Random noise / unknown pitch
        bg_audio = (0.3 * np.sin(2 * np.pi * 320 * t) * 32767).astype(np.int16)
        res = engine.process_speech_turn(bg_audio, sr, "Turn on the lights")

        if not res.actionable_speech and "ignored" in res.rejection_reason.lower():
            return "Background rejection test passed: Unrelated background speech was ignored while owner session was active."
        return f"Background test completed: {res.rejection_reason}"

    return "Supported actions: status | lock_owner | unlock | set_address | test_overlap | test_background_rejection"


TOOL = {
    "name": "speaker_manager",
    "description": (
        "Multi-speaker intelligence, active speaker lock, diarization dashboard, and background voice isolation manager for JARVIS H3.1. "
        "Allows viewing live speaker recognition telemetry, configuring preferred forms of address, locking session to the owner, and testing overlap detection."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | lock_owner | unlock | set_address | test_overlap | test_background_rejection (default: status)"
            },
            "preferred_name": {
                "type": "STRING",
                "description": "Preferred form of address (e.g. 'Sir', 'Ma'am', 'Aman', 'Boss')"
            }
        }
    },
    "handler": speaker_manager,
}

run = speaker_manager
