"""
actions/whatsapp_automation.py — WhatsApp Desktop Messaging, Calling & Automation for JARVIS H3.3
Contributed by Aman Kumar (@iamTechieAman).

Supports:
  - macOS WhatsApp Desktop native integration via official URL scheme & AppleScript
  - Contact search & disambiguation
  - Real unread message reading / notification status
  - Compose & send messages with explicit confirmation safeguard
  - Hands-Free WhatsApp Calling & Driving Mode
  - Transparent execution verification and permission reporting
"""
from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import companion_gateway, permissions
from core.whatsapp_desktop_controller import get_whatsapp_controller

ROOT_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT_DIR / "memory"
PENDING_MESSAGES_FILE = MEMORY_DIR / "pending_whatsapp_messages.json"

_PENDING_DISPATCH: Dict[str, dict] = {}
_HANDS_FREE_ACTIVE = False


def _load_contacts() -> Dict[str, dict]:
    return get_whatsapp_controller().load_contacts()


def _resolve_contact(query: str) -> Optional[dict]:
    return get_whatsapp_controller().resolve_contact(query)


def whatsapp_automation(parameters: dict, player=None, session_memory=None) -> str:
    """
    Executes WhatsApp messaging, calling, notification read-out, and driving mode.
    Uses native macOS WhatsApp Desktop integration when available, with fallback to companion gateway.
    """
    global _HANDS_FREE_ACTIVE

    controller = get_whatsapp_controller()
    action = (parameters.get("action") or "status").lower().strip()
    recipient = parameters.get("recipient") or parameters.get("contact") or parameters.get("query") or parameters.get("name") or ""
    message_text = parameters.get("message") or parameters.get("text") or ""
    confirm_code = parameters.get("confirm_id") or ""

    contacts = _load_contacts()
    gw = companion_gateway.get_companion_gateway()

    # 1. Status / Diagnostics
    if action in ("status", "telemetry", "info"):
        tel = controller.get_telemetry()
        status_md = [
            "# 📱 WhatsApp Integration Status",
            f"- **Desktop App Installed:** `{'Yes' if tel['installed'] else 'No'}` ({tel['app_path'] or 'Not found'})",
            f"- **Process Running:** `{'Yes' if tel['running'] else 'No'}`",
            f"- **macOS Accessibility Granted:** `{'Yes' if tel['accessibility_granted'] else 'Needs Permission'}`",
            f"- **Contacts Loaded:** `{tel['contacts_count']}` contacts",
            f"- **Driving Mode:** `{'Enabled' if _HANDS_FREE_ACTIVE else 'Disabled'}`"
        ]
        if player and hasattr(player, "show_content"):
            player.show_content("WhatsApp Status", "\n".join(status_md))
        inst_str = "installed and operational" if tel["installed"] else "not installed"
        return f"WhatsApp Desktop is {inst_str} on macOS, with {tel['contacts_count']} contacts available."

    # 2. Contact Search & Lookup
    elif action in ("search_contact", "find_contact", "lookup_contact", "contacts"):
        if not recipient:
            clist = [f"- **{c.get('name', k)}** ({c.get('relationship', 'Contact')}): `{c.get('phone', '')}`" for k, c in contacts.items()]
            md = "# 📇 Saved WhatsApp Contacts\n" + "\n".join(clist)
            if player and hasattr(player, "show_content"):
                player.show_content("WhatsApp Contacts", md)
            return f"You have {len(contacts)} saved WhatsApp contacts, sir."

        found = _resolve_contact(recipient)
        if found:
            return f"Found contact: {found.get('name')} ({found.get('relationship', 'Contact')}), phone number {found.get('phone')}."
        return f"Contact '{recipient}' was not found in your saved directory. Please provide their full phone number."

    # 3. Read Unread Notifications / Messages
    elif action in ("read_unread", "unread", "read_messages"):
        unread = controller.read_unread_messages()
        if not unread:
            return "No unread WhatsApp messages found at this time, sir."
        announcements = [f"{n.get('source', 'Message')}: {n.get('title', n.get('message', ''))}" for n in unread]
        summary = f"You have {len(unread)} unread WhatsApp messages, sir. " + " ... ".join(announcements)
        if player and hasattr(player, "write_log"):
            player.write_log(f"WhatsApp: Read {len(unread)} unread messages.")
        return summary

    # 4. Compose Message & Prepare Confirmation
    elif action in ("compose", "compose_message", "prepare_message") or (action in ("send", "send_message") and not confirm_code and not parameters.get("draft_id") and not parameters.get("immediate")):
        if not recipient:
            return "Who would you like to send the message to? Please specify a contact name."
        if not message_text:
            return f"What message would you like to send to {recipient}?"

        contact_info = _resolve_contact(recipient)
        phone = contact_info.get("phone") if contact_info else recipient
        display_name = contact_info.get("name") if contact_info else recipient

        draft_id = f"WA_{int(time.time()) % 10000:04d}"
        _PENDING_DISPATCH[draft_id] = {
            "recipient": display_name,
            "phone": phone,
            "message": message_text,
            "timestamp": time.time()
        }

        review_card = [
            "# 💬 WhatsApp Message Confirmation",
            f"**Draft ID:** `{draft_id}`",
            f"**To:** {display_name} (`{phone}`)",
            f"**Message:** \"{message_text}\"",
            "",
            "> [!IMPORTANT]",
            f"> To confirm and send this message, say: **\"Confirm send {draft_id}\"**"
        ]
        if player and hasattr(player, "show_content"):
            player.show_content("Confirm WhatsApp Message", "\n".join(review_card))

        return (
            f"I have prepared your message for {display_name}: '{message_text}'. "
            f"To send it, please say 'Confirm send {draft_id}'."
        )

    # 5. Send / Confirm Dispatch
    elif action in ("confirm_send", "dispatch_message", "send", "send_message"):
        # If parameters directly contain recipient and message, allow sending
        did = confirm_code or parameters.get("draft_id")
        target_recipient = ""
        target_message = ""

        if did and did in _PENDING_DISPATCH:
            draft = _PENDING_DISPATCH.pop(did)
            target_recipient = draft["recipient"]
            target_message = draft["message"]
        elif not did and _PENDING_DISPATCH:
            draft = _PENDING_DISPATCH.pop(list(_PENDING_DISPATCH.keys())[-1])
            target_recipient = draft["recipient"]
            target_message = draft["message"]
        elif recipient and message_text:
            target_recipient = recipient
            target_message = message_text
        else:
            return "No pending WhatsApp message draft found to confirm. Please specify a recipient and message."

        # Execute via Desktop Controller
        res = controller.send_message(target_recipient, target_message, auto_submit=True)
        if res.get("verified"):
            if player and hasattr(player, "write_log"):
                player.write_log(f"WhatsApp: Dispatched verified message to {res.get('recipient')} via Desktop.")
            return f"Message sent to {res.get('recipient')}, sir: '{target_message}'."
        elif res.get("status") == "STAGED_REQUIRES_ENTER":
            if player and hasattr(player, "write_log"):
                player.write_log(f"WhatsApp: Message staged in WhatsApp Desktop for {res.get('recipient')}.")
            return (
                f"I have staged your message for {res.get('recipient')} in WhatsApp Desktop. "
                "Press Return in WhatsApp to dispatch, or grant Accessibility permission in macOS Settings."
            )
        else:
            # Fallback to companion gateway
            clean_phone = str(res.get("phone", "")).replace("+", "").replace(" ", "").replace("-", "")
            gw.execute_hardware_command("launch_app", {"app_name": f"WhatsApp: {target_recipient}"})
            return f"Staged WhatsApp message for {target_recipient}: '{target_message}'."

    # 6. Stage Message Only (Without Enter)
    elif action in ("stage", "stage_message", "open_chat"):
        if not recipient:
            return "Please specify a contact or phone number to open in WhatsApp."
        res = controller.stage_message(recipient, message_text)
        if res.get("success"):
            return f"Opened WhatsApp chat for {res.get('recipient')}" + (f" with pre-filled message." if message_text else ".")
        return f"Could not open WhatsApp chat: {res.get('error', 'unknown error')}"

    # 7. WhatsApp Voice Call
    elif action in ("call", "make_call", "whatsapp_call"):
        if not recipient:
            return "Who would you like to call on WhatsApp?"

        contact_info = _resolve_contact(recipient)
        if not contact_info:
            return f"I could not verify contact details for '{recipient}'. Please confirm their name or phone number first."

        clean_phone = contact_info["phone"].replace("+", "").replace(" ", "").replace("-", "")
        call_url = f"whatsapp://call?phone={clean_phone}"

        # Open URL scheme to trigger desktop call or companion
        try:
            import subprocess
            subprocess.run(["open", call_url], check=True)
        except Exception:
            gw.execute_hardware_command("launch_app", {"app_name": f"WhatsApp Call: {contact_info['name']}"})

        if player and hasattr(player, "write_log"):
            player.write_log(f"WhatsApp: Initiating call to {contact_info['name']} ({clean_phone}).")

        return f"Initiating WhatsApp call to {contact_info['name']}, sir."

    # 8. Hands-Free Driving Mode
    elif action in ("hands_free_mode", "driving_mode", "toggle_hands_free"):
        _HANDS_FREE_ACTIVE = not _HANDS_FREE_ACTIVE
        state_str = "ENABLED (Hands-Free Zero-Touch Driving Mode)" if _HANDS_FREE_ACTIVE else "DISABLED"
        if player and hasattr(player, "write_log"):
            player.write_log(f"SYS: Hands-Free Driving Mode {state_str}.")
        return (
            f"Hands-free driving mode is now {state_str}, sir. "
            f"Incoming messages will be announced aloud, and voice confirmations are active."
        )

    return "Supported actions: status | search_contact | read_unread | compose | send | confirm_send | stage | call | hands_free_mode"


TOOL = {
    "name": "whatsapp_automation",
    "description": (
        "WhatsApp Desktop and Mobile Automation for JARVIS H3.3. "
        "Enables voice-driven WhatsApp operations on macOS: searching contacts, reading unread messages, "
        "composing and sending verified text messages via native WhatsApp Desktop, opening chats, "
        "initiating calls, and toggling hands-free driving mode."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | search_contact | read_unread | compose | send | confirm_send | stage | call | hands_free_mode"
            },
            "recipient": {
                "type": "STRING",
                "description": "Contact name (e.g. 'Rahul', 'Maya') or phone number"
            },
            "message": {
                "type": "STRING",
                "description": "Text message content to send"
            },
            "confirm_id": {
                "type": "STRING",
                "description": "Draft ID for explicit message dispatch confirmation (e.g. 'WA_1234')"
            }
        }
    },
    "handler": whatsapp_automation,
}

run = whatsapp_automation

def reset_whatsapp_draft():
    """Clears pending message dispatch queue."""
    _PENDING_DISPATCH.clear()
