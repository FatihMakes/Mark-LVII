"""
actions/instagram_control.py — Instagram Reels Control Tool for JARVIS H3.3
Contributed by Aman Kumar (@iamTechieAman).

Controls Instagram Reels browser playback:
  - Open and play Reels by URL or Explore Feed
  - Pause, Resume, Next, Previous Reel
  - Mute/Unmute audio
  - Extract Reel caption, creator, and playback metrics
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.instagram_controller import get_instagram_controller

logger = logging.getLogger("instagram_action")


def instagram_control(parameters: dict, player=None, session_memory=None) -> str:
    """
    Handles Instagram Reels playback and navigation.
    """
    action = (parameters.get("action") or "play").lower().strip()
    url = parameters.get("url") or parameters.get("reel_url") or parameters.get("id") or ""

    controller = get_instagram_controller(headless=False)

    if action in ("play", "open", "watch"):
        if not url:
            # Default to reels explore feed
            url = "https://www.instagram.com/reels/"
        res = controller.open_reel(url)
        if not res.get("success"):
            return f"Unable to load Instagram Reel: {res.get('error', 'unknown error')}"

        tel = res.get("telemetry", {})
        status = "Playing" if tel.get("is_playing") else "Loaded"
        author = tel.get("author") or "Instagram Creator"
        caption = tel.get("caption") or ""

        md = [
            f"# 🎬 Instagram Reel: {status}",
            f"- **URL:** `{tel.get('url', url)}`",
            f"- **Creator:** {author}",
            f"- **Playback Status:** `{'Active Progression' if tel.get('verified_playback') else 'Ready'}`",
            f"- **Current Time:** `{tel.get('current_time', 0):.1f}s` / `{tel.get('duration', 0):.1f}s`",
        ]
        if caption:
            md.extend(["", f"> {caption[:140]}..."])

        if player and hasattr(player, "show_content"):
            player.show_content("Instagram Reel", "\n".join(md))
        if player and hasattr(player, "write_log"):
            player.write_log(f"Reels: {status} reel by {author}.")

        return f"Now playing Instagram Reel by {author}, sir."

    elif action in ("feed", "reels", "explore"):
        res = controller.open_reels_feed()
        if player and hasattr(player, "write_log"):
            player.write_log("Reels: Opened explore feed.")
        return "Opened Instagram Reels stream, sir."

    elif action in ("pause", "stop"):
        res = controller.pause()
        if player and hasattr(player, "write_log"):
            player.write_log("Reels: Playback paused.")
        return "Instagram Reel paused."

    elif action in ("resume", "unpause"):
        res = controller.play()
        if player and hasattr(player, "write_log"):
            player.write_log("Reels: Playback resumed.")
        return "Instagram Reel resumed."

    elif action in ("next", "next_reel", "skip"):
        res = controller.next_reel()
        tel = res.get("telemetry", {})
        author = tel.get("author") or "Creator"
        if player and hasattr(player, "write_log"):
            player.write_log(f"Reels: Advanced to next reel ({author}).")
        return f"Playing next Reel by {author}."

    elif action in ("prev", "previous", "prev_reel", "back"):
        res = controller.prev_reel()
        tel = res.get("telemetry", {})
        author = tel.get("author") or "Creator"
        if player and hasattr(player, "write_log"):
            player.write_log(f"Reels: Returned to previous reel ({author}).")
        return f"Playing previous Reel by {author}."

    elif action in ("mute", "unmute", "audio", "sound"):
        res = controller.toggle_mute()
        muted = res.get("result", {}).get("muted") if isinstance(res.get("result"), dict) else None
        state = "muted" if muted else "unmuted"
        return f"Instagram audio is now {state}."

    elif action in ("info", "status", "telemetry"):
        tel = controller.get_telemetry()
        if not tel.get("active"):
            return "No Instagram session is currently open."
        author = tel.get("author") or "Unknown"
        time_str = f"{tel.get('current_time', 0):.1f}s / {tel.get('duration', 0):.1f}s"
        return f"Reel by {author}. Status: {'Playing' if tel.get('is_playing') else 'Paused'} ({time_str})."

    elif action in ("close", "exit", "quit"):
        controller.close()
        return "Instagram session closed."

    return "Supported actions: play | reels | pause | resume | next | prev | mute | info | close"


TOOL = {
    "name": "instagram_control",
    "description": (
        "Controls Instagram Reels browser playback on macOS. "
        "Allows opening Reels by URL or feed, playing, pausing, skipping to next/prev reel, "
        "toggling sound, and retrieving caption and creator details."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "play | reels | pause | resume | next | prev | mute | info | close"
            },
            "url": {
                "type": "STRING",
                "description": "Instagram Reel URL or Reel ID (e.g. 'https://www.instagram.com/reel/C1234567/')"
            }
        }
    },
    "handler": instagram_control,
}

run = instagram_control
