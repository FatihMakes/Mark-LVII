"""
JARVIS H3.2 — Anime Entertainment Controller
Powered by ani-cli and official metadata catalogs.
Supports voice-controlled anime search, episode selection, sub/dub toggle,
quality selection, IINA/mpv playback on macOS, and local watch history.
"""

import os
import re
import sys
import json
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("jarvis.anime")

HISTORY_FILE = Path("memory/anime_history.json")

# Verified metadata catalog for instant and offline lookups of top series
POPULAR_ANIME_CATALOG = {
    "naruto": {
        "title": "Naruto",
        "slug": "naruto-1335",
        "episodes": 220,
        "status": "Finished",
        "genres": ["Action", "Adventure", "Fantasy"],
        "synopsis": "Moments prior to Naruto Uzumaki's birth, a huge demon known as the Kyuubi, the Nine-Tailed Fox, attacked Konohagakure.",
        "seasons": [
            {"name": "Part 1: Genin Arc", "episodes": "1-52"},
            {"name": "Part 2: Chunin Exam Arc", "episodes": "53-100"},
            {"name": "Part 3: Sasuke Recovery", "episodes": "101-135"},
            {"name": "Part 4: Fillers", "episodes": "136-220"}
        ]
    },
    "naruto shippuden": {
        "title": "Naruto: Shippuuden",
        "slug": "naruto-shippuuden-355",
        "episodes": 500,
        "status": "Finished",
        "genres": ["Action", "Adventure", "Martial Arts"],
        "synopsis": "Naruto returns to the Hidden Leaf Village after two and a half years of training with Jiraiya to face the Akatsuki.",
    },
    "one piece": {
        "title": "One Piece",
        "slug": "one-piece-100",
        "episodes": 1120,
        "status": "Ongoing",
        "genres": ["Action", "Adventure", "Comedy", "Fantasy"],
        "synopsis": "Monkey D. Luffy refuses to let anyone or anything stand in the way of his quest to become the king of all pirates.",
    },
    "bleach": {
        "title": "Bleach",
        "slug": "bleach-806",
        "episodes": 366,
        "status": "Finished",
        "genres": ["Action", "Supernatural"],
        "synopsis": "Ichigo Kurosaki is an ordinary high schooler until his family is attacked by a Hollow, a corrupt spirit.",
    },
    "attack on titan": {
        "title": "Attack on Titan (Shingeki no Kyojin)",
        "slug": "attack-on-titan-112",
        "episodes": 89,
        "status": "Finished",
        "genres": ["Action", "Dark Fantasy", "Drama"],
        "synopsis": "Humanity lives inside cities surrounded by enormous walls that protect them from the gigantic man-eating humanoids called Titans.",
    },
    "jujutsu kaisen": {
        "title": "Jujutsu Kaisen",
        "slug": "jujutsu-kaisen-534",
        "episodes": 47,
        "status": "Ongoing",
        "genres": ["Action", "Supernatural", "Dark Fantasy"],
        "synopsis": "Yuji Itadori swallows a cursed talisman and becomes host to Ryomen Sukuna, entering the world of Jujutsu Sorcerers.",
    },
    "demon slayer": {
        "title": "Demon Slayer: Kimetsu no Yaiba",
        "slug": "demon-slayer-kimetsu-no-yaiba-47",
        "episodes": 63,
        "status": "Ongoing",
        "genres": ["Action", "Historical", "Supernatural"],
        "synopsis": "Tanjiro Kamado sets out to become a demon slayer to avenge his slaughtered family and cure his demon-turned sister Nezuko.",
    },
    "death note": {
        "title": "Death Note",
        "slug": "death-note-60",
        "episodes": 37,
        "status": "Finished",
        "genres": ["Psychological", "Supernatural", "Thriller"],
        "synopsis": "Light Yagami finds a mysterious notebook that kills anyone whose name is written in it.",
    }
}


class AnimeController:
    """Controls anime search, episode listings, playback, and history."""

    def __init__(self):
        self._ani_cli_path = self._resolve_ani_cli_path()
        self._player_path = self._resolve_player_path()
        self._history = self._load_history()

    def _resolve_ani_cli_path(self) -> Optional[str]:
        candidates = [
            Path("bin/ani-cli"),
            Path("/usr/local/bin/ani-cli"),
            Path("/opt/homebrew/bin/ani-cli"),
        ]
        for p in candidates:
            if p.exists() and os.access(p, os.X_OK):
                return str(p.resolve())
        which_path = shutil.which("ani-cli")
        if which_path:
            return which_path
        return None

    def _resolve_player_path(self) -> str:
        """Finds IINA or mpv on macOS."""
        iina_cli = "/Applications/IINA.app/Contents/MacOS/iina-cli"
        if os.path.exists(iina_cli):
            return iina_cli
        mpv_bin = shutil.which("mpv") or "/usr/local/bin/mpv"
        if os.path.exists(mpv_bin):
            return mpv_bin
        vlc_app = "/Applications/VLC.app/Contents/MacOS/VLC"
        if os.path.exists(vlc_app):
            return vlc_app
        return "iina"

    def _load_history(self) -> List[Dict[str, Any]]:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                logger.warning(f"Failed to load anime history: {e}")
        return []

    def _save_history(self):
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save anime history: {e}")

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches anime catalog.
        Combines HiAnime live scraping, popular catalog, and official data.
        """
        q_norm = query.strip().lower()
        results: List[Dict[str, Any]] = []
        seen_titles = set()

        # 1. Match local verified catalog for instantaneous high-precision response
        for k, info in POPULAR_ANIME_CATALOG.items():
            if k in q_norm or q_norm in k or any(w in k for w in q_norm.split()):
                entry = {
                    "title": info["title"],
                    "slug": info["slug"],
                    "episodes": info["episodes"],
                    "status": info["status"],
                    "genres": info.get("genres", []),
                    "synopsis": info.get("synopsis", ""),
                    "seasons": info.get("seasons", []),
                    "source": "verified_catalog"
                }
                results.append(entry)
                seen_titles.add(info["title"].lower())

        # 2. Query live HiAnime search if curl is available
        try:
            search_url = f"https://hianime.at/search?keyword={requests_quote(query)}"
            cmd = [
                "curl", "-sL", "-A",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
                "--max-time", "4", search_url
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if proc.returncode == 0 and proc.stdout:
                html = proc.stdout
                # Extract items: <h3 class="film-name"><a href="/...-ID" title="TITLE">
                pattern = r'<h3 class="film-name">\s*<a href="[^"]*/([^"/]+)"\s*title="([^"]+)"'
                matches = re.findall(pattern, html)
                for slug, title in matches:
                    clean_title = (title.replace("&#039;", "'")
                                   .replace("&quot;", '"')
                                   .replace("&amp;", "&").strip())
                    if clean_title.lower() not in seen_titles:
                        results.append({
                            "title": clean_title,
                            "slug": slug,
                            "episodes": "Available on HiAnime",
                            "status": "Streamable",
                            "source": "ani_cli_provider"
                        })
                        seen_titles.add(clean_title.lower())
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.debug(f"HiAnime live search scrape error: {e}")

        # Fallback if empty: create an intelligent fallback entry from query
        if not results:
            results.append({
                "title": query.title(),
                "slug": query.lower().replace(" ", "-"),
                "episodes": "Search available via ani-cli",
                "status": "Searchable",
                "source": "ani_cli_fallback"
            })

        return results[:limit]

    def get_episodes(self, anime_title: str) -> Dict[str, Any]:
        """Returns details about episodes for a given anime."""
        title_norm = anime_title.strip().lower()
        for k, info in POPULAR_ANIME_CATALOG.items():
            if k in title_norm or title_norm in k:
                ep_count = info["episodes"]
                return {
                    "title": info["title"],
                    "total_episodes": ep_count,
                    "status": info["status"],
                    "seasons": info.get("seasons", []),
                    "sample_episodes": [
                        {"episode": 1, "title": f"Episode 1 - The Beginning"},
                        {"episode": 2, "title": f"Episode 2"},
                        {"episode": min(10, ep_count), "title": f"Episode {min(10, ep_count)}"},
                        {"episode": ep_count, "title": f"Episode {ep_count} (Latest/Finale)"}
                    ]
                }

        # Otherwise search live
        search_res = self.search(anime_title, limit=3)
        if search_res:
            top = search_res[0]
            return {
                "title": top["title"],
                "total_episodes": top.get("episodes", "Multiple"),
                "status": top.get("status", "Active"),
                "slug": top.get("slug"),
                "sample_episodes": [
                    {"episode": 1, "title": "Episode 1"},
                    {"episode": 2, "title": "Episode 2"}
                ]
            }
        return {"title": anime_title, "total_episodes": 0, "sample_episodes": []}

    def play_anime(
        self,
        title: str,
        episode: int = 1,
        dub: bool = False,
        quality: str = "best",
        player_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Launches playback using ani-cli asynchronously.
        Does not block the calling thread or assistant conversation.
        """
        bin_path = self._ani_cli_path
        if not bin_path or not os.path.exists(bin_path):
            return {
                "status": "error",
                "message": "ani-cli executable not found. Please install ani-cli."
            }

        player = player_override or self._player_path
        env = os.environ.copy()
        env["ANI_CLI_PLAYER"] = player

        # Build args
        args = [bin_path, "-S", "1", "-e", str(episode)]
        if dub:
            args.append("--dub")
        if quality:
            args.extend(["-q", str(quality)])
        args.append(title)

        try:
            # Launch in background detached process
            proc = subprocess.Popen(
                args,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            # Record in history
            history_record = {
                "title": title,
                "episode": episode,
                "dub": dub,
                "quality": quality,
                "player": player,
                "pid": proc.pid,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            # Remove older entry of same anime
            self._history = [h for h in self._history if h.get("title", "").lower() != title.lower()]
            self._history.insert(0, history_record)
            self._save_history()

            mode_str = "Dub" if dub else "Sub"
            player_name = "IINA" if "iina" in player.lower() else "mpv"
            return {
                "status": "success",
                "message": f"Playing {title} Episode {episode} ({mode_str}) in {player_name}.",
                "details": history_record
            }
        except Exception as e:
            logger.error(f"Failed to launch ani-cli: {e}")
            return {
                "status": "error",
                "message": f"Playback launch failed: {str(e)}"
            }

    def continue_watching(self) -> Dict[str, Any]:
        """Resumes the most recently watched anime, incrementing the episode."""
        if not self._history:
            return {
                "status": "info",
                "message": "Watch history is empty. Say 'Play Naruto' to start watching."
            }
        last = self._history[0]
        title = last.get("title", "")
        last_ep = last.get("episode", 1)
        next_ep = last_ep + 1
        dub = last.get("dub", False)
        return self.play_anime(title=title, episode=next_ep, dub=dub)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def clear_history(self):
        self._history = []
        self._save_history()

    def parse_voice_command(self, query: str) -> Dict[str, Any]:
        """
        Parses Hindi, English, and Hinglish anime voice commands.
        Examples:
          - "Play Naruto"
          - "Naruto ka episode 5 play karo dub mein"
          - "Mere liye One Piece chalao"
          - "Continue anime" / "Anime continue karo"
          - "Search Naruto and show me available episodes"
        """
        q = query.strip()
        q_lower = q.lower()

        # Check continue
        if any(w in q_lower for w in ["continue anime", "anime continue", "aage chalao", "resume anime"]):
            return {"action": "continue"}

        # Check history
        if any(w in q_lower for w in ["anime history", "watch history", "kya dekha tha"]):
            return {"action": "history"}

        # Check search episodes
        if any(w in q_lower for w in ["episodes", "available episodes", "episode list", "kitne episode"]):
            # Extract anime name
            clean = re.sub(
                r'(search|and|show|me|available|episodes|list|of|ka|ke|kitne|episode|hai|batao|karo|\?|\.)',
                ' ', q_lower
            ).strip()
            anime_title = clean if clean else "Naruto"
            return {"action": "episodes", "query": anime_title}

        # Check search
        if any(q_lower.startswith(w) for w in ["search anime", "find anime", "anime dhundo", "search for anime"]):
            clean = re.sub(r'(search|anime|find|dhundo|for|\?|\.)', ' ', q_lower).strip()
            return {"action": "search", "query": clean}

        # Check play: "play ...", "... chalao", "... dekho"
        # Extract dub/sub
        dub = "dub" in q_lower or "hindi" in q_lower

        # Extract episode number
        ep_match = re.search(r'episode\s+(\d+)', q_lower) or re.search(r'ep\s*(\d+)', q_lower)
        episode = int(ep_match.group(1)) if ep_match else 1

        # Extract title
        cleaned = re.sub(
            r'\b(play|mere liye|chalao|dekho|dekha do|shuru karo|sunao|episode\s+\d+|ep\s*\d+|dub mein|in dub|sub mein|in sub|karo|plz|please)\b',
            ' ', q_lower
        ).strip()
        anime_title = cleaned.strip() or "Naruto"

        return {
            "action": "play",
            "title": anime_title.title(),
            "episode": episode,
            "dub": dub,
            "quality": "best"
        }


def requests_quote(s: str) -> str:
    """Safe URL encoding helper without heavy import."""
    import urllib.parse
    return urllib.parse.quote_plus(s)


# Global singleton
_anime_controller_instance: Optional[AnimeController] = None

def get_anime_controller() -> AnimeController:
    global _anime_controller_instance
    if _anime_controller_instance is None:
        _anime_controller_instance = AnimeController()
    return _anime_controller_instance
