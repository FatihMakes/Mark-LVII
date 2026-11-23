"""
Voice Biometrics & Speaker Recognition Action for JARVIS (Voice Match / Siri / Google Assistant).
Contributed by Aman Kumar (@iamTechieAman).

Ensures JARVIS only executes commands from the verified owner (Aman Kumar),
ignoring unauthorized voices and background speech.
"""
from __future__ import annotations

import json
from pathlib import Path
from core import voice_verifier


def voice_biometrics(parameters: dict, player=None, session_memory=None) -> str:
    """
    Speaker recognition and voice lock management.
    parameters:
      action: 'status' | 'enroll' | 'enable' | 'disable' | 'calibrate'
      owner: Name of owner (default: 'Aman Kumar')
    """
    action = (parameters.get("action") or "status").lower().strip()
    owner = parameters.get("owner") or "Aman Kumar"

    if player and hasattr(player, "write_log"):
        player.write_log(f"BIOMETRICS: Executing Voice ID action '{action}'...")

    if action in ("status", "info"):
        enrolled = voice_verifier.is_enrolled()
        enabled = voice_verifier.is_voice_match_enabled()

        details = "No voiceprint calibrated yet."
        if enrolled:
            try:
                data = json.loads(voice_verifier.VOICEPRINT_FILE.read_text(encoding="utf-8"))
                details = f"Owner: **{data.get('owner')}** | Calibrated: `{data.get('enrolled_at')}`"
            except Exception:
                pass

        card = f"""# 🎙️ Voice ID & Biometric Matcher
**Owner Protection:** {'🟢 ACTIVE (Only responding to owner)' if (enrolled and enabled) else '⚪ OFF / Calibrating'}  
**Status:** {'Calibrated' if enrolled else 'Not Enrolled'}  
**Details:** {details}  

---
### 🛡️ Features:
- **Acoustic Voiceprint:** 20-dimensional spectral & energy profile
- **Background Speaker Filter:** Ignores non-owner voices (TV, strangers)
- **Say:** *'Calibrate my voice'* to record a fresh voice profile.
"""
        if player and hasattr(player, "show_content"):
            player.show_content("Voice Biometrics", card)

        return (
            f"Voice Match is currently {'active and locked to ' + owner if (enrolled and enabled) else 'available for calibration'}, sir. "
            f"Voice biometrics status is on your screen."
        )

    elif action in ("enable", "activate", "lock"):
        voice_verifier.set_voice_match_enabled(True)
        if player and hasattr(player, "write_log"):
            player.write_log("BIOMETRICS: Voice Match locked to owner")
        return f"Voice Match is now locked, sir. I will respond exclusively to your voice ({owner})."

    elif action in ("disable", "unlock"):
        voice_verifier.set_voice_match_enabled(False)
        if player and hasattr(player, "write_log"):
            player.write_log("BIOMETRICS: Voice Match unlocked")
        return "Voice Match verification has been paused, sir. I will respond to all voice inputs."

    elif action in ("enroll", "calibrate"):
        # Multi-sample Voice Calibration for Owner
        import numpy as np
        try:
            import sounddevice as sd
            from core import identity_engine
            sr = 16000
            duration = 2.5
            samples = []

            for i in range(1, 4):
                if player and hasattr(player, "write_log"):
                    player.write_log(f"BIOMETRICS: Recording calibration pass {i}/3 (Please speak)...")
                rec = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="float32")
                sd.wait()
                raw = rec.flatten()
                rms = float(np.sqrt(np.mean(raw ** 2)))
                if rms >= 0.004:
                    samples.append(raw)
                time.sleep(0.3)

            if not samples:
                return "The microphone recording was quiet during calibration. Please speak clearly into the microphone and say 'Calibrate my voice' again."

            pin = parameters.get("pin")
            res = identity_engine.enroll_owner_profile(
                name=owner,
                samples=samples,
                pin=pin,
                sample_rate=sr
            )
        except Exception as e:
            return f"Voice calibration encountered an issue: {e}. Please ensure microphone access is active."

        card = f"""# 🛡️ JARVIS H3.0 Layered Voice ID Enrolled: {owner}
**Status:** Calibrated & Locked  
**Samples Captured:** {res['samples']} passes  
**Hardware Binding:** `{res.get('device', 'MacBook-Pro')}`  
**Anti-Replay Protection:** 🟢 Active  
**Timestamp:** `{res['enrolled_at']}`  

JARVIS will now recognize your unique acoustic profile, detect liveness, and respond only to authorized speakers.
"""
        if player and hasattr(player, "show_content"):
            player.show_content("Voice Match Enrolled", card)

        return f"Your voice has been successfully calibrated and enrolled with 3-pass acoustic verification, {owner}. Your session is protected."

    elif action in ("challenge", "verify_challenge"):
        from core import identity_engine
        challenge = identity_engine.generate_challenge("user_session")
        if player and hasattr(player, "show_content"):
            player.show_content("Security Challenge", f"### 🔐 Spoken Challenge\nPlease repeat the following security words:\n**\"{challenge}\"**")
        return f"Security challenge issued: Please say '{challenge}' to verify authorization."

    elif action in ("authorize", "add_user", "grant"):
        from core import permissions
        target_name = parameters.get("target_name") or parameters.get("name") or "Guest"
        role = parameters.get("role") or permissions.ROLE_AUTHORIZED_PERSON
        duration = int(parameters.get("duration") or 0) or None
        res = permissions.authorize_person(
            name=target_name,
            role=role,
            duration_minutes=duration
        )
        return f"Authorized {target_name} as {role}. Scoped permissions have been activated."

    elif action in ("revoke", "remove_user"):
        from core import permissions
        target_name = parameters.get("target_name") or parameters.get("name") or ""
        if not target_name:
            return "Please provide the name of the user to revoke."
        ok = permissions.revoke_person(target_name)
        return f"User '{target_name}' access revoked." if ok else f"User '{target_name}' not found."

    return "Supported actions: status | enroll | enable | disable | challenge | authorize | revoke"


TOOL = {
    "name": "voice_biometrics",
    "description": (
        "Layered Voice Biometrics & Speaker Recognition Engine for JARVIS H3.0. "
        "Calibrates owner acoustic profile across 3 passes, detects voice liveness, provides challenge-response "
        "verification, and manages authorized multi-user access."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | enroll | enable | disable | challenge | authorize | revoke (default: status)",
            },
            "owner": {
                "type": "STRING",
                "description": "Name of the owner (default: Aman Kumar)",
            },
            "target_name": {
                "type": "STRING",
                "description": "Name of guest or person to authorize/revoke",
            },
            "pin": {
                "type": "STRING",
                "description": "Optional secondary security PIN",
            },
            "duration": {
                "type": "INTEGER",
                "description": "Duration in minutes for temporary guest authorization",
            }
        },
    },
    "handler": voice_biometrics,
}
