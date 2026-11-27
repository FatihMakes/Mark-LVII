"""
actions/quick_notes.py — Quick Voice Notes & Idea Capture for JARVIS
Contributed by Aman Kumar (@iamTechieAman).

Supports capturing thoughts, to-dos, meeting notes, and voice memos to:
  - ~/Desktop/JARVIS_Notes.md
  - memory/quick_notes.json
Integrates with FileTrackerEngine and thread-safe player signals.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quick_notes")

DESKTOP_DIR = Path.home() / "Desktop"
NOTES_MD_FILE = DESKTOP_DIR / "JARVIS_Notes.md"
MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
NOTES_JSON_FILE = MEMORY_DIR / "quick_notes.json"


def _sync_to_apple_notes(title: str, text: str) -> bool:
    """Sync note to macOS Apple Notes application (OpenJarvis connector pattern)."""
    if sys.platform != "darwin":
        return False
    try:
        clean_title = title.replace("\\", "\\\\").replace('"', '\\"')
        clean_body = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "<br>")
        html_body = f"<div><b>{clean_title}</b></div><div><br></div><div>{clean_body}</div>"
        script = f'''
        tell application "Notes"
            tell default account
                make new note at folder "Notes" with properties {{name: "{clean_title}", body: "{html_body}"}}
            end tell
        end tell
        '''
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
        return res.returncode == 0
    except Exception as e:
        logger.debug(f"Apple Notes sync notice: {e}")
        return False


def _load_notes() -> List[Dict[str, Any]]:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if NOTES_JSON_FILE.is_file():
        try:
            data = json.loads(NOTES_JSON_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception as e:
            logger.warning(f"Failed to read quick notes JSON: {e}")
    return []


def _save_notes(notes: List[Dict[str, Any]]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        NOTES_JSON_FILE.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write quick notes JSON: {e}")

    # Also sync to Desktop Markdown file
    try:
        md_lines = ["# 📝 JARVIS Quick Notes\n", f"*Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n---\n"]
        for n in reversed(notes):
            ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(n.get("timestamp", time.time())))
            tag = f" `[{n.get('tag', 'General')}]`" if n.get("tag") else ""
            md_lines.append(f"### {ts_str}{tag}\n{n.get('text', '')}\n")
        NOTES_MD_FILE.write_text("\n".join(md_lines), encoding="utf-8")
        # Register in file tracker
        try:
            from core.file_tracker import get_file_tracker
            get_file_tracker().register_file(
                str(NOTES_MD_FILE),
                action="created",
                description=f"JARVIS Quick Notes file with {len(notes)} entries"
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to write Desktop notes MD: {e}")


def quick_notes(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = (params.get("action") or "add").lower().strip()
    text = (params.get("text") or params.get("note") or params.get("content") or "").strip()
    tag = (params.get("tag") or params.get("category") or "Note").title()

    notes = _load_notes()

    if action in ("add", "create", "write", "save", "take_note", "note"):
        if not text:
            return "What would you like me to note down, sir?"

        entry = {
            "id": f"note_{int(time.time() * 1000)}",
            "timestamp": time.time(),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tag": tag,
            "text": text,
        }
        notes.append(entry)
        _save_notes(notes)
        _sync_to_apple_notes(f"JARVIS: {tag}", text)

        if player and hasattr(player, "write_log"):
            player.write_log(f"Notes: Captured note [{tag}]: {text[:40]}...")

        if player and hasattr(player, "show_content"):
            content_preview = f"**Saved to `{NOTES_MD_FILE.name}`:**\n\n> {text}\n\n*Total notes:* {len(notes)}"
            player.show_content("Quick Note Saved", content_preview)

        return f"I have noted that down on your Desktop, sir: '{text}'."

    elif action in ("list", "read", "show", "view", "get"):
        if not notes:
            return "You don't have any notes saved yet, sir."

        recent = notes[-5:]
        summary_lines = [f"# 📝 Recent Notes ({len(notes)} total)"]
        for idx, n in enumerate(reversed(recent), 1):
            dt = n.get("datetime", "")
            summary_lines.append(f"**{idx}. [{n.get('tag')}]** *{dt}*\n> {n.get('text')}\n")

        if player and hasattr(player, "show_content"):
            player.show_content("Quick Notes", "\n".join(summary_lines))

        return f"You have {len(notes)} notes saved. Latest note: '{notes[-1].get('text')}'."

    elif action in ("clear", "delete_all", "reset"):
        count = len(notes)
        _save_notes([])
        return f"Cleared all {count} quick notes, sir."

    return "Supported actions: add | list | clear"


TOOL = {
    "name": "quick_notes",
    "description": "Captures thoughts, reminders, to-dos and quick voice notes to Desktop and memory.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "add | list | clear"
            },
            "text": {
                "type": "STRING",
                "description": "Content of the note to capture"
            },
            "tag": {
                "type": "STRING",
                "description": "Category or tag (e.g. Work, Idea, ToDo, Personal)"
            }
        },
        "required": [
            "text"
        ]
    },
    "handler": quick_notes,
}

run = quick_notes
