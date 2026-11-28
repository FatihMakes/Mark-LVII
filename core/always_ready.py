"""
core/always_ready.py — Always-Ready Listening & macOS Power-Management Engine for JARVIS H3.5
Contributed by Aman Kumar (@iamTechieAman).

Maintains low-power continuous listening, wake-word readiness, intelligent macOS power assertion
management (caffeinate), thermal & battery awareness, and component-isolated audio recovery.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("jarvis.always_ready")

CONFIG_FILE = Path("memory/always_ready_config.json")


class AssistantListeningState(str, Enum):
    ACTIVE_CONVERSATION = "ACTIVE_CONVERSATION"
    ALWAYS_READY_LISTENING = "ALWAYS_READY_LISTENING"
    PRIVACY_LOCKED = "PRIVACY_LOCKED"


class AlwaysReadyEngine:
    """Manages continuous availability, power state, and low-power wake-word listening."""

    def __init__(self):
        self._state: AssistantListeningState = AssistantListeningState.ALWAYS_READY_LISTENING
        self._caffeinate_proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._last_user_activity = time.monotonic()
        self._active_tasks_count = 0
        self._config = self._load_config()

        # State change callbacks
        self._state_callbacks: list[Callable[[AssistantListeningState], None]] = []

    def _load_config(self) -> Dict[str, Any]:
        defaults = {
            "always_ready_enabled": True,
            "prevent_sleep_during_tasks": True,
            "keep_awake_when_screen_locked": False,
            "respect_battery_threshold": True,
            "battery_critical_percent": 15,
            "low_power_sample_rate": 16000,
            "idle_sleep_timeout_seconds": 3600
        }
        if CONFIG_FILE.is_file():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                defaults.update(data)
            except Exception as e:
                logger.warning(f"Could not load always_ready_config.json: {e}")
        return defaults

    def save_config(self) -> None:
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(self._config, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save always_ready_config: {e}")

    @property
    def state(self) -> AssistantListeningState:
        with self._lock:
            return self._state

    def set_state(self, new_state: AssistantListeningState) -> None:
        with self._lock:
            if self._state == new_state:
                return
            old_state = self._state
            self._state = new_state
            logger.info(f"[AlwaysReady] State transition: {old_state.value} → {new_state.value}")

        for cb in self._state_callbacks:
            try:
                cb(new_state)
            except Exception as e:
                logger.error(f"[AlwaysReady] Callback error: {e}")

    def register_state_callback(self, cb: Callable[[AssistantListeningState], None]) -> None:
        self._state_callbacks.append(cb)

    # ── Power Management (macOS caffeinate) ───────────────────────────────────

    def start_task(self, task_name: str = "unnamed_task") -> None:
        """Call when a background task or voice conversation begins."""
        with self._lock:
            self._active_tasks_count += 1
            self._last_user_activity = time.monotonic()

            if self._config.get("prevent_sleep_during_tasks") and self._caffeinate_proc is None:
                self._acquire_caffeinate_lock(task_name)

    def finish_task(self, task_name: str = "unnamed_task") -> None:
        """Call when a background task or turn ends."""
        with self._lock:
            self._active_tasks_count = max(0, self._active_tasks_count - 1)
            self._last_user_activity = time.monotonic()

            if self._active_tasks_count == 0:
                self._release_caffeinate_lock()

    def _acquire_caffeinate_lock(self, reason: str = "") -> None:
        """Invokes native macOS caffeinate to prevent system sleep during critical work."""
        if os.name != "posix" or not Path("/usr/bin/caffeinate").exists():
            return
        try:
            # -d: prevent display sleep
            # -i: prevent system idle sleep
            # -m: prevent disk idle sleep
            # -s: prevent system sleep while on AC
            # -w <pid>: exit when this process exits
            pid = str(os.getpid())
            self._caffeinate_proc = subprocess.Popen(
                ["/usr/bin/caffeinate", "-d", "-i", "-s", "-w", pid],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.debug(f"[AlwaysReady] macOS caffeinate lock acquired ({reason}, pid={pid})")
        except Exception as e:
            logger.warning(f"[AlwaysReady] Could not start caffeinate: {e}")

    def _release_caffeinate_lock(self) -> None:
        if self._caffeinate_proc is not None:
            try:
                self._caffeinate_proc.terminate()
                self._caffeinate_proc.wait(timeout=1.0)
            except Exception:
                pass
            finally:
                self._caffeinate_proc = None
                logger.debug("[AlwaysReady] macOS caffeinate lock released — normal power behaviour restored.")

    # ── Battery & Thermal Telemetry ───────────────────────────────────────────

    def get_power_telemetry(self) -> Dict[str, Any]:
        batt_pct = 100.0
        is_charging = True
        thermal_pressure = "nominal"

        # Check psutil if battery is supported
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt:
                batt_pct = batt.percent
                is_charging = batt.power_plugged
        except Exception:
            pass

        # Check macOS pmset if on Darwin
        if os.name == "posix":
            try:
                res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=2)
                if "%" in res.stdout:
                    parts = res.stdout.split("%")
                    val_str = parts[0].split()[-1]
                    batt_pct = float(val_str)
                    is_charging = "AC Power" in res.stdout or "charging" in res.stdout.lower()
            except Exception:
                pass

            try:
                therm = subprocess.run(["pmset", "-g", "thermalsubsys"], capture_output=True, text=True, timeout=2)
                if "Thermal_Pressure" in therm.stdout:
                    thermal_pressure = "elevated" if "Nominal" not in therm.stdout else "nominal"
            except Exception:
                pass

        is_critical = (
            self._config.get("respect_battery_threshold", True)
            and not is_charging
            and batt_pct <= self._config.get("battery_critical_percent", 15)
        )

        return {
            "battery_percent": batt_pct,
            "is_charging": is_charging,
            "thermal_pressure": thermal_pressure,
            "is_battery_critical": is_critical,
            "active_tasks_count": self._active_tasks_count,
            "caffeinate_active": self._caffeinate_proc is not None,
            "current_state": self._state.value
        }

    # ── Self-Healing Audio Recovery ───────────────────────────────────────────

    def recover_audio_stream(
        self,
        stream_name: str,
        restart_fn: Callable[[], Any]
    ) -> bool:
        """Restarts a failed audio stream component without restarting the whole app."""
        logger.warning(f"[AlwaysReady] Initiating isolated recovery for audio stream: {stream_name}")
        try:
            time.sleep(0.15)
            restart_fn()
            logger.info(f"[AlwaysReady] Successfully recovered {stream_name}")
            return True
        except Exception as e:
            logger.error(f"[AlwaysReady] Recovery failed for {stream_name}: {e}")
            return False


_always_ready_engine: Optional[AlwaysReadyEngine] = None


def get_always_ready_engine() -> AlwaysReadyEngine:
    global _always_ready_engine
    if _always_ready_engine is None:
        _always_ready_engine = AlwaysReadyEngine()
    return _always_ready_engine
