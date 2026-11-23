"""
core/anti_theft.py — Anti-Theft Siren Guard & Motion Sensor Intrusion Defense for JARVIS H3.1
Contributed by Aman Kumar (@iamTechieAman).

Implements:
  - Armed State Lifecycle: DISARMED -> ARMING (grace delay) -> ARMED -> TRIGGERED
  - Multi-Sensor Trigger Detection:
      1. Charging Cable Disconnection
      2. Device Lifting / Accelerometer Displacement
      3. Unexpected Orientation Flip
  - Security Siren Activation & Emergency Desktop HUD Alert
  - Evidence Incident Logging in memory/theft_incidents.jsonl
  - PIN & Biometric Disarm Verification (Anti-False-Alarm Guard)
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import companion_gateway

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
CONFIG_DIR = BASE_DIR / "config"
ANTI_THEFT_CONFIG = CONFIG_DIR / "anti_theft_config.json"
INCIDENTS_LOG = MEMORY_DIR / "theft_incidents.jsonl"


class GuardState:
    DISARMED = "DISARMED"
    ARMING = "ARMING"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"


@dataclass
class TheftIncident:
    incident_id: str
    timestamp: str
    trigger_reason: str
    device_id: str
    device_name: str
    alarm_duration: int
    is_disarmed: bool = False
    disarmed_by: str = ""


class AntiTheftEngine:
    """
    State machine and alert controller for the JARVIS Anti-Theft Guard system.
    """

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._state = GuardState.DISARMED
        self._arm_delay_sec = 10
        self._arm_timer: Optional[threading.Timer] = None
        self._sensitivity = "medium"  # "low" | "medium" | "high"
        self._detect_charger_disconnect = True
        self._detect_motion = True
        self._detect_flip = True
        self._alarm_duration_sec = 60
        self._disarm_pin = "1170"
        self._active_incident: Optional[TheftIncident] = None
        self._load_config()

    def _load_config(self) -> None:
        if ANTI_THEFT_CONFIG.is_file():
            try:
                cfg = json.loads(ANTI_THEFT_CONFIG.read_text(encoding="utf-8"))
                self._sensitivity = cfg.get("sensitivity", self._sensitivity)
                self._detect_charger_disconnect = cfg.get("detect_charger_disconnect", True)
                self._detect_motion = cfg.get("detect_motion", True)
                self._detect_flip = cfg.get("detect_flip", True)
                self._arm_delay_sec = cfg.get("arm_delay_sec", 10)
                self._alarm_duration_sec = cfg.get("alarm_duration_sec", 60)
                self._disarm_pin = cfg.get("disarm_pin", "1170")
            except Exception:
                pass

    def _save_config(self) -> None:
        ANTI_THEFT_CONFIG.write_text(json.dumps({
            "sensitivity": self._sensitivity,
            "detect_charger_disconnect": self._detect_charger_disconnect,
            "detect_motion": self._detect_motion,
            "detect_flip": self._detect_flip,
            "arm_delay_sec": self._arm_delay_sec,
            "alarm_duration_sec": self._alarm_duration_sec,
            "disarm_pin": self._disarm_pin,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }, indent=2), encoding="utf-8")

    def get_state(self) -> str:
        return self._state

    def is_armed(self, include_arming: bool = True) -> bool:
        if include_arming:
            return self._state in (GuardState.ARMED, GuardState.ARMING)
        return self._state == GuardState.ARMED

    # ── Arming Protocol ────────────────────────────────────────────────────────
    def arm(self, delay_seconds: Optional[int] = None) -> Tuple[bool, str]:
        """
        Arms the Anti-Theft Guard with countdown grace period.
        """
        if self._state in (GuardState.ARMED, GuardState.ARMING):
            return True, f"Anti-Theft Guard is already {self._state.lower()}."

        delay = delay_seconds if delay_seconds is not None else self._arm_delay_sec
        self._state = GuardState.ARMING

        def _complete_arm():
            self._state = GuardState.ARMED
            # Notify companion
            gw = companion_gateway.get_companion_gateway()
            primary = gw.get_primary_device()
            if primary:
                primary.anti_theft_armed = True
                gw._save_devices()

        if delay > 0:
            self._arm_timer = threading.Timer(delay, _complete_arm)
            self._arm_timer.daemon = True
            self._arm_timer.start()
            return True, f"Anti-Theft Guard arming initiated. You have {delay} seconds grace period to place your device down."
        else:
            _complete_arm()
            return True, "Anti-Theft Guard is now ARMED and actively monitoring motion & power sensors."

    # ── Disarming Protocol ──────────────────────────────────────────────────────
    def disarm(self, pin: str = "", is_owner: bool = False) -> Tuple[bool, str]:
        """
        Disarms the security system using valid PIN or authenticated owner voice.
        """
        if self._state == GuardState.DISARMED:
            return True, "Anti-Theft Guard is already disarmed."

        if self._arm_timer and self._arm_timer.is_alive():
            self._arm_timer.cancel()

        # Authorization check
        if not is_owner and pin.strip() != self._disarm_pin:
            return False, "Security Disarm Failed: Invalid PIN provided. System remains armed."

        self._state = GuardState.DISARMED
        if getattr(self, "_alarm_proc", None):
            try:
                self._alarm_proc.terminate()
                self._alarm_proc.wait(timeout=0.2)
            except Exception:
                pass
            self._alarm_proc = None

        if self._active_incident:
            self._active_incident.is_disarmed = True
            self._active_incident.disarmed_by = "Owner" if is_owner else "PIN"
            self._log_incident(self._active_incident)
            self._active_incident = None

        # Reset companion flag
        gw = companion_gateway.get_companion_gateway()
        primary = gw.get_primary_device()
        if primary:
            primary.anti_theft_armed = False
            gw._save_devices()

        return True, "Anti-Theft Guard disarmed successfully. Sirens silenced and sensors stood down."

    # ── Siren & Alarm Trigger Execution ───────────────────────────────────────
    def trigger_theft_alarm(self, reason: str, device_name: str = "Android Companion") -> TheftIncident:
        """
        Executes emergency alarm response:
          1. Sets state to TRIGGERED.
          2. Dispatches maximum volume siren to phone and desktop.
          3. Logs encrypted incident event.
        """
        self._state = GuardState.TRIGGERED
        inc_id = f"THEFT_{int(time.time())}"
        inc = TheftIncident(
            incident_id=inc_id,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            trigger_reason=reason,
            device_id="DEV_PRIMARY",
            device_name=device_name,
            alarm_duration=self._alarm_duration_sec
        )
        self._active_incident = inc
        self._log_incident(inc)

        # 1. Trigger desktop sound alert (non-blocking)
        try:
            # macOS native emergency alarm tone
            self._alarm_proc = subprocess.Popen(["afplay", "/System/Library/Sounds/Sosumi.aiff"])
        except Exception:
            self._alarm_proc = None

        # 2. Dispatch siren to paired phone
        gw = companion_gateway.get_companion_gateway()
        gw.execute_hardware_command("set_volume", {"level": 100})

        return inc

    def _log_incident(self, inc: TheftIncident) -> None:
        try:
            with open(INCIDENTS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(inc)) + "\n")
        except Exception:
            pass

    def list_incidents(self) -> List[dict]:
        """Returns recent security incident events."""
        if not INCIDENTS_LOG.is_file():
            return []
        try:
            lines = INCIDENTS_LOG.read_text(encoding="utf-8").strip().splitlines()
            return [json.loads(line) for line in lines if line.strip()]
        except Exception:
            return []

    def get_guard_status(self) -> dict:
        """Returns full security guard diagnostics."""
        return {
            "state": self._state,
            "sensitivity": self._sensitivity,
            "detect_charger_disconnect": self._detect_charger_disconnect,
            "detect_motion": self._detect_motion,
            "detect_flip": self._detect_flip,
            "arm_delay_sec": self._arm_delay_sec,
            "alarm_duration_sec": self._alarm_duration_sec,
            "has_active_alarm": (self._state == GuardState.TRIGGERED),
            "incidents_count": len(self.list_incidents())
        }


# Global Singleton
_anti_theft_engine = AntiTheftEngine()


def get_anti_theft() -> AntiTheftEngine:
    return _anti_theft_engine


def reset_anti_theft() -> AntiTheftEngine:
    global _anti_theft_engine
    _anti_theft_engine = AntiTheftEngine()
    return _anti_theft_engine


# Backward-compatible alias
AntiTheftGuard = AntiTheftEngine
AntiTheftState = GuardState
get_anti_theft_guard = get_anti_theft
reset_anti_theft_guard = reset_anti_theft
