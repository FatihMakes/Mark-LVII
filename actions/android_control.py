"""
actions/android_control.py — Android Companion & Device Hardware Control Tool for JARVIS H3.1
Contributed by Aman Kumar (@iamTechieAman).

Supports voice commands:
  - "JARVIS, turn on flashlight on my phone" / "Turn off phone torch"
  - "JARVIS, check phone battery" / "Is my phone charging?"
  - "JARVIS, set phone volume to 75%" / "Mute phone media"
  - "JARVIS, pair new Android phone" / "Companion devices status"
  - "JARVIS, launch WhatsApp on my phone"
  - "JARVIS, open phone Wi-Fi settings"
"""
from __future__ import annotations

import json
from pathlib import Path

from core import companion_gateway

ROOT_DIR = Path(__file__).resolve().parent.parent


def android_control(parameters: dict, player=None, session_memory=None) -> str:
    """
    Executes Android hardware control, device telemetry query, and pairing operations.
    """
    gw = companion_gateway.get_companion_gateway()
    action = (parameters.get("action") or "status").lower().strip()
    target = parameters.get("target") or parameters.get("setting") or parameters.get("app_name")
    level = parameters.get("level")

    # 1. Device Pairing & Enrolment
    if action in ("pair", "pair_device", "connect_phone", "qr_code"):
        token, qr_data = gw.generate_pairing_token(ttl_seconds=300)
        report = [
            "# 📱 JARVIS H3.1 Android Companion Pairing",
            f"**One-Time Pairing Token:** `{token}`",
            "**Validity:** `5 minutes (Time-Bounded Nonce)`",
            "",
            "### 📲 Pairing Instructions:",
            "1. Open the **JARVIS Companion App** on your Android device.",
            "2. Select **Scan Desktop QR Code** or enter the token above.",
            "3. The connection uses encrypted local WebSocket communication.",
            "",
            f"```json\n{qr_data}\n```"
        ]
        if player and hasattr(player, "show_content"):
            player.show_content("Android Companion Pairing", "\n".join(report))
        return f"One-time pairing token generated: {token}. Scan the QR code or enter the token in your Android companion app to pair securely."

    # 2. Companion Status & Paired Devices
    elif action in ("status", "devices", "list"):
        devices = gw.list_devices()
        primary = gw.get_primary_device()

        lines = [
            "# 📱 Paired Android Companion Status",
            f"**Paired Devices:** {len(devices)} active",
            ""
        ]
        if primary:
            lines.extend([
                f"### Primary Companion: **{primary.device_name}** ({primary.model})",
                f"- **Battery:** `{primary.battery_percent}% {'(Charging ⚡)' if primary.is_charging else '(Discharging)'}`",
                f"- **Flashlight:** `{'ON' if primary.flashlight_on else 'OFF'}`",
                f"- **Media Volume:** `{primary.volume_level}% {'(Muted)' if primary.media_muted else ''}`",
                f"- **Display Brightness:** `{primary.brightness_level}%`",
                f"- **Wi-Fi:** `Connected to {primary.wifi_ssid}`",
                f"- **Anti-Theft Guard:** `{'ARMED 🛡️' if primary.anti_theft_armed else 'Disarmed'}`",
                f"- **Last Synchronized:** `{primary.paired_at}`"
            ])
        else:
            lines.append("No physical Android devices currently paired. Operating in synchronized standby mode.")

        if player and hasattr(player, "show_content"):
            player.show_content("Companion Telemetry", "\n".join(lines))

        if primary:
            charge_phrase = "charging" if primary.is_charging else "discharging"
            return f"Connected to {primary.device_name}, sir. Battery is at {primary.battery_percent}% ({charge_phrase}), flashlight is {'on' if primary.flashlight_on else 'off'}."
        return "Companion gateway is active and ready for Android device pairing."

    # 3. Flashlight Control
    elif action in ("flashlight_on", "torch_on"):
        ok, msg, _ = gw.execute_hardware_command("flashlight_on")
        return msg

    elif action in ("flashlight_off", "torch_off"):
        ok, msg, _ = gw.execute_hardware_command("flashlight_off")
        return msg

    # 4. Battery Status
    elif action in ("battery", "battery_status", "power"):
        ok, msg, _ = gw.execute_hardware_command("get_battery")
        return msg

    # 5. Volume & Media
    elif action in ("volume", "set_volume"):
        val = int(level) if level is not None else 75
        ok, msg, _ = gw.execute_hardware_command("set_volume", {"level": val})
        return msg

    elif action in ("mute", "mute_media"):
        ok, msg, _ = gw.execute_hardware_command("mute_media")
        return msg

    elif action in ("unmute", "unmute_media"):
        ok, msg, _ = gw.execute_hardware_command("unmute_media")
        return msg

    # 6. Brightness
    elif action in ("brightness", "set_brightness"):
        val = int(level) if level is not None else 65
        ok, msg, _ = gw.execute_hardware_command("set_brightness", {"level": val})
        return msg

    # 7. Launch App on Phone
    elif action in ("launch_app", "open_app"):
        app_str = target or "application"
        ok, msg, _ = gw.execute_hardware_command("launch_app", {"app_name": app_str})
        return msg

    # 8. Open Android System Settings Intent
    elif action in ("setting", "open_setting", "wifi_settings", "bluetooth_settings"):
        setting_type = target or "wifi"
        ok, msg, _ = gw.execute_hardware_command("settings_intent", {"setting": setting_type})
        return msg

    # 9. Revoke Device
    elif action in ("revoke", "revoke_device", "unpair"):
        if not target:
            return "Please specify the device name or ID to revoke."
        if gw.revoke_device(target):
            return f"Successfully revoked access for companion device '{target}', sir."
        return f"Device '{target}' was not found in active paired registry."

    return "Supported actions: pair | status | flashlight_on | flashlight_off | battery | volume | mute | unmute | brightness | launch_app | setting | revoke"


TOOL = {
    "name": "android_control",
    "description": (
        "Android Companion and Hardware Control Tool for JARVIS H3.1. "
        "Allows voice control of paired Android smartphone hardware: toggling flashlight, "
        "checking battery & charging state, adjusting volume/brightness, launching mobile apps, "
        "opening system settings intents (Wi-Fi, Bluetooth), and pairing new devices via QR tokens."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "pair | status | flashlight_on | flashlight_off | battery | volume | mute | unmute | brightness | launch_app | setting | revoke"
            },
            "target": {
                "type": "STRING",
                "description": "Application name, setting name ('wifi', 'bluetooth'), or device name to revoke"
            },
            "level": {
                "type": "INTEGER",
                "description": "Percentage level for volume or brightness (0 - 100)"
            }
        }
    },
    "handler": android_control,
}

run = android_control
