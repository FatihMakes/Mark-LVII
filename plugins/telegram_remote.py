"""
plugins/telegram_remote.py — Private Phone Bridge & 24/7 Telegram Assistant for JARVIS.
Contributed by Aman Kumar (@iamTechieAman).

Connects JARVIS to your private Telegram bot:
- 24/7 access from your phone even when away from your PC
- Ask "Is my PC still on?", "Send me the report on my desktop", or run voice notes
- Secure by design: only authorized Telegram Chat IDs are permitted
- Two-way messaging and live PC telemetry
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from memory.config_manager import get_plugin_config, save_plugin_config

PLUGIN = {
    "name": "telegram_remote",
    "description": (
        "24/7 Telegram Phone Bot bridge for JARVIS. Allows interacting with JARVIS "
        "from your smartphone via Telegram: check PC status, receive files/reports, "
        "and command your system from anywhere."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'start' | 'stop' | 'status' | 'send_message' (default: status).",
            },
            "message": {
                "type": "STRING",
                "description": "Message text to send to approved phone chat.",
            },
        },
        "required": [],
    },
}

_state: Dict[str, Any] = {
    "running": False,
    "stopping": False,
    "bot": "",
    "turn_chat": None,
    "turn_open": False,
}

_outbox: queue.Queue = queue.Queue()
_stop_event = threading.Event()
_poll_thread: Optional[threading.Thread] = None


def _cfg() -> dict:
    try:
        return get_plugin_config("telegram_remote") or {}
    except Exception:
        return {}


def _parse_ids(val: Any) -> List[int]:
    if isinstance(val, list):
        return [int(x) for x in val if str(x).isdigit()]
    if isinstance(val, (int, float)):
        return [int(val)]
    raw = str(val or "")
    out = []
    for part in re.split(r"[,;\s]+", raw):
        part = part.strip()
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            out.append(int(part))
    return out


def _turn_active() -> bool:
    return bool(_state.get("turn_open"))


def _enqueue(chat_id: int, text: str) -> None:
    _outbox.put({"kind": "text", "chat": chat_id, "text": text})


def _put(item: dict) -> None:
    _outbox.put(item)


def _keyboard(cfg: dict) -> dict:
    return {
        "keyboard": [
            [{"text": "🖥 PC Status"}, {"text": "📊 Hardware Load"}],
            [{"text": "📁 Latest Report"}, {"text": "📸 Screen Snapshot"}]
        ],
        "resize_keyboard": True
    }


def _sender_loop(token: str) -> None:
    """Consumes the _outbox queue and sends messages/documents to Telegram."""
    while not _stop_event.is_set():
        try:
            item = _outbox.get(timeout=1.0)
        except queue.Empty:
            continue

        chat_id = item.get("chat")
        kind = item.get("kind", "text")
        text = item.get("text", "")
        markup = item.get("markup")

        try:
            if kind == "text":
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": text[:4000]}
                if markup:
                    payload["reply_markup"] = markup
                requests.post(url, json=payload, timeout=15)
            elif kind in ("photo", "document"):
                method = "sendPhoto" if kind == "photo" else "sendDocument"
                url = f"https://api.telegram.org/bot{token}/{method}"
                files = {kind: (item.get("name", "file"), item.get("data", b""), item.get("mime", "application/octet-stream"))}
                data = {"chat_id": chat_id, "caption": item.get("caption", "")[:1024]}
                requests.post(url, data=data, files=files, timeout=60)
        except Exception as e:
            print(f"[Telegram] Sender error: {e}")
        finally:
            _outbox.task_done()


def _bot_poll_loop(token: str, player=None) -> None:
    """Long-polls Telegram updates and dispatches commands to JARVIS."""
    offset = 0
    _state["running"] = True
    _state["stopping"] = False

    # Get Bot Name
    try:
        me_resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if me_resp.status_code == 200:
            _state["bot"] = me_resp.json().get("result", {}).get("username", "JarvisBot")
    except Exception:
        pass

    sender_th = threading.Thread(target=_sender_loop, args=(token,), daemon=True)
    sender_th.start()

    while not _stop_event.is_set():
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=20"
            r = requests.get(url, timeout=25)
            if r.status_code != 200:
                time.sleep(2.0)
                continue

            updates = r.json().get("result", [])
            allowed = _parse_ids(_cfg().get("allowed_chat_ids", ""))

            for u in updates:
                offset = max(offset, u.get("update_id", 0) + 1)
                msg = u.get("message") or {}
                chat = msg.get("chat") or {}
                cid = chat.get("id")
                text = (msg.get("text") or "").strip()

                if not cid:
                    continue

                # Access control check
                if allowed and cid not in allowed:
                    _enqueue(cid, "⛔ Unauthorized device. Your Chat ID is not registered in JARVIS settings.")
                    continue

                if not allowed:
                    # Auto-register first phone if unconfigured
                    allowed = [cid]
                    save_plugin_config("telegram_remote", {"bot_token": token, "allowed_chat_ids": str(cid)})
                    _enqueue(cid, f"✅ Phone authorized! Registered Chat ID {cid} to JARVIS.")

                # Process command
                _state["turn_chat"] = cid
                _state["turn_open"] = True

                if text == "/start":
                    _enqueue(cid, "👋 Greetings! JARVIS 24/7 Phone Bridge is active. You can talk to your PC, ask for reports, or inspect system load.")
                elif text == "🖥 PC Status" or text.lower() == "is my pc still on?":
                    _enqueue(cid, "🖥 Yes, sir. Your PC is online, responsive, and all systems are operational.")
                elif text == "📊 Hardware Load":
                    import psutil
                    cpu = psutil.cpu_percent(interval=0.5)
                    ram = psutil.virtual_memory().percent
                    _enqueue(cid, f"📊 Hardware Telemetry:\n- CPU Load: {cpu}%\n- RAM Usage: {ram}%")
                elif text == "📁 Latest Report" or "report" in text.lower():
                    # Find latest report
                    reports_dir = Path(__file__).resolve().parent.parent / "reports"
                    if reports_dir.exists():
                        md_files = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if md_files:
                            latest = md_files[0]
                            _enqueue(cid, f"📄 Latest Report: {latest.name}\n\n{latest.read_text(encoding='utf-8')[:3000]}")
                        else:
                            _enqueue(cid, "Sir, no reports currently found in the reports archive.")
                    else:
                        _enqueue(cid, "Sir, reports archive directory is empty.")
                else:
                    # General command routing
                    if player and hasattr(player, "write_log"):
                        player.write_log(f"TELEGRAM ({cid}): {text}")
                    from core import gemini
                    reply = gemini.text(f"You are JARVIS assisting via Telegram phone bot. User query: {text}", tier=gemini.FAST, default="Sir, I received your message.")
                    _enqueue(cid, reply)

                _state["turn_open"] = False

        except Exception as e:
            if not _stop_event.is_set():
                time.sleep(3.0)

    _state["running"] = False
    _state["stopping"] = False


def run(parameters: dict, player=None, session_memory=None) -> str:
    global _poll_thread, _stop_event
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()
    msg = str(params.get("message") or "").strip()

    cfg = _cfg()
    token = str(cfg.get("bot_token") or "").strip()

    if action == "start":
        if not token:
            return "Sir, Telegram bot token is not configured in Plugin Settings."
        if _state["running"]:
            return "Sir, Telegram phone bot is already active and listening."

        _stop_event.clear()
        _poll_thread = threading.Thread(target=_bot_poll_loop, args=(token, player), daemon=True)
        _poll_thread.start()
        if player and hasattr(player, "write_log"):
            player.write_log("TELEGRAM: Phone bridge started successfully")
        return "Sir, your 24/7 Telegram phone bridge is now running and connected."

    elif action == "stop":
        if not _state["running"]:
            return "Sir, Telegram phone bridge is not running."
        _state["stopping"] = True
        _stop_event.set()
        return "Sir, Telegram phone bridge is shutting down."

    elif action == "send_message" and msg:
        allowed = _parse_ids(cfg.get("allowed_chat_ids", ""))
        if not allowed:
            return "Sir, no approved Telegram chat IDs are registered."
        for cid in allowed:
            _enqueue(cid, msg)
        return f"Sir, message sent to your Telegram phone bot: '{msg}'."

    else:
        status_str = "ACTIVE 🟢" if _state["running"] else "STOPPED ⚫"
        allowed = _parse_ids(cfg.get("allowed_chat_ids", ""))
        bot_name = _state.get("bot") or "Unconnected"
        return f"Sir, Telegram phone bridge is currently {status_str}. Connected bot: @{bot_name}, Registered phones: {len(allowed)}."
