"""
JARVIS H3.2 — Anime Control Action
Integrates ani-cli voice and text actions into the core action registry.
Thread-safe for PyQt UI via player.
"""

from typing import Dict, Any, Optional
from core.anime_controller import get_anime_controller


def anime_control_handler(parameters: Dict[str, Any], player=None, speak=None) -> str:
    """
    Executes anime entertainment commands.
    """
    controller = get_anime_controller()
    raw_query = parameters.get("query", "").strip()
    action = parameters.get("action")
    episode = parameters.get("episode")
    dub = parameters.get("dub", False)
    quality = parameters.get("quality", "best")

    # If action is not explicitly passed, infer it from query
    if not action:
        parsed = controller.parse_voice_command(raw_query)
        action = parsed.get("action", "search")
        if "query" in parsed:
            raw_query = parsed["query"]
        if "title" in parsed:
            raw_query = parsed["title"]
        if "episode" in parsed and not episode:
            episode = parsed["episode"]
        if "dub" in parsed:
            dub = parsed["dub"]

    if episode is None:
        episode = 1

    if action == "play":
        target_title = raw_query or "Naruto"
        res = controller.play_anime(
            title=target_title,
            episode=episode,
            dub=dub,
            quality=quality
        )
        msg = res.get("message", f"Playing {target_title} episode {episode}.")
        if player:
            player.write_log(f"🎬 Anime Play: {target_title} Ep {episode} ({'Dub' if dub else 'Sub'})")
            player.show_content(f"Anime: {target_title}", f"Episode: {episode}\nMode: {'Dub' if dub else 'Sub'}\nStatus: Launching Player...")
        return msg

    elif action == "continue":
        res = controller.continue_watching()
        msg = res.get("message", "Resuming anime playback.")
        if player:
            player.write_log(f"🎬 Anime: {msg}")
            player.show_content("Anime Resumed", msg)
        return msg

    elif action == "episodes":
        target = raw_query or "Naruto"
        data = controller.get_episodes(target)
        title = data.get("title", target)
        total = data.get("total_episodes", "Unknown")
        status = data.get("status", "Active")
        seasons = data.get("seasons", [])

        lines = [
            f"🎬 **{title}**",
            f"• **Status**: {status}",
            f"• **Available Episodes**: {total}",
        ]
        if seasons:
            lines.append("\n**Story Arcs / Seasons:**")
            for s in seasons:
                lines.append(f"• {s['name']}: Episodes {s['episodes']}")

        lines.append(f"\nSay 'Play {title} episode <number>' to stream instantly.")
        content = "\n".join(lines)

        if player:
            player.write_log(f"🎬 Anime Episodes: {title} ({total} eps)")
            player.show_content(f"Episodes: {title}", content)

        return f"{title} has {total} episodes available. Status is {status}. Would you like me to start episode 1 or a specific episode?"

    elif action == "history":
        history = controller.get_history()
        if not history:
            return "Your anime watch history is currently empty."
        lines = ["**Recent Anime Watch History:**"]
        for idx, item in enumerate(history[:5], start=1):
            lines.append(f"{idx}. {item.get('title')} — Episode {item.get('episode')} ({'Dub' if item.get('dub') else 'Sub'}) [{item.get('timestamp')}]")
        content = "\n".join(lines)
        if player:
            player.write_log("🎬 Anime History retrieved")
            player.show_content("Anime Watch History", content)
        return f"You recently watched {history[0].get('title')} episode {history[0].get('episode')}."

    else:  # default search
        target = raw_query or "Naruto"
        results = controller.search(target, limit=5)
        if not results:
            return f"I couldn't find any anime matching '{target}'."

        lines = [f"**Anime Search Results for '{target}':**"]
        for idx, r in enumerate(results, start=1):
            lines.append(f"{idx}. **{r['title']}** — {r.get('episodes', 'Available')} ({r.get('status', 'Streamable')})")
        lines.append("\nSay 'Play <anime name>' to start streaming.")
        content = "\n".join(lines)

        if player:
            player.write_log(f"🎬 Anime Search: {target} ({len(results)} found)")
            player.show_content(f"Anime Search: {target}", content)

        top_title = results[0]["title"]
        top_eps = results[0].get("episodes", "")
        return f"Found {len(results)} matches for {target}. Top result is {top_title} with {top_eps}. Would you like me to play it?"


TOOL = {
    "name": "anime_control",
    "description": "Stream and search anime series, list episodes, toggle dub/sub, and manage watch history using ani-cli and macOS media players.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Anime title or search query, e.g. 'Naruto', 'One Piece', 'Bleach'"
            },
            "action": {
                "type": "STRING",
                "enum": ["play", "search", "episodes", "continue", "history"],
                "description": "Action to perform: play episode, search titles, list episodes, continue watching, or view history."
            },
            "episode": {
                "type": "INTEGER",
                "description": "Episode number to play (defaults to 1)"
            },
            "dub": {
                "type": "BOOLEAN",
                "description": "True for English dub, False for original Japanese with English subtitles"
            },
            "quality": {
                "type": "STRING",
                "description": "Video quality: 'best', '1080p', '720p', '480p', 'worst'"
            }
        }
    },
    "handler": anime_control_handler
}
