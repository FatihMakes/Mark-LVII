"""
actions/whatsapp_automation.py — WhatsApp Desktop Messaging, Calling & Automation for JARVIS H3.4
Contributed by Aman Kumar (@iamTechieAman).

Supports:
  - Real macOS WhatsApp Desktop native integration via official URL scheme & AppleScript
  - Intelligent Owner-Authorized Auto-Execution: Direct send without repetitive confirmations
  - Intent distinction: Explicit send vs explicit draft/prepare request
  - Contact matching and recipient ambiguity protection
  - Duplicate-send protection and idempotency
  - Multi-user permission gatekeeping (owner-only sending vs guest denial)
  - Transparent macOS accessibility guidance
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import companion_gateway, permissions
from core.owner_session import is_owner_authenticated, get_owner_session
from core.permissions import get_current_speaker, UserRole
from core.whatsapp_desktop_controller import (
    get_whatsapp_controller,
    WhatsAppExecutionState,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT_DIR / "memory"
PENDING_MESSAGES_FILE = MEMORY_DIR / "pending_whatsapp_messages.json"

_PENDING_DISPATCH: Dict[str, dict] = {}
_HANDS_FREE_ACTIVE = False
logger = logging.getLogger("whatsapp_automation")


def _load_contacts() -> Dict[str, dict]:
    return get_whatsapp_controller().load_contacts()


def _resolve_contact(query: str) -> Optional[dict]:
    return get_whatsapp_controller().resolve_contact(query)


def _is_owner_caller(session_memory: Optional[dict] = None) -> bool:
    """Verifies that the speaker authorized for this turn is the enrolled owner."""
    if session_memory and isinstance(session_memory, dict):
        spk = str(session_memory.get("speaker") or "").upper()
        if spk in ("GUEST", "TEMPORARY_GUEST", "UNKNOWN"):
            return False
        if session_memory.get("owner_authenticated") is True:
            return True

    curr_spk = get_current_speaker().upper()
    if curr_spk in (UserRole.TEMPORARY_GUEST.value, "TEMPORARY_GUEST", "GUEST", "UNKNOWN"):
        return False

    return is_owner_authenticated()


def whatsapp_automation(parameters: dict, player=None, session_memory=None) -> str:
    """
    Executes WhatsApp operations with intelligent owner-authorized auto-execution.
    """
    global _HANDS_FREE_ACTIVE

    controller = get_whatsapp_controller()
    params = parameters or {}
    action = (params.get("action") or "status").lower().strip()
    recipient = params.get("recipient") or params.get("contact") or params.get("query") or params.get("name") or ""
    message_text = params.get("message") or params.get("text") or ""
    confirm_code = params.get("confirm_id") or params.get("draft_id") or ""
    operation_id = params.get("operation_id") or params.get("idempotency_key") or ""

    contacts = _load_contacts()
    gw = companion_gateway.get_companion_gateway()

    # 1. Status / Diagnostics / Config
    if action in ("status", "telemetry", "info", "config"):
        tel = controller.get_telemetry()
        conf = controller.get_config()
        status_md = [
            "# 📱 WhatsApp Integration Status (H3.4)",
            f"- **Desktop App Installed:** `{'Yes' if tel['installed'] else 'No'}` ({tel['app_path'] or 'Not found'})",
            f"- **Process Running:** `{'Yes' if tel['running'] else 'No'}`",
            f"- **macOS Accessibility Granted:** `{'Yes' if tel['accessibility_granted'] else 'Needs Permission'}`",
            f"- **Owner Auto-Send Enabled:** `{'Yes' if conf.get('owner_auto_send_enabled') else 'No (Confirmation Required)'}`",
            f"- **Contacts Loaded:** `{tel['contacts_count']}` contacts",
            f"- **Driving Mode:** `{'Enabled' if _HANDS_FREE_ACTIVE else 'Disabled'}`"
        ]
        if player and hasattr(player, "show_content"):
            player.show_content("WhatsApp Status", "\n".join(status_md))
        inst_str = "installed and operational" if tel["installed"] else "not installed"
        auto_str = "auto-send active for owner" if conf.get("owner_auto_send_enabled") else "confirmations enabled"
        return f"WhatsApp Desktop is {inst_str} on macOS ({auto_str}), with {tel['contacts_count']} contacts available."

    # Toggle / Set Configuration
    elif action in ("set_config", "configure_auto_send"):
        updates = {}
        if "auto_send" in params:
            updates["owner_auto_send_enabled"] = bool(params["auto_send"])
        if "trusted_contacts_auto_send" in params:
            updates["trusted_contacts_auto_send"] = bool(params["trusted_contacts_auto_send"])
        updated = controller.update_config(updates)
        return f"WhatsApp configuration updated: owner_auto_send_enabled={updated.get('owner_auto_send_enabled')}."

    # 2. Contact Search & Lookup
    elif action in ("search_contact", "find_contact", "lookup_contact", "contacts"):
        if not recipient:
            clist = [f"- **{c.get('name', k)}** ({c.get('relationship', 'Contact')}): `{c.get('phone', '')}`" for k, c in contacts.items()]
            md = "# 📇 Saved WhatsApp Contacts\n" + "\n".join(clist)
            if player and hasattr(player, "show_content"):
                player.show_content("WhatsApp Contacts", md)
            return f"You have {len(contacts)} saved WhatsApp contacts, sir."

        matches = controller.resolve_contacts(recipient)
        if len(matches) == 1:
            found = matches[0]
            return f"Found contact: {found.get('name')} ({found.get('relationship', 'Contact')}), phone number {found.get('phone')}."
        elif len(matches) > 1:
            names = [f"{m.get('name')} ({m.get('phone')})" for m in matches]
            return f"Found {len(matches)} contacts matching '{recipient}': {', '.join(names)}."
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

    # 4. Compose / Send Decision Logic
    elif action in ("compose", "compose_message", "prepare_message", "draft", "draft_message", "send", "send_message", "confirm_send", "dispatch_message"):
        # Security Gatekeeper: Ensure caller is the owner
        is_owner = _is_owner_caller(session_memory)
        if not is_owner:
            logger.warning(f"[SECURITY] WhatsApp send blocked for unauthenticated/guest caller.")
            return "Access denied. Sending WhatsApp messages requires owner authorization."

        # Check intent: Explicit Draft vs Direct Send
        explicit_draft_request = (
            action in ("compose", "compose_message", "prepare_message", "draft", "draft_message")
            or bool(params.get("draft") or params.get("draft_only"))
            or str(params.get("mode") or "").lower() == "draft"
            or "do not send" in message_text.lower()
            or "draft only" in message_text.lower()
            or "draft" in str(params.get("instruction") or "").lower()
        )

        # Confirm Send of an existing draft
        if action in ("confirm_send", "dispatch_message") or confirm_code:
            did = confirm_code or (list(_PENDING_DISPATCH.keys())[-1] if _PENDING_DISPATCH else "")
            if not did or did not in _PENDING_DISPATCH:
                # If no draft pending but recipient and message given, proceed to direct send
                if not recipient or not message_text:
                    return "No pending WhatsApp message draft found to confirm. Please specify a recipient and message."
                target_recipient = recipient
                target_message = message_text
            else:
                draft = _PENDING_DISPATCH.pop(did)
                target_recipient = draft["recipient"]
                target_message = draft["message"]

            res = controller.send_message(target_recipient, target_message, auto_submit=True, operation_id=operation_id)
            if res.get("status") == WhatsAppExecutionState.SENT_VERIFIED:
                if player and hasattr(player, "write_log"):
                    player.write_log(f"WhatsApp: Message sent to {res.get('recipient')}.")
                return f"Message sent to {res.get('recipient')}, sir: '{target_message}'."
            elif res.get("status") == WhatsAppExecutionState.ACCESSIBILITY_PERMISSION_REQUIRED:
                return (
                    f"Message pre-filled in WhatsApp for {res.get('recipient')}. "
                    "Please grant macOS Accessibility permission in System Settings > Privacy & Security > Accessibility "
                    "for automatic dispatch. Press Return in WhatsApp to send."
                )
            else:
                return f"Message dispatched to WhatsApp for {target_recipient}."

        # Explicit Draft Request
        if explicit_draft_request:
            if not recipient:
                return "Who would you like to draft a message to? Please specify a contact name."
            if not message_text:
                return f"What message would you like to draft for {recipient}?"

            matches = controller.resolve_contacts(recipient)
            if len(matches) > 1:
                names = [f"{m.get('name')} ({m.get('phone')})" for m in matches]
                return f"I found multiple contacts matching '{recipient}': {', '.join(names)}. Which one should I draft the message for?"

            contact_info = matches[0] if matches else None
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
                "# 💬 WhatsApp Message Draft (Not Sent)",
                f"**Draft ID:** `{draft_id}`",
                f"**To:** {display_name} (`{phone}`)",
                f"**Message:** \"{message_text}\"",
                "",
                "> [!NOTE]",
                f"> Prepared as requested without sending. Say **\"Confirm send {draft_id}\"** whenever you are ready."
            ]
            if player and hasattr(player, "show_content"):
                player.show_content("WhatsApp Draft", "\n".join(review_card))

            return (
                f"I have prepared your message draft for {display_name}: '{message_text}'. "
                f"To send it, please say 'Confirm send {draft_id}'."
            )

        # Direct Send Requested
        if not recipient:
            return "Who would you like to send the message to? Please specify a contact name."
        if not message_text:
            return f"What message would you like to send to {recipient}?"

        # Resolve recipient
        matches = controller.resolve_contacts(recipient)
        if len(matches) > 1:
            names = [f"{m.get('name')} ({m.get('phone')})" for m in matches]
            return f"I found multiple contacts matching '{recipient}': {', '.join(names)}. Please clarify which contact to message."
        if not matches:
            return f"Contact '{recipient}' was not found in your saved directory. Please provide their full phone number."

        target_contact = matches[0]
        display_name = target_contact.get("name", recipient)

        # Auto-Send Policy Check
        if controller.is_auto_send_enabled():
            # Send Directly!
            res = controller.send_message(recipient, message_text, auto_submit=True, operation_id=operation_id)
            status = res.get("status")

            if status == WhatsAppExecutionState.SENT_VERIFIED:
                if player and hasattr(player, "write_log"):
                    player.write_log(f"WhatsApp: Auto-sent verified message to {display_name}.")
                return f"Message successfully sent to {display_name}: '{message_text}'"

            elif status == WhatsAppExecutionState.ACCESSIBILITY_PERMISSION_REQUIRED:
                if player and hasattr(player, "write_log"):
                    player.write_log(f"WhatsApp: Staged message for {display_name} (Accessibility required).")
                return (
                    f"I have pre-filled the message for {display_name} in WhatsApp Desktop. "
                    "To enable automatic sending without manual confirmation, please grant macOS Accessibility permission in "
                    "System Settings > Privacy & Security > Accessibility. In the meantime, press Return in WhatsApp to dispatch."
                )

            elif status == "DUPLICATE_SUPPRESSED":
                return f"Duplicate message suppressed: an identical message was recently sent to {display_name}."

            elif status == WhatsAppExecutionState.SENT_UNCONFIRMED:
                return f"Message staged in WhatsApp for {display_name}. Please check the chat window to confirm dispatch."

            else:
                return f"Unable to dispatch message to {display_name}: {res.get('error', 'unknown error')}."

        else:
            # Fallback to draft confirmation card if auto-send preference is explicitly disabled
            draft_id = f"WA_{int(time.time()) % 10000:04d}"
            _PENDING_DISPATCH[draft_id] = {
                "recipient": display_name,
                "phone": target_contact.get("phone", recipient),
                "message": message_text,
                "timestamp": time.time()
            }
            return f"I have prepared your message for {display_name}: '{message_text}'. To send it, please say 'Confirm send {draft_id}'."

    # 5. Stage Message Only (Without Enter)
    elif action in ("stage", "stage_message", "open_chat"):
        if not recipient:
            return "Please specify a contact or phone number to open in WhatsApp."
        res = controller.stage_message(recipient, message_text)
        if res.get("success"):
            return f"Opened WhatsApp chat for {res.get('recipient')}" + (f" with pre-filled message." if message_text else ".")
        return f"Could not open WhatsApp chat: {res.get('error', 'unknown error')}"

    # 6. WhatsApp Voice Call
    elif action in ("call", "make_call", "whatsapp_call"):
        if not recipient:
            return "Who would you like to call on WhatsApp?"

        contact_info = _resolve_contact(recipient)
        if not contact_info:
            return f"I could not verify contact details for '{recipient}'. Please confirm their name or phone number first."

        clean_phone = contact_info["phone"].replace("+", "").replace(" ", "").replace("-", "")
        call_url = f"whatsapp://call?phone={clean_phone}"

        try:
            import subprocess
            subprocess.run(["open", call_url], check=True)
        except Exception:
            gw.execute_hardware_command("launch_app", {"app_name": f"WhatsApp Call: {contact_info['name']}"})

        if player and hasattr(player, "write_log"):
            player.write_log(f"WhatsApp: Initiating call to {contact_info['name']} ({clean_phone}).")

        return f"Initiating WhatsApp call to {contact_info['name']}, sir."

    # 7. Hands-Free Driving Mode
    elif action in ("hands_free_mode", "driving_mode", "toggle_hands_free"):
        _HANDS_FREE_ACTIVE = not _HANDS_FREE_ACTIVE
        state_str = "ENABLED (Hands-Free Zero-Touch Driving Mode)" if _HANDS_FREE_ACTIVE else "DISABLED"
        if player and hasattr(player, "write_log"):
            player.write_log(f"SYS: Hands-Free Driving Mode {state_str}.")
        return (
            f"Hands-free driving mode is now {state_str}, sir. "
            f"Incoming messages will be announced aloud, and direct auto-send is active."
        )

    return "Supported actions: status | search_contact | read_unread | send | compose | confirm_send | stage | call | hands_free_mode"


TOOL = {
    "name": "whatsapp_automation",
    "description": (
        "WhatsApp Desktop Automation for JARVIS H3.4 with Owner Auto-Send. "
        "Directly sends messages to unambiguous contacts when instructed by the authenticated owner without repetitive confirmations. "
        "Supports drafting, reading unread messages, recipient disambiguation, duplicate prevention, and hands-free calls."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "send | compose | search_contact | read_unread | confirm_send | stage | call | status | hands_free_mode"
            },
            "recipient": {
                "type": "STRING",
                "description": "Contact name (e.g. 'Rahul', 'Maya') or direct phone number"
            },
            "message": {
                "type": "STRING",
                "description": "Exact text message content to send or draft"
            },
            "draft": {
                "type": "BOOLEAN",
                "description": "Set to true if user explicitly requested a draft without sending"
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
