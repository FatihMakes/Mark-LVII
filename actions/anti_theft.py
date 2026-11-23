"""
actions/anti_theft.py — Anti-Theft Siren Guard & Motion Defense Tool for JARVIS H3.1
Contributed by Aman Kumar (@iamTechieAman).

Supports voice commands:
  - "JARVIS, arm anti-theft guard" / "Secure my phone"
  - "JARVIS, disarm security PIN 1170" / "Silence alarm"
  - "JARVIS, anti-theft status" / "Show theft incidents"
  - "JARVIS, test anti-theft siren"
"""
from __future__ import annotations

import json
from pathlib import Path

from core import anti_theft, permissions

ROOT_DIR = Path(__file__).resolve().parent.parent


def anti_theft_action(parameters: dict, player=None, session_memory=None) -> str:
    """
    Controls Anti-Theft Guard state: arming, disarming with PIN/voice, incident logs, and testing.
    """
    engine = anti_theft.get_anti_theft()
    action = (parameters.get("action") or "status").lower().strip()
    pin = parameters.get("pin") or ""
    delay = parameters.get("delay")

    # 1. Arming
    if action in ("arm", "enable", "secure"):
        delay_val = int(delay) if delay is not None else 10
        ok, msg = engine.arm(delay_seconds=delay_val)
        if player and hasattr(player, "write_log"):
            player.write_log(f"SYS: Anti-Theft Guard arming initiated ({delay_val}s grace).")
        return msg

    # 2. Disarming
    elif action in ("disarm", "silence", "stand_down"):
        is_owner = (permissions.get_current_speaker() == permissions.UserRole.OWNER.value)
        ok, msg = engine.disarm(pin=pin, is_owner=is_owner)
        if player and hasattr(player, "write_log"):
            player.write_log(f"SYS: Anti-Theft Guard disarm: {'SUCCESS' if ok else 'FAILED'}.")
        return msg

    # 3. Status & Telemetry
    elif action in ("status", "info"):
        st = engine.get_guard_status()
        state_badge = "🔴 TRIGGERED (ALARM)" if st["state"] == "TRIGGERED" else (
            "🟢 ARMED 🛡️" if st["state"] == "ARMED" else (
                "🟠 ARMING (Grace Period)" if st["state"] == "ARMING" else "⚪ DISARMED"
            )
        )
        lines = [
            "# 🛡️ JARVIS H3.1 Anti-Theft Siren Guard",
            f"**Current Status:** {state_badge}",
            f"**Motion Sensitivity:** `{st['sensitivity'].upper()}`",
            "",
            "### 📡 Monitored Sensor Triggers:",
            f"- **Charging Cable Disconnect:** `{'ACTIVE ✅' if st['detect_charger_disconnect'] else 'Disabled'}`",
            f"- **Motion & Accelerometer Displacement:** `{'ACTIVE ✅' if st['detect_motion'] else 'Disabled'}`",
            f"- **Orientation Flip:** `{'ACTIVE ✅' if st['detect_flip'] else 'Disabled'}`",
            f"- **Grace Period Delay:** `{st['arm_delay_sec']} seconds`",
            f"- **Alarm Duration:** `{st['alarm_duration_sec']} seconds`",
            f"- **Recorded Incident History:** `{st['incidents_count']} incidents`"
        ]
        if player and hasattr(player, "show_content"):
            player.show_content("Anti-Theft Guard Status", "\n".join(lines))
        return f"Anti-Theft Guard is currently {st['state'].lower()}, sir. All sensor monitors are operational."

    # 4. Incident Logs
    elif action in ("incidents", "logs", "history"):
        incidents = engine.list_incidents()
        if not incidents:
            return "No theft or intrusion incidents recorded, sir. The system has been secure."
        table = [
            "# 🚨 Recorded Security Incidents",
            "| Incident ID | Timestamp | Trigger Reason | Device | Status |",
            "|---|---|---|---|---|"
        ]
        for inc in incidents[-8:]:
            status = f"Disarmed by {inc.get('disarmed_by', 'Owner')}" if inc.get("is_disarmed") else "Active Alarm"
            table.append(
                f"| `{inc['incident_id']}` | {inc['timestamp']} | {inc['trigger_reason']} | "
                f"{inc['device_name']} | {status} |"
            )
        if player and hasattr(player, "show_content"):
            player.show_content("Security Incidents", "\n".join(table))
        return f"Retrieved {len(incidents)} security incidents from the audit ledger, sir."

    # 5. Simulated Test Trigger
    elif action in ("test_trigger", "test", "siren"):
        inc = engine.trigger_theft_alarm("Simulated Intrusion Test: Device Lifted & Cable Disconnected")
        if player and hasattr(player, "show_content"):
            player.show_content(
                "🚨 SECURITY ALERT: ANTI-THEFT TRIGGERED",
                f"**Trigger Reason:** {inc.trigger_reason}\n\n"
                f"**Device:** {inc.device_name}\n\n"
                f"**Timestamp:** `{inc.timestamp}`\n\n"
                "> Maximum volume emergency siren active. Say **'JARVIS, disarm security'** or enter PIN 1170 to silence."
            )
        return "Simulated anti-theft alarm triggered, sir! Emergency siren active. Say 'JARVIS, disarm security' to stand down."

    return "Supported actions: arm | disarm | status | incidents | test_trigger"


TOOL = {
    "name": "anti_theft",
    "description": (
        "Anti-Theft Siren Guard and Intrusion Defense Tool for JARVIS H3.1. "
        "Arms device protection against unauthorized physical lifting, charger disconnection, and movement. "
        "Sounds emergency siren upon intrusion and requires verified owner voice or PIN to disarm."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "arm | disarm | status | incidents | test_trigger (default: status)"
            },
            "pin": {
                "type": "STRING",
                "description": "Disarm PIN code (default: '1170')"
            },
            "delay": {
                "type": "INTEGER",
                "description": "Arming countdown delay in seconds (default: 10)"
            }
        }
    },
    "handler": anti_theft_action,
}

run = anti_theft_action
