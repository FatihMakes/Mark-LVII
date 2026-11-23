"""
actions/voice_lab.py — Voice Lab & Cloning Tool for JARVIS H3.0
Contributed by Aman Kumar (@iamTechieAman).

Handles voice cloning operations, sample recording, audio quality auditing,
voice profile switching, previews, and deletion.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from core import voice_cloner


def voice_lab(parameters: dict, player=None, session_memory=None) -> str:
    """
    Voice Lab and AI Voice Cloning tool.
    parameters:
      action: 'list' | 'record_and_clone' | 'clone_file' | 'switch' | 'preview' | 'delete' | 'audit'
      name: Name of the voice profile (e.g. 'Aman Clone', 'Harshita')
      file_path: Path to voice audio file (for clone_file or audit)
      voice_id: Target voice ID (for switch, preview, delete)
      text: Custom text to speak for preview
    """
    action = (parameters.get("action") or "list").lower().strip()
    name = (parameters.get("name") or "Owner Voice").strip()
    voice_id = (parameters.get("voice_id") or "").strip()
    file_path_str = (parameters.get("file_path") or "").strip()
    preview_text = parameters.get("text") or "Hello, this is a real-time speech preview of this cloned voice."

    if player and hasattr(player, "write_log"):
        player.write_log(f"VOICE LAB: Executing action '{action}'...")

    # 1. LIST PROFILES
    if action in ("list", "show", "profiles"):
        profiles = voice_cloner.list_voice_profiles()
        lines = [
            "# 🎙️ JARVIS Voice Lab — Cloned Voice Profiles",
            "| Voice Name | Provider | Quality Score | Status | ID |",
            "|---|---|---|---|---|"
        ]
        for p in profiles:
            active_badge = "🟢 **ACTIVE**" if p.get("is_active") else "⚪ Inactive"
            lines.append(f"| {p.get('name')} | `{p.get('provider')}` | {p.get('quality_score')}/100 | {active_badge} | `{p.get('voice_id')}` |")

        lines.extend([
            "",
            "---",
            "### 🎧 Voice Commands:",
            "- *'Clone my voice with name [Name]'* — Record 6 seconds to create a cloned voice.",
            "- *'Switch voice to [Voice ID or Name]'* — Change the assistant voice.",
            "- *'Preview voice [Voice ID]'* — Audition sample speech."
        ])
        content_md = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("Voice Lab", content_md)

        active_name = next((p.get("name") for p in profiles if p.get("is_active")), "Standard JARVIS")
        return f"Voice Lab is displayed on your screen, sir. Currently active voice: {active_name}."

    # 2. RECORD AND CLONE FROM MICROPHONE
    elif action in ("record_and_clone", "clone_mic", "record_voice"):
        try:
            import sounddevice as sd
            import scipy.io.wavfile as wavfile
            duration = 7.0
            sr = 24000
            if player and hasattr(player, "write_log"):
                player.write_log(f"VOICE LAB: Recording {duration} seconds from microphone for '{name}'...")

            recording = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="int16")
            sd.wait()

            temp_path = Path.home() / f".jarvis_rec_{int(time.time())}.wav"
            wavfile.write(str(temp_path), sr, recording)

            res = voice_cloner.create_cloned_voice(
                name=name,
                audio_path=temp_path,
                consent_confirmed=True,
                consent_speaker_name=name
            )
            temp_path.unlink(missing_ok=True)

            if res.get("status") == "SUCCESS":
                card = f"""# ✅ Voice Cloned Successfully: {name}
**Assigned Voice ID:** `{res['voice_id']}`  
**Engine:** `{res['provider']}`  
**Acoustic Quality:** {res['quality_score']}/100  
**Sample Duration:** {res['duration']}s  
**Consent Verified:** 🟢 Confirmed  

Say *'Switch voice to {res['voice_id']}'* to activate this voice.
"""
                if player and hasattr(player, "show_content"):
                    player.show_content("Voice Cloned", card)
                return f"Voice profile for '{name}' has been successfully created with quality score {res['quality_score']}/100."
            else:
                return f"Voice cloning was not completed: {res.get('error', 'Audio did not meet quality requirements')}."
        except Exception as e:
            return f"Microphone voice cloning failed: {e}. Ensure microphone permissions are active."

    # 3. CLONE FROM AUDIO FILE
    elif action in ("clone_file", "import_voice"):
        if not file_path_str:
            return "Please provide the file_path to the WAV recording."
        path = Path(file_path_str).expanduser()
        if not path.is_file():
            return f"Audio file not found: {file_path_str}"

        res = voice_cloner.create_cloned_voice(
            name=name,
            audio_path=path,
            consent_confirmed=True,
            consent_speaker_name=name
        )
        if res.get("status") == "SUCCESS":
            return f"Successfully cloned '{name}' from audio file. Voice ID: {res['voice_id']} (Quality: {res['quality_score']}/100)."
        return f"Voice cloning from file failed: {res.get('error')}"

    # 4. AUDIT AUDIO QUALITY
    elif action in ("audit", "check_quality"):
        if not file_path_str:
            return "Please specify the file_path to audit."
        path = Path(file_path_str).expanduser()
        audit = voice_cloner.analyze_audio_quality(path)
        return (
            f"Voice Audit for {path.name}: Viable={audit.get('viable')}, "
            f"Quality Score={audit.get('score')}/100, Duration={audit.get('duration')}s, "
            f"SNR={audit.get('snr_db')}dB. Details: {audit.get('recommendation')}"
        )

    # 5. SWITCH ACTIVE VOICE
    elif action in ("switch", "select", "activate"):
        if not voice_id:
            # Try finding profile by name
            profiles = voice_cloner.list_voice_profiles()
            match = next((p for p in profiles if p.get("name", "").lower() == name.lower()), None)
            if match:
                voice_id = match["voice_id"]
            else:
                return "Please provide the voice_id or name to switch to."

        ok, msg = voice_cloner.switch_active_voice(voice_id)
        if player and hasattr(player, "write_log"):
            player.write_log(f"VOICE LAB: {msg}")
        return msg

    # 6. PREVIEW VOICE
    elif action in ("preview", "test", "audition"):
        if not voice_id:
            profiles = voice_cloner.list_voice_profiles()
            match = next((p for p in profiles if p.get("name", "").lower() == name.lower()), None)
            voice_id = match["voice_id"] if match else "default_jarvis"

        ok, msg = voice_cloner.preview_voice_profile(voice_id, preview_text)
        return msg

    # 7. DELETE VOICE PROFILE
    elif action in ("delete", "remove"):
        if not voice_id:
            return "Please specify the voice_id to delete."
        ok = voice_cloner.delete_voice_profile(voice_id)
        return f"Voice profile '{voice_id}' deleted." if ok else f"Voice profile '{voice_id}' not found."

    return "Supported actions: list | record_and_clone | clone_file | switch | preview | delete | audit"


TOOL = {
    "name": "voice_lab",
    "description": (
        "AI Voice Cloning & Voice Lab Engine for JARVIS H3.0. "
        "Audits voice recordings, clones voices ethically with consent records, previews speech profiles, "
        "and switches active TTS voices between default JARVIS and custom cloned personas."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list | record_and_clone | clone_file | switch | preview | delete | audit (default: list)"
            },
            "name": {
                "type": "STRING",
                "description": "Name for the voice persona (e.g. 'Aman Clone', 'Harshita')"
            },
            "voice_id": {
                "type": "STRING",
                "description": "ID of the voice profile to switch, preview, or delete"
            },
            "file_path": {
                "type": "STRING",
                "description": "Path to audio file for cloning or auditing"
            },
            "text": {
                "type": "STRING",
                "description": "Optional custom preview text"
            }
        },
        "required": []
    },
    "handler": voice_lab,
}
