"""
core/barge_in.py — Full-Duplex Real-Time Voice Barge-In & Interruption Engine for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Implements real-time double-talk detection, acoustic echo reference subtraction,
adaptive sensitivity thresholding, sub-300ms interruption dispatch, and audio buffer flushing.
Enables the owner to interrupt JARVIS mid-speech naturally (e.g. "Wait", "Stop", "Ruko", "Suno").
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, List, Optional, Tuple

import numpy as np
from core.echo import EchoGuard

logger = logging.getLogger("jarvis.barge_in")


@dataclass
class BargeInMetrics:
    total_interruptions: int = 0
    last_interruption_time: float = 0.0
    last_detected_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    recent_latencies: List[float] = field(default_factory=list)
    double_talk_triggers: int = 0
    keyword_triggers: int = 0


# Recognized interruption keywords across English, Hindi, and Hinglish
INTERRUPT_KEYWORDS = [
    "wait", "stop", "hold on", "listen", "no i mean", "that is not",
    "repeat", "pause", "continue", "ruko", "suno", "chup", "ek minute",
    "dhyan se suno", "arey ruko", "nahi mera matlab", "ruk jao", "hold"
]


class BargeInEngine:
    """
    Real-time full-duplex interruption engine.
    Monitors microphone audio while TTS playback is actively sounding.
    Differentiates between assistant echo and actual user speech.
    """

    def __init__(
        self,
        echo_guard: Optional[EchoGuard] = None,
        interrupt_callback: Optional[Callable[[], None]] = None,
        sensitivity: str = "medium"
    ):
        self._echo = echo_guard or EchoGuard()
        self._interrupt_cb = interrupt_callback
        self._sensitivity = sensitivity

        # Sensitivity configurations
        # required_blocks at ~50ms block size: 3 blocks = 150ms
        self._sensitivity_config = {
            "high": {"min_user_level": 0.05, "required_blocks": 2, "headroom_mult": 1.05},
            "medium": {"min_user_level": 0.08, "required_blocks": 3, "headroom_mult": 1.15},
            "low": {"min_user_level": 0.12, "required_blocks": 5, "headroom_mult": 1.30},
        }

        self._consecutive_speech_blocks = 0
        self._speech_onset_time: Optional[float] = None
        self._is_active = True
        self._metrics = BargeInMetrics()

        # Audio buffer for buffered pre-roll speech delivery upon interruption
        self._barge_in_buffer: Deque[np.ndarray] = deque(maxlen=8)

        # Cooldown guard: prevent re-triggering within 400ms of an interruption
        self._last_interrupt_event = 0.0
        self._min_interrupt_interval = 0.40

    @property
    def metrics(self) -> BargeInMetrics:
        return self._metrics

    @property
    def sensitivity(self) -> str:
        return self._sensitivity

    def set_sensitivity(self, level: str) -> None:
        if level in self._sensitivity_config:
            self._sensitivity = level
            logger.info(f"[BargeIn] Interruption sensitivity set to: {level}")

    def reset_state(self) -> None:
        """Resets running counters when playback turn concludes."""
        self._consecutive_speech_blocks = 0
        self._speech_onset_time = None
        self._barge_in_buffer.clear()

    def process_mic_frame(
        self,
        indata: np.ndarray,
        sample_rate: int,
        is_speaking: bool,
        current_out_level: float = 0.0
    ) -> Tuple[bool, Optional[float]]:
        """
        Processes a single incoming microphone block while JARVIS is speaking.
        Returns:
            (is_interrupted: bool, latency_ms: Optional[float])
        """
        if not self._is_active or not is_speaking:
            self._consecutive_speech_blocks = 0
            self._speech_onset_time = None
            return False, None

        now = time.monotonic()
        if (now - self._last_interrupt_event) < self._min_interrupt_interval:
            return False, None

        # Calculate RMS energy level of incoming block
        lvl = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))) / 32768.0 if indata.size > 0 else 0.0
        cfg = self._sensitivity_config.get(self._sensitivity, self._sensitivity_config["medium"])

        if lvl < cfg["min_user_level"]:
            self._consecutive_speech_blocks = max(0, self._consecutive_speech_blocks - 1)
            if self._consecutive_speech_blocks == 0:
                self._speech_onset_time = None
            return False, None

        # Store recent audio in pre-roll buffer so words spoken during onset are preserved
        self._barge_in_buffer.append(indata.copy())

        # Check with EchoGuard whether this block is distinct speech or playback echo
        is_user_speech = self._echo.is_user_speech(indata, sample_rate, lvl)

        if is_user_speech:
            if self._speech_onset_time is None:
                self._speech_onset_time = now

            self._consecutive_speech_blocks += 1

            # Check if sustained blocks satisfy threshold
            if self._consecutive_speech_blocks >= cfg["required_blocks"]:
                latency_ms = (now - self._speech_onset_time) * 1000.0

                # Log and track metrics
                self._metrics.total_interruptions += 1
                self._metrics.last_interruption_time = now
                self._metrics.last_detected_latency_ms = latency_ms
                self._metrics.double_talk_triggers += 1
                self._metrics.recent_latencies.append(latency_ms)
                if len(self._metrics.recent_latencies) > 20:
                    self._metrics.recent_latencies.pop(0)
                self._metrics.average_latency_ms = float(np.mean(self._metrics.recent_latencies))

                self._last_interrupt_event = now
                self._consecutive_speech_blocks = 0
                self._speech_onset_time = None

                logger.info(
                    f"[BargeIn] 🚨 Owner voice interruption detected! Latency: {latency_ms:.1f}ms "
                    f"(lvl={lvl:.3f}, out={current_out_level:.3f})"
                )

                # Dispatch callback
                if self._interrupt_cb:
                    try:
                        self._interrupt_cb()
                    except Exception as e:
                        logger.error(f"[BargeIn] Interrupt callback error: {e}")

                return True, latency_ms
        else:
            # Echo matched: decay counter
            self._consecutive_speech_blocks = max(0, self._consecutive_speech_blocks - 1)
            if self._consecutive_speech_blocks == 0:
                self._speech_onset_time = None

        return False, None

    def get_preroll_audio(self) -> List[np.ndarray]:
        """Returns captured audio blocks leading up to the interruption."""
        frames = list(self._barge_in_buffer)
        self._barge_in_buffer.clear()
        return frames

    def get_telemetry(self) -> Dict[str, any]:
        return {
            "sensitivity": self._sensitivity,
            "total_interruptions": self._metrics.total_interruptions,
            "last_latency_ms": round(self._metrics.last_detected_latency_ms, 2),
            "average_latency_ms": round(self._metrics.average_latency_ms, 2),
            "double_talk_triggers": self._metrics.double_talk_triggers,
            "echo_calibrated": self._echo.calibrated,
            "echo_floor": round(self._echo.floor, 3),
            "echo_reliable": self._echo.reliable
        }


_barge_in_engine: Optional[BargeInEngine] = None


def get_barge_in_engine(
    echo_guard: Optional[EchoGuard] = None,
    interrupt_callback: Optional[Callable[[], None]] = None
) -> BargeInEngine:
    global _barge_in_engine
    if _barge_in_engine is None:
        _barge_in_engine = BargeInEngine(
            echo_guard=echo_guard,
            interrupt_callback=interrupt_callback
        )
    elif interrupt_callback and _barge_in_engine._interrupt_cb is None:
        _barge_in_engine._interrupt_cb = interrupt_callback
    return _barge_in_engine
