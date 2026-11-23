"""
core/specialists/voice_gpt.py — Voice Intelligence Specialist GPT for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Provides:
- Voice biometrics & enrolled speaker verification.
- Speaker diarization (multi-speaker separation and overlap detection).
- Background noise classification.
- Real-time barge-in and double-talk metrics.
- Owner-first priority voice command routing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.barge_in import get_barge_in_engine
from core.speaker_intelligence import get_speaker_engine

logger = logging.getLogger("jarvis.specialists.voice")


class VoiceGPT:
    """Voice Intelligence & Diarization domain specialist."""

    def __init__(self):
        self.domain = "VOICE_INTELLIGENCE"
        self._speaker_engine = get_speaker_engine()
        self._barge_in = get_barge_in_engine()

    def get_status_overview(self) -> Dict[str, Any]:
        """Returns comprehensive telemetry of voice pipeline, speakers, and barge-in engine."""
        return {
            "status": "OPERATIONAL",
            "enrolled_profiles": self._speaker_engine.list_enrolled_profiles(),
            "barge_in_telemetry": self._barge_in.get_telemetry(),
            "double_talk_supported": True,
            "speaker_diarization_active": True,
            "owner_first_priority": True
        }

    def query(self, prompt: str) -> str:
        status = self.get_status_overview()
        b_tel = status["barge_in_telemetry"]
        return (
            f"# 🎙️ Voice Intelligence & Full-Duplex Subsystem\n\n"
            f"- **Enrolled Profiles:** `{len(status['enrolled_profiles'])} active`\n"
            f"- **Barge-In Mode:** `Active (Sensitivity: {b_tel['sensitivity'].title()})`\n"
            f"- **Measured Interruption Latency:** `{b_tel['average_latency_ms']:.1f} ms` (Target: < 300 ms)\n"
            f"- **Total Barge-Ins Handled:** `{b_tel['total_interruptions']}`\n"
            f"- **Acoustic Echo Cancellation:** `Calibrated (Floor: {b_tel['echo_floor']})`\n\n"
            f"The voice intelligence pipeline continuously distinguishes your voice from audio playback, "
            f"enabling instant real-time conversational interruption."
        )
