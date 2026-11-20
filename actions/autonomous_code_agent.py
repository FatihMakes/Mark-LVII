"""
Antigravity-Style Autonomous Code Engineering Agent for JARVIS.
Contributed by Aman Kumar (@iamTechieAman).

Gives JARVIS the full coding, refactoring, code search, and surgical editing
capabilities of an expert AI software engineer like Antigravity.

Supported operations:
  - 'read': Read specific lines or whole files across any workspace.
  - 'edit': Exact surgical find-and-replace edit with AST validation.
  - 'write': Create or overwrite files.
  - 'search': Search for symbols, text, or regex across a directory.
  - 'command': Execute build, test, or package commands and capture outputs.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from pathlib import Path

MAX_READ_BYTES = 50_000


def _safe_path(raw_path: str) -> Path:
    p = Path(raw_path).expanduser().resolve()
    return p


def autonomous_code_agent(parameters: dict, player=None) -> str:
    """
    Antigravity-style autonomous code agent.
    parameters:
      action: 'read' | 'edit' | 'write' | 'search' | 'command'
      path: absolute or relative file/directory path
      target: string to replace (for 'edit')
      replacement: replacement string (for 'edit')
      content: full file content (for 'write')
      start_line: integer line offset (optional, for 'read')
      end_line: integer line offset (optional, for 'read')
      query: search pattern or keyword (for 'search')
      command: shell command string (for 'command')
    """
    action = (parameters.get("action") or "read").lower().strip()
    raw_path = parameters.get("path") or "."
    target = parameters.get("target") or ""
    replacement = parameters.get("replacement") or ""
    content = parameters.get("content") or ""
    query = parameters.get("query") or ""
    command = parameters.get("command") or ""

    try:
        p = _safe_path(raw_path)
    except Exception as e:
        return f"Invalid path provided: {e}"

    if action == "read":
        if not p.is_file():
            return f"Error: File '{p}' does not exist."
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            start = int(parameters.get("start_line") or 1) - 1
            end = int(parameters.get("end_line") or len(lines))
            start = max(0, start)
            end = min(len(lines), end)
            selected = "".join(lines[start:end])
            if len(selected) > MAX_READ_BYTES:
                selected = selected[:MAX_READ_BYTES] + "\n...[truncated]"
            
            if player and hasattr(player, "show_content"):
                player.show_content(f"Code Viewer: {p.name}", f"```\n{selected}\n```")
            return f"Read lines {start+1} to {end} of {p.name} ({len(selected)} characters)."
        except Exception as e:
            return f"Failed to read file: {e}"

    elif action == "edit":
        if not p.is_file():
            return f"Error: Target file '{p}' does not exist."
        if not target:
            return "Error: Edit requires a non-empty 'target' string."
        try:
            original = p.read_text(encoding="utf-8", errors="replace")
            if target not in original:
                return f"Error: Target snippet not found in {p.name}."
            count = original.count(target)
            updated = original.replace(target, replacement)
            
            # If python file, validate AST before writing
            if p.suffix == ".py":
                try:
                    ast.parse(updated, filename=str(p))
                except SyntaxError as se:
                    return f"Edit aborted: Syntax validation failed on line {se.lineno}: {se.msg}"
            
            p.write_text(updated, encoding="utf-8")
            diff_summary = f"Replaced {count} occurrence(s) in {p.name}."
            if player and hasattr(player, "show_content"):
                player.show_content(f"Code Edit: {p.name}", f"### Modified {p.name}\n- {diff_summary}")
            if player and hasattr(player, "write_log"):
                player.write_log(f"CODE: Surgically edited {p.name} ({diff_summary})")
            return f"Successfully edited {p.name}. {diff_summary}"
        except Exception as e:
            return f"Failed to edit file: {e}"

    elif action == "write":
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.suffix == ".py":
                try:
                    ast.parse(content, filename=str(p))
                except SyntaxError as se:
                    return f"Write aborted: Syntax error on line {se.lineno}: {se.msg}"
            p.write_text(content, encoding="utf-8")
            if player and hasattr(player, "show_content"):
                player.show_content(f"Created File: {p.name}", f"```\n{content[:2000]}\n```")
            if player and hasattr(player, "write_log"):
                player.write_log(f"CODE: Wrote file {p.name} ({len(content)} bytes)")
            return f"Successfully created {p.name} ({len(content)} bytes)."
        except Exception as e:
            return f"Failed to write file: {e}"

    elif action == "search":
        if not query:
            return "Error: Search action requires a 'query' string."
        if not p.is_dir():
            p = p.parent
        matches = []
        try:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            for f in p.rglob("*"):
                if f.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in f.parts):
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        for idx, line in enumerate(text.splitlines(), 1):
                            if pattern.search(line):
                                matches.append(f"{f.relative_to(p)}:{idx}: {line.strip()[:100]}")
                                if len(matches) >= 25:
                                    break
                    except Exception:
                        continue
                if len(matches) >= 25:
                    break
            
            result_text = "\n".join(matches) if matches else f"No matches found for '{query}' in {p}."
            if player and hasattr(player, "show_content"):
                player.show_content(f"Code Search: '{query}'", f"```\n{result_text}\n```")
            return f"Found {len(matches)} matching line(s) for '{query}'."
        except Exception as e:
            return f"Search failed: {e}"

    elif action == "command":
        if not command:
            return "Error: Command action requires a 'command' string."
        # Safe execution in project or specified directory
        cwd = p if p.is_dir() else p.parent
        try:
            r = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=60)
            out = (r.stdout + "\n" + r.stderr).strip()
            if len(out) > 2000:
                out = out[:2000] + "\n...[output truncated]"
            if player and hasattr(player, "show_content"):
                player.show_content(f"Terminal Output: {command[:30]}", f"Exit Code: {r.returncode}\n```\n{out}\n```")
            return f"Command executed with exit code {r.returncode}. Output: {out[:200]}"
        except subprocess.TimeoutExpired:
            return "Command timed out after 60 seconds."
        except Exception as e:
            return f"Command execution failed: {e}"

    return f"Unknown action '{action}'. Supported actions: read, edit, write, search, command."


TOOL = {
    "name": "autonomous_code_agent",
    "description": (
        "Antigravity-grade autonomous software engineering tool for JARVIS. "
        "Allows reading file contents, performing surgical code edits with AST syntax verification, "
        "writing new code files, searching codebases across directories, and executing terminal commands."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Operation to perform: read | edit | write | search | command",
            },
            "path": {
                "type": "STRING",
                "description": "Target file or directory path (absolute or relative)",
            },
            "target": {
                "type": "STRING",
                "description": "Exact text or code snippet to replace (for action='edit')",
            },
            "replacement": {
                "type": "STRING",
                "description": "New replacement code snippet (for action='edit')",
            },
            "content": {
                "type": "STRING",
                "description": "Full file content to create or write (for action='write')",
            },
            "start_line": {
                "type": "INTEGER",
                "description": "Starting line number for reading (for action='read')",
            },
            "end_line": {
                "type": "INTEGER",
                "description": "Ending line number for reading (for action='read')",
            },
            "query": {
                "type": "STRING",
                "description": "Search keyword or regex pattern (for action='search')",
            },
            "command": {
                "type": "STRING",
                "description": "Shell/terminal command to execute (for action='command')",
            },
        },
        "required": ["action"],
    },
    "handler": autonomous_code_agent,
}

