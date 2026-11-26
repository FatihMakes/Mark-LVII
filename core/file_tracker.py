"""
core/file_tracker.py — Persistent File Tracking & Resolution Engine for JARVIS.
Contributed by Aman Kumar (@iamTechieAman).

Maintains a persistent registry of all files created, generated, modified, downloaded,
or referenced during JARVIS sessions in `memory/file_registry.json`.
Solves the real-world problem where the assistant creates or downloads a file, but on subsequent
turns the user asks "kaha save kiya hai", "wo file kholo", or "file nahi mil rahi", and the assistant
fails to locate it.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.file_tracker")

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "memory" / "file_registry.json"
MAX_REGISTRY_ENTRIES = 120

COMMON_SEARCH_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Documents",
    Path.home(),
]

EXCLUDED_DIR_NAMES = {
    ".git", ".venv", "venv", "node_modules", "Library", ".cache",
    ".Trash", ".npm", "__pycache__", ".vscode", ".idea", ".antigravity"
}


class FileTrackerEngine:
    def __init__(self, registry_file: Path = REGISTRY_PATH):
        self.registry_file = registry_file
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.registry_file.is_file():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._entries = data
            except Exception as e:
                logger.warning(f"Could not load file registry: {e}")
                self._entries = []
        else:
            self._entries = []

    def _save(self) -> None:
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            # Prune to max entries
            self._entries = self._entries[:MAX_REGISTRY_ENTRIES]
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save file registry: {e}")

    def register_file(
        self,
        path: str | Path,
        action: str = "created",
        description: str = "",
        size_bytes: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Registers a created, modified, or downloaded file into persistent memory."""
        try:
            p = Path(path).expanduser().resolve()
        except Exception:
            p = Path(path)

        exists = p.exists()
        calc_size = 0
        if exists and p.is_file():
            try:
                calc_size = p.stat().st_size
            except Exception:
                calc_size = 0
        if size_bytes is not None:
            calc_size = size_bytes

        entry: Dict[str, Any] = {
            "path": str(p),
            "name": p.name,
            "stem": p.stem,
            "extension": p.suffix.lower(),
            "action": action,
            "description": description or f"{action.replace('_', ' ').capitalize()} file",
            "size_bytes": calc_size,
            "size_str": self.format_size(calc_size),
            "created_at": time.time(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exists": exists,
            "metadata": metadata or {}
        }

        # Deduplicate: if path already in entries, remove old occurrence
        self._entries = [e for e in self._entries if e.get("path") != str(p)]
        # Insert newest at top
        self._entries.insert(0, entry)
        self._save()
        logger.info(f"Registered file: {p.name} ({entry['action']}) at {p}")
        return entry

    def get_recent_files(self, limit: int = 10, extension: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recent tracked files, verifying if they currently exist on disk."""
        results = []
        ext_clean = extension.lower().strip() if extension else None
        if ext_clean and not ext_clean.startswith("."):
            ext_clean = f".{ext_clean}"

        for e in self._entries:
            if ext_clean and e.get("extension") != ext_clean:
                continue
            p = Path(e.get("path", ""))
            e["exists"] = p.exists()
            if e["exists"]:
                results.append(e)
            if len(results) >= limit:
                break
        return results

    def get_latest_file(self, extension: Optional[str] = None, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Finds the most recently registered file matching criteria."""
        recents = self.get_recent_files(limit=30, extension=extension)
        if not query:
            return recents[0] if recents else None

        q = query.lower().strip()
        for r in recents:
            if q in r.get("name", "").lower() or q in r.get("description", "").lower():
                return r
        return recents[0] if recents else None

    def find_tracked_file(self, query: str) -> Optional[Dict[str, Any]]:
        """Fuzzy search across tracked files by name or description."""
        q = query.lower().strip()
        for e in self._entries:
            name = e.get("name", "").lower()
            stem = e.get("stem", "").lower()
            if q == name or q == stem or q in name:
                p = Path(e.get("path", ""))
                if p.exists():
                    e["exists"] = True
                    return e
        return None

    def locate_file(self, query_name: str, preferred_ext: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fast disk search across common user roots (Desktop, Downloads, Documents)
        ignoring heavyweight virtualenvs, git directories and caches.
        """
        # First check tracked memory
        tracked = self.find_tracked_file(query_name)
        if tracked:
            return [tracked]

        matches: List[Dict[str, Any]] = []
        q = query_name.lower().strip()
        ext_clean = preferred_ext.lower().strip() if preferred_ext else None
        if ext_clean and not ext_clean.startswith("."):
            ext_clean = f".{ext_clean}"

        for root in COMMON_SEARCH_ROOTS:
            if not root.is_dir():
                continue
            try:
                # Scan top-level first
                for item in root.iterdir():
                    if item.name.startswith(".") or item.name in EXCLUDED_DIR_NAMES:
                        continue
                    if item.is_file():
                        if q in item.name.lower():
                            if not ext_clean or item.suffix.lower() == ext_clean:
                                matches.append({
                                    "path": str(item.resolve()),
                                    "name": item.name,
                                    "extension": item.suffix.lower(),
                                    "size_bytes": item.stat().st_size,
                                    "size_str": self.format_size(item.stat().st_size),
                                    "source": str(root.name),
                                    "exists": True
                                })
                                if len(matches) >= 8:
                                    return matches
                    elif item.is_dir():
                        # Scan 1 subfolder level deep
                        try:
                            for sub in item.iterdir():
                                if sub.name.startswith(".") or sub.name in EXCLUDED_DIR_NAMES:
                                    continue
                                if sub.is_file() and q in sub.name.lower():
                                    if not ext_clean or sub.suffix.lower() == ext_clean:
                                        matches.append({
                                            "path": str(sub.resolve()),
                                            "name": sub.name,
                                            "extension": sub.suffix.lower(),
                                            "size_bytes": sub.stat().st_size,
                                            "size_str": self.format_size(sub.stat().st_size),
                                            "source": f"{root.name}/{item.name}",
                                            "exists": True
                                        })
                                        if len(matches) >= 8:
                                            return matches
                        except Exception:
                            continue
            except Exception:
                continue

        return matches

    def open_or_preview(self, target_path: str | Path, app_name: Optional[str] = None) -> Tuple[bool, str]:
        """Opens or previews a file on the native host operating system."""
        p = Path(target_path).expanduser().resolve()
        if not p.exists():
            return False, f"File does not exist: {p}"

        if sys.platform == "darwin":
            try:
                if app_name:
                    res = subprocess.run(["open", "-a", app_name, str(p)], capture_output=True, timeout=5)
                elif p.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".tiff"]:
                    res = subprocess.run(["open", "-a", "Preview", str(p)], capture_output=True, timeout=5)
                else:
                    res = subprocess.run(["open", str(p)], capture_output=True, timeout=5)
                if res.returncode == 0:
                    return True, f"Opened '{p.name}' in Preview/Viewer."
                else:
                    return False, f"Failed to open '{p.name}': {res.stderr.decode().strip()}"
            except Exception as e:
                return False, f"Error launching preview: {e}"
        elif sys.platform == "win32":
            try:
                os.startfile(str(p))
                return True, f"Opened '{p.name}'."
            except Exception as e:
                return False, f"Error opening file: {e}"
        else:
            try:
                res = subprocess.run(["xdg-open", str(p)], capture_output=True, timeout=5)
                return (res.returncode == 0), f"Opened '{p.name}'."
            except Exception as e:
                return False, f"Error opening file: {e}"

    @staticmethod
    def format_size(size_bytes: int) -> str:
        b = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if b < 1024.0 or unit == "TB":
                return f"{b:.1f} {unit}" if unit != "B" else f"{int(b)} B"
            b /= 1024.0
        return f"{size_bytes} B"


_tracker_instance: Optional[FileTrackerEngine] = None


def get_file_tracker() -> FileTrackerEngine:
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = FileTrackerEngine()
    return _tracker_instance
