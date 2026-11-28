"""
JARVIS H3.2 — macOS Deep Scan & System Audit Action
Executes read-only system diagnostics, process analysis, and file discovery.
Thread-safe for UI via player.
"""

from typing import Dict, Any, Optional
from core.mac_analyzer import get_mac_analyzer


def mac_scan_handler(parameters: Dict[str, Any], player=None, speak=None) -> str:
    """Entry point for macOS Deep Scan and System Audit."""
    analyzer = get_mac_analyzer()
    mode = parameters.get("mode", "").lower().strip()

    # Auto-detect mode from query
    query = (parameters.get("query") or "").lower()
    if not mode:
        if "duplicate" in query:
            mode = "duplicates"
        elif "large" in query or "big file" in query or "size" in query:
            mode = "large_files"
        elif "dot" in query or "hidden" in query:
            mode = "dotfiles"
        elif "process" in query or "ram" in query or "cpu" in query:
            mode = "processes"
        else:
            mode = "audit"

    if mode in ["audit", "system_audit", "diagnostics", "health"]:
        audit = analyzer.run_system_audit()
        metrics = audit.get("metrics", {})
        findings = audit.get("findings", [])

        lines = [
            f"🖥️ **JARVIS System Diagnostics & Health Audit**",
            f"• **Timestamp**: {audit.get('audit_timestamp')} ({audit.get('duration_sec')}s scan)",
            f"• **Memory**: {metrics.get('Memory', 'N/A')}",
            f"• **CPU**: {metrics.get('CPU', 'N/A')}",
            f"• **Disk**: {metrics.get('Disk', 'N/A')}",
            f"• **Top Processes**: {metrics.get('Top Processes', 'N/A')}",
            f"• **API Keys**: {metrics.get('API Keys', 'N/A')}",
            f"• **Anime Subsystem**: {metrics.get('Anime Subsystem', 'N/A')}",
            f"• **Audio Inputs**: {metrics.get('Audio Inputs', 'N/A')}",
            "\n**Audit Findings & Status:**"
        ]
        for f in findings:
            lines.append(f"• {f}")

        content = "\n".join(lines)
        if player:
            player.write_log(f"🖥️ System Audit: {'Healthy' if audit.get('is_healthy') else 'Attention Needed'}")
            player.show_content("System Health & Forensic Audit", content)

        finding_summary = findings[0] if findings else "All systems fully operational."
        return f"System audit complete. Memory is {metrics.get('Memory')}. Disk is {metrics.get('Disk')}. {finding_summary}"

    elif mode in ["large_files", "large", "big"]:
        min_mb = float(parameters.get("min_size_mb", 100.0))
        limit = int(parameters.get("limit", 10))
        large_files = analyzer.find_large_files(min_size_mb=min_mb, limit=limit)

        if not large_files:
            return f"No files larger than {min_mb} MB found in safe user directories."

        lines = [f"📂 **Large Files (> {min_mb} MB):**"]
        for idx, lf in enumerate(large_files, start=1):
            lines.append(f"{idx}. **{lf['name']}** — {lf['size_mb']} MB (`{lf['path']}`)")
        content = "\n".join(lines)

        if player:
            player.write_log(f"📂 Found {len(large_files)} large files (> {min_mb}MB)")
            player.show_content("Large Files Discovery", content)

        return f"Found {len(large_files)} files exceeding {min_mb} MB. Largest is {large_files[0]['name']} at {large_files[0]['size_mb']} MB."

    elif mode in ["duplicates", "dup"]:
        dups = analyzer.find_duplicate_files(limit=8)
        if not dups:
            return "No duplicate files found in safe scanning directories."

        lines = ["📂 **Duplicate Files Detected:**"]
        for idx, d in enumerate(dups, start=1):
            lines.append(f"{idx}. **Size:** {d['size_mb']} MB (SHA256: `{d['sha256']}`):")
            for p in d['paths']:
                lines.append(f"   - `{p}`")
        content = "\n".join(lines)

        if player:
            player.write_log(f"📂 Found {len(dups)} duplicate file clusters")
            player.show_content("Duplicate Files", content)

        return f"Identified {len(dups)} duplicate file clusters in scan locations."

    elif mode in ["dotfiles", "hidden"]:
        dots = analyzer.find_hidden_dotfiles(limit=15)
        if not dots:
            return "No unexpected dotfiles found."

        lines = ["📂 **Hidden Dotfiles Discovered:**"]
        for idx, df in enumerate(dots, start=1):
            tag = "[DIR]" if df["is_dir"] else f"[{df['size_kb']} KB]"
            lines.append(f"{idx}. `{df['name']}` {tag} — `{df['path']}`")
        content = "\n".join(lines)

        if player:
            player.write_log(f"📂 Found {len(dots)} hidden dotfiles")
            player.show_content("Hidden Dotfiles", content)

        return f"Discovered {len(dots)} hidden dotfiles and configuration directories."

    elif mode in ["processes", "procs", "ram"]:
        procs = analyzer.get_heavy_processes(limit=8)
        lines = ["⚙️ **Top Memory-Consuming Processes:**"]
        for idx, p in enumerate(procs, start=1):
            lines.append(f"{idx}. **{p['name']}** (PID {p['pid']}) — {p['memory_mb']} MB RAM, {p['cpu_pct']}% CPU")
        content = "\n".join(lines)

        if player:
            player.write_log("⚙️ Heavy processes inspected")
            player.show_content("Process Diagnostics", content)

        top = procs[0]
        return f"Top RAM consumer is {top['name']} using {top['memory_mb']} MB memory."

    return f"Unknown scan mode '{mode}'. Available modes: audit, large_files, duplicates, dotfiles, processes."


TOOL = {
    "name": "mac_deep_scan",
    "description": (
        "Read-only macOS deep analyzer: comprehensive system health audit, large file discovery (>100MB), "
        "duplicate detection via SHA-256, hidden dotfile inspection, and heavy RAM process monitoring."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "enum": ["audit", "large_files", "duplicates", "dotfiles", "processes"],
                "description": "Diagnostic mode to execute"
            },
            "query": {
                "type": "STRING",
                "description": "Natural language query describing what to scan for"
            },
            "min_size_mb": {
                "type": "NUMBER",
                "description": "Minimum file size in megabytes for large file search (default 100)"
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of items to return"
            }
        }
    },
    "handler": mac_scan_handler
}
