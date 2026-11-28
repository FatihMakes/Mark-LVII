"""
actions/media_search.py — Local Photo & Media Discovery Tool for JARVIS H3.3
Contributed by Aman Kumar (@iamTechieAman).

Supports:
  - Local image search by keyword, filename, and date
  - EXIF metadata and camera parameter extraction
  - Exact duplicate detection using cryptographic content hashing
  - Native macOS Preview integration
  - Strict privacy preservation (zero remote transmission)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from core.media_search import get_media_search_engine

logger = logging.getLogger("media_search_action")


def media_search(parameters: dict, player=None, session_memory=None) -> str:
    """
    Executes local-only photo and media searches, duplicate audits, and metadata review.
    """
    action = (parameters.get("action") or "search").lower().strip()
    query = parameters.get("query") or parameters.get("keyword") or ""
    file_path = parameters.get("path") or parameters.get("file") or ""
    directory = parameters.get("directory") or parameters.get("folder") or None

    engine = get_media_search_engine()

    if action in ("search", "find", "list"):
        results = engine.search_media(query, limit=12)
        if not results:
            return f"No local media files matching '{query}' were found in your standard folders, sir."

        lines = [
            f"# 🖼️ Local Media Search Results: '{query or 'Recent'}'",
            f"Found **{len(results)}** matching images across local directories:",
            ""
        ]
        for idx, r in enumerate(results, 1):
            dim = r.get("dimensions", "Unknown")
            cam = f" · {r.get('camera')}" if r.get("camera") and r.get("camera") != "Unknown" else ""
            lines.append(f"{idx}. **{r.get('name')}** (`{dim}`, {r.get('size_kb')} KB{cam})  \n   `{r.get('path')}`")

        md = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("Local Media Search", md)
        if player and hasattr(player, "write_log"):
            player.write_log(f"Media: Found {len(results)} images for '{query}'.")

        return f"Found {len(results)} local photos matching '{query}', sir."

    elif action in ("duplicates", "find_duplicates", "dedup"):
        target_dir = Path(directory) if directory else None
        dupes = engine.find_duplicates(target_dir, limit=8)
        if not dupes:
            return "No duplicate images detected in the scanned directory, sir."

        lines = [
            "# 🔍 Duplicate Images Detected",
            f"Identified **{len(dupes)}** sets of identical image files (exact MD5 hash matches):",
            ""
        ]
        for idx, d in enumerate(dupes, 1):
            lines.append(f"### Set {idx}: {d.get('count')} copies ({d.get('size_kb')} KB each)")
            lines.append(f"- **Primary:** `{d.get('primary')}`")
            for dup_path in d.get("duplicates", []):
                lines.append(f"- Duplicate: `{dup_path}`")
            lines.append("")

        md = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("Duplicate Media Audit", md)
        if player and hasattr(player, "write_log"):
            player.write_log(f"Media: Identified {len(dupes)} duplicate image sets.")

        return f"Found {len(dupes)} sets of duplicate images, sir."

    elif action in ("info", "inspect", "metadata", "exif"):
        if not file_path:
            return "Please provide the file path of the image to inspect."
        info = engine.get_image_info(file_path)
        if "error" in info:
            return f"Could not inspect file: {info['error']}"

        lines = [
            f"# 📷 Photo Metadata: {info.get('name')}",
            f"- **Path:** `{info.get('path')}`",
            f"- **Dimensions:** `{info.get('dimensions')}`",
            f"- **Format:** `{info.get('format', info.get('extension'))}`",
            f"- **Size:** `{info.get('size_kb')} KB`",
            f"- **Modified:** `{info.get('modified')}`",
            f"- **Camera:** `{info.get('camera')}`",
            f"- **Date Taken:** `{info.get('date_taken') or 'Not recorded'}`",
            f"- **EXIF Data Present:** `{'Yes' if info.get('has_exif') else 'No'}`",
        ]
        md = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("Image Metadata", md)

        return f"Image {info.get('name')} is {info.get('dimensions')} ({info.get('size_kb')} KB)."

    elif action in ("open", "preview", "view"):
        if not file_path:
            return "Please provide the image file path to open."
        ok = engine.open_in_macos_preview(file_path)
        if ok:
            return f"Opened {Path(file_path).name} in macOS Preview."
        return f"Unable to open file: {file_path}"

    return "Supported actions: search | duplicates | info | open"


TOOL = {
    "name": "media_search",
    "description": (
        "Local Photo & Media Discovery Tool for JARVIS H3.3. "
        "Enables searching local images by filename or metadata, detecting duplicate files, "
        "inspecting EXIF parameters, and opening photos in native macOS Preview. "
        "100% on-device private processing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "search | duplicates | info | open (default: search)"
            },
            "query": {
                "type": "STRING",
                "description": "Search keyword or filename substring"
            },
            "path": {
                "type": "STRING",
                "description": "Image file path for inspection or preview"
            },
            "directory": {
                "type": "STRING",
                "description": "Specific directory path to scan for duplicates"
            }
        }
    },
    "handler": media_search,
}

run = media_search
