"""
JARVIS H3.3 — Comprehensive Document & Media Library Manager
Provides persistent document management, searching, importing, previewing,
and native macOS integration (Preview, QuickLook, TextEdit).
Zero fake entries — every listed item is verified on the local filesystem.
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("jarvis.library")

DEFAULT_LIBRARY_DIR = Path.home() / "Desktop" / "JarvisLibrary"


class LibraryManager:
    """Manages files, folders, notes, and documents in the JARVIS persistent library."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or DEFAULT_LIBRARY_DIR).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        # Create standard folders
        for sub in ["Documents", "Reports", "Notes", "Projects", "Spreadsheets"]:
            (self.root_dir / sub).mkdir(parents=True, exist_ok=True)

    def list_files(
        self,
        subfolder: Optional[str] = None,
        file_type: Optional[str] = None,
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """Lists real files in library, categorized by type with sizes and timestamps."""
        target_dir = (self.root_dir / subfolder).resolve() if subfolder else self.root_dir
        if not target_dir.exists() or not target_dir.is_dir():
            target_dir = self.root_dir

        results: List[Dict[str, Any]] = []
        pattern = "**/*" if recursive else "*"

        try:
            for item in target_dir.glob(pattern):
                try:
                    if item.is_file() and not item.name.startswith("."):
                        ext = item.suffix.lower()
                        cat = self._categorize_extension(ext)
                        if file_type and file_type.lower() != cat.lower() and file_type.lower() != ext:
                            continue
                        stat = item.stat()
                        results.append({
                            "name": item.name,
                            "path": str(item),
                            "relative_path": str(item.relative_to(self.root_dir)),
                            "size_bytes": stat.st_size,
                            "size_str": self._format_size(stat.st_size),
                            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                            "type": cat,
                            "extension": ext
                        })
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except Exception as e:
            logger.error(f"Error scanning library directory: {e}")

        results.sort(key=lambda x: x["name"].lower())
        return results

    def list_folders(self) -> List[Dict[str, Any]]:
        """Lists available subdirectories in the library."""
        folders = []
        try:
            for item in self.root_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    folders.append({
                        "name": item.name,
                        "path": str(item),
                        "items_count": len([x for x in item.iterdir() if not x.name.startswith(".")])
                    })
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
        folders.sort(key=lambda x: x["name"])
        return folders

    def search_library(self, query: str) -> List[Dict[str, Any]]:
        """Searches files by name and text content across the library."""
        q = query.strip().lower()
        if not q:
            return self.list_files(recursive=True)

        matches = []
        for f in self.list_files(recursive=True):
            p = Path(f["path"])
            # Match in file name
            if q in f["name"].lower():
                f["match_type"] = "filename"
                matches.append(f)
                continue
            # Match in text content for readable formats
            if f["type"] in ("Document", "Note", "Spreadsheet"):
                try:
                    text = self.read_document_text(str(p), max_chars=10000).lower()
                    if q in text:
                        f["match_type"] = "content"
                        matches.append(f)
                except Exception:
                    pass
        return matches

    def import_document(self, source_path: str, dest_folder: Optional[str] = None) -> Dict[str, Any]:
        """Imports an external file from disk into the library."""
        src = Path(source_path).expanduser().resolve()
        if not src.is_file():
            return {"status": "error", "message": f"Source file does not exist: {source_path}"}

        target_dir = (self.root_dir / dest_folder).resolve() if dest_folder else self.root_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / src.name

        try:
            if src.resolve() == dest.resolve():
                return {
                    "status": "success",
                    "message": f"'{src.name}' is already present in library.",
                    "path": str(dest)
                }
            shutil.copy2(src, dest)
            return {
                "status": "success",
                "message": f"Imported '{src.name}' into Library ({self._format_size(dest.stat().st_size)}).",
                "path": str(dest)
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to import file: {e}"}

    def save_note(self, title: str, content: str, folder: str = "Notes") -> Dict[str, Any]:
        """Creates or updates a persistent markdown note in the library."""
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip() or "Untitled"
        filename = f"{clean_title}.md"
        target_dir = self.root_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / filename

        try:
            dest.write_text(content, encoding="utf-8")
            return {
                "status": "success",
                "message": f"Saved note '{filename}' to Library/{folder}.",
                "path": str(dest),
                "size_bytes": dest.stat().st_size
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to save note: {e}"}

    def read_document_text(self, file_path: str, max_chars: int = 15000) -> str:
        """Extracts text from PDF, Word (.docx), Excel/CSV, markdown, and text files."""
        p = Path(file_path).expanduser().resolve()
        if not p.is_file():
            return f"Error: File does not exist at {file_path}"

        ext = p.suffix.lower()

        # PDF extraction
        if ext == ".pdf":
            try:
                import pymupdf
                doc = pymupdf.open(str(p))
                pages = [page.get_text() or "" for page in doc]
                doc.close()
                text = "\n\n--- Page Break ---\n\n".join(pages)
                return text[:max_chars] if text.strip() else "[PDF contains no extractable text]"
            except Exception as e:
                return f"Error reading PDF: {e}"

        # Word Document
        elif ext in (".docx", ".doc"):
            try:
                import docx
                doc = docx.Document(p)
                paragraphs = [para.text for para in doc.paragraphs if para.text]
                return "\n\n".join(paragraphs)[:max_chars]
            except Exception as e:
                return f"Error reading Word document: {e}"

        # CSV / Spreadsheet
        elif ext == ".csv":
            try:
                import csv
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    r = csv.reader(f)
                    lines = [", ".join(row) for i, row in enumerate(r) if i < 150]
                return "\n".join(lines)[:max_chars]
            except Exception as e:
                return f"Error reading CSV: {e}"

        elif ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(p, data_only=True)
                lines = []
                for sheet in wb.sheetnames[:3]:
                    ws = wb[sheet]
                    lines.append(f"Sheet: {sheet}")
                    for row in list(ws.iter_rows(values_only=True))[:50]:
                        lines.append(" | ".join(str(c) for c in row if c is not None))
                return "\n".join(lines)[:max_chars]
            except Exception as e:
                return f"Error reading spreadsheet: {e}"

        # Plain Text / Markdown / Code
        else:
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(max_chars)
            except Exception as e:
                return f"Error reading text: {e}"

    def open_in_macos_viewer(self, file_path: str) -> Dict[str, Any]:
        """Opens file in native macOS Preview or default system application."""
        p = Path(file_path).expanduser().resolve()
        if not p.is_file():
            return {"status": "error", "message": f"File does not exist: {file_path}"}

        ext = p.suffix.lower()
        try:
            if ext in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp"):
                subprocess.Popen(["open", "-a", "Preview", str(p)])
            else:
                subprocess.Popen(["open", str(p)])
            return {"status": "success", "message": f"Opened '{p.name}' in macOS viewer.", "path": str(p)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to launch macOS viewer: {e}"}

    def create_folder(self, folder_name: str, parent_subfolder: Optional[str] = None) -> Dict[str, Any]:
        """Creates a new folder inside the Library."""
        clean = "".join(c for c in folder_name if c.isalnum() or c in (" ", "-", "_")).strip()
        if not clean:
            return {"status": "error", "message": "Invalid folder name."}
        target = (self.root_dir / parent_subfolder / clean) if parent_subfolder else (self.root_dir / clean)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return {"status": "success", "message": f"Folder '{clean}' created.", "path": str(target)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def rename_item(self, old_path: str, new_name: str) -> Dict[str, Any]:
        """Renames a file or folder in the Library."""
        p = Path(old_path).expanduser().resolve()
        if not p.exists():
            return {"status": "error", "message": "Item does not exist."}
        dest = p.parent / new_name
        try:
            p.rename(dest)
            return {"status": "success", "message": f"Renamed to '{new_name}'.", "new_path": str(dest)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_item(self, target_path: str, confirmed: bool = False) -> Dict[str, Any]:
        """Deletes a file or directory with explicit owner confirmation safety."""
        if not confirmed:
            return {
                "status": "confirmation_required",
                "message": f"Deletion of '{Path(target_path).name}' requires explicit confirmation."
            }
        p = Path(target_path).expanduser().resolve()
        if not p.exists():
            return {"status": "error", "message": "Item does not exist."}
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return {"status": "success", "message": f"Successfully deleted '{p.name}'."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _categorize_extension(self, ext: str) -> str:
        if ext in (".pdf", ".docx", ".doc", ".odt"):
            return "Document"
        elif ext in (".xlsx", ".xls", ".csv", ".numbers"):
            return "Spreadsheet"
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"):
            return "Image"
        elif ext in (".md", ".txt", ".rtf"):
            return "Note"
        elif ext in (".py", ".js", ".ts", ".html", ".css", ".sh", ".json"):
            return "Code"
        return "File"

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{round(size_bytes / 1024, 1)} KB"
        else:
            return f"{round(size_bytes / (1024 * 1024), 2)} MB"


_library_manager_instance: Optional[LibraryManager] = None

def get_library_manager() -> LibraryManager:
    global _library_manager_instance
    if _library_manager_instance is None:
        _library_manager_instance = LibraryManager()
    return _library_manager_instance
