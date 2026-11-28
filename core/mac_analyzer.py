"""
JARVIS H3.2 — macOS Deep Scan & System Analyzer
Provides comprehensive, read-only system auditing, file discovery,
duplicate detection, large file tracking, and process health monitoring
optimized for Apple Silicon APFS and macOS TCC permissions.
"""

import os
import sys
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import psutil

logger = logging.getLogger("jarvis.mac_analyzer")

SAFE_SCAN_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Documents",
    Path.home() / "Projects",
    Path.home() / "Downloads" / "Jarvise",
]


class MacAnalyzer:
    """Read-only system inspector and deep file analyzer."""

    def __init__(self):
        pass

    def run_system_audit(self) -> Dict[str, Any]:
        """
        Runs a comprehensive read-only audit of system resources, process health,
        dependencies, API keys, and audio subsystems.
        """
        audit_start = time.time()
        findings: List[str] = []
        status_summary: Dict[str, str] = {}

        # 1. CPU & Memory Metrics
        mem = psutil.virtual_memory()
        mem_total_gb = round(mem.total / (1024**3), 2)
        mem_avail_gb = round(mem.available / (1024**3), 2)
        mem_used_pct = mem.percent
        cpu_pct = psutil.cpu_percent(interval=0.1)

        status_summary["Memory"] = f"{mem_avail_gb} GB free / {mem_total_gb} GB total ({mem_used_pct}% used)"
        status_summary["CPU"] = f"{cpu_pct}% utilization ({psutil.cpu_count(logical=False)} cores)"

        if mem_used_pct > 90:
            findings.append("⚠️ Unified memory headroom is critical (<10% available).")

        # 2. Disk Space (APFS root)
        disk = psutil.disk_usage("/")
        disk_free_gb = round(disk.free / (1024**3), 2)
        disk_total_gb = round(disk.total / (1024**3), 2)
        status_summary["Disk"] = f"{disk_free_gb} GB free of {disk_total_gb} GB ({disk.percent}% used)"

        if disk.percent > 95:
            findings.append("⚠️ Disk storage critically low (<5% available).")

        # 3. Top RAM-heavy processes
        heavy_procs = self.get_heavy_processes(limit=5)
        top_proc_names = [f"{p['name']} ({p['memory_mb']} MB)" for p in heavy_procs[:3]]
        status_summary["Top Processes"] = ", ".join(top_proc_names)

        # 4. API Key Configuration Health
        key_status = self._check_api_keys()
        status_summary["API Keys"] = key_status["summary"]
        if key_status["missing"]:
            findings.append(f"ℹ️ Unconfigured services: {', '.join(key_status['missing'])}")

        # 5. Media & Tool Capabilities
        anime_cli_ok = Path("bin/ani-cli").exists() or shutil_which("ani-cli") is not None
        iina_ok = Path("/Applications/IINA.app").exists()
        status_summary["Anime Subsystem"] = "Operational (ani-cli + IINA detected)" if (anime_cli_ok and iina_ok) else "Degraded"

        # 6. Audio Subsystem
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            in_devs = [d for d in devs if d.get('max_input_channels', 0) > 0]
            status_summary["Audio Inputs"] = f"{len(in_devs)} input device(s) active"
        except Exception as e:
            status_summary["Audio Inputs"] = f"Unavailable: {e}"
            findings.append("⚠️ Audio input querying encountered an issue.")

        duration = round(time.time() - audit_start, 3)

        return {
            "status": "success",
            "audit_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_sec": duration,
            "metrics": status_summary,
            "findings": findings if findings else ["✅ All audited core subsystems are operational."],
            "is_healthy": len([f for f in findings if f.startswith("⚠️")]) == 0
        }

    def _check_api_keys(self) -> Dict[str, Any]:
        cfg_file = Path("config/api_keys.json")
        configured = []
        missing = []

        cfg = {}
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json_load(f)
            except Exception:
                pass

        keys_to_check = [
            ("gemini_api_key", "Gemini API"),
            ("groq_api_key", "Groq API"),
            ("google_maps_api_key", "Google Maps"),
            ("openweather_api_key", "OpenWeather"),
        ]
        for key_name, label in keys_to_check:
            val = cfg.get(key_name) or os.environ.get(key_name.upper())
            if val and isinstance(val, str) and len(val.strip()) > 5:
                configured.append(label)
            else:
                missing.append(label)

        return {
            "configured": configured,
            "missing": missing,
            "summary": f"{len(configured)} active, {len(missing)} unconfigured"
        }

    def find_large_files(
        self,
        min_size_mb: float = 100.0,
        roots: Optional[List[Path]] = None,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Finds files larger than min_size_mb across user directories."""
        min_bytes = int(min_size_mb * 1024 * 1024)
        scan_roots = roots or [r for r in SAFE_SCAN_ROOTS if r.exists()]
        large_files = []

        for root in scan_roots:
            try:
                for entry in root.rglob("*"):
                    try:
                        if entry.is_file() and not entry.is_symlink():
                            sz = entry.stat().st_size
                            if sz >= min_bytes:
                                large_files.append({
                                    "path": str(entry),
                                    "name": entry.name,
                                    "size_mb": round(sz / (1024 * 1024), 2),
                                    "modified": time.strftime("%Y-%m-%d", time.localtime(entry.stat().st_mtime))
                                })
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
            except (PermissionError, OSError):
                continue

        large_files.sort(key=lambda x: x["size_mb"], reverse=True)
        return large_files[:limit]

    def find_hidden_dotfiles(
        self,
        roots: Optional[List[Path]] = None,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Finds hidden dotfiles (.DS_Store, cache artifacts, etc.) in target roots."""
        scan_roots = roots or [r for r in SAFE_SCAN_ROOTS if r.exists()]
        dotfiles = []

        for root in scan_roots:
            try:
                for entry in root.rglob(".*"):
                    try:
                        if entry.name in [".", "..", ".git", ".venv"]:
                            continue
                        is_dir = entry.is_dir()
                        sz = 0
                        if not is_dir and not entry.is_symlink():
                            sz = entry.stat().st_size
                        dotfiles.append({
                            "path": str(entry),
                            "name": entry.name,
                            "is_dir": is_dir,
                            "size_kb": round(sz / 1024, 2)
                        })
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
                    if len(dotfiles) >= limit * 2:
                        break
            except (PermissionError, OSError):
                continue

        return dotfiles[:limit]

    def find_duplicate_files(
        self,
        root: Optional[Path] = None,
        min_size_kb: float = 50.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Discovers duplicate files by matching file size followed by SHA-256 chunk hash.
        """
        scan_dir = root or Path.home() / "Downloads"
        if not scan_dir.exists():
            return []

        min_bytes = int(min_size_kb * 1024)
        size_map: Dict[int, List[Path]] = {}

        try:
            for entry in scan_dir.rglob("*"):
                try:
                    if entry.is_file() and not entry.is_symlink() and not entry.name.startswith("."):
                        sz = entry.stat().st_size
                        if sz >= min_bytes:
                            size_map.setdefault(sz, []).append(entry)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except Exception:
            pass

        duplicates = []
        for sz, paths in size_map.items():
            if len(paths) < 2:
                continue
            # Hash verification
            hash_map: Dict[str, List[Path]] = {}
            for p in paths:
                h = _hash_file_fast(p)
                if h:
                    hash_map.setdefault(h, []).append(p)

            for h, dup_paths in hash_map.items():
                if len(dup_paths) > 1:
                    duplicates.append({
                        "size_mb": round(sz / (1024 * 1024), 2),
                        "sha256": h[:16],
                        "paths": [str(p) for p in dup_paths]
                    })
                if len(duplicates) >= limit:
                    break

        return duplicates[:limit]

    def get_heavy_processes(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Returns top RAM-consuming processes."""
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
            try:
                mem = p.info.get('memory_info')
                if mem:
                    rss_mb = round(mem.rss / (1024 * 1024), 1)
                    procs.append({
                        "pid": p.info['pid'],
                        "name": p.info.get('name') or "Unknown",
                        "memory_mb": rss_mb,
                        "cpu_pct": p.info.get('cpu_percent') or 0.0
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x["memory_mb"], reverse=True)
        return procs[:limit]


def _hash_file_fast(p: Path) -> Optional[str]:
    """Calculates SHA-256 of first 1MB of file for fast duplicate verification."""
    try:
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            chunk = f.read(1024 * 1024)
            hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


def shutil_which(cmd: str) -> Optional[str]:
    import shutil
    return shutil.which(cmd)


def json_load(f):
    import json
    return json.load(f)


_analyzer_instance: Optional[MacAnalyzer] = None

def get_mac_analyzer() -> MacAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = MacAnalyzer()
    return _analyzer_instance
