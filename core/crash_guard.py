"""
JARVIS H3.2 — Crash Guard & Reliability Monitor
Centralized exception handling, crash loop detection, rate limiting,
supervised execution, and graceful shutdown management.
"""

from __future__ import annotations

import os
import sys
import time
import json
import signal
import atexit
import logging
import threading
import traceback
from pathlib import Path
from typing import Callable, Any, Dict, List, Optional
import psutil

logger = logging.getLogger("jarvis.crash_guard")

MEMORY_DIR = Path("memory")
CRASH_LOG = MEMORY_DIR / "crash_reports.jsonl"
SHUTDOWN_HOOKS: List[Callable[[], None]] = []


class CrashGuard:
    """Centralized reliability and exception supervisor."""

    def __init__(self, max_crashes_per_minute: int = 3):
        self.max_crashes = max_crashes_per_minute
        self._crash_timestamps: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._installed = False

    def install_global_hooks(self):
        """Attaches system and thread unhandled exception hooks."""
        if self._installed:
            return
        self._installed = True

        # System excepthook
        orig_excepthook = sys.excepthook

        def _custom_excepthook(exc_type, exc_value, exc_tb):
            self.record_crash("GlobalSystem", exc_value, exc_tb)
            orig_excepthook(exc_type, exc_value, exc_tb)

        sys.excepthook = _custom_excepthook

        # Threading excepthook (Python 3.8+)
        if hasattr(threading, "excepthook"):
            orig_thread_hook = threading.excepthook

            def _custom_thread_hook(args):
                self.record_crash(f"Thread:{args.thread.name}", args.exc_value, args.exc_traceback)
                orig_thread_hook(args)

            threading.excepthook = _custom_thread_hook

        # Signal handlers
        try:
            signal.signal(signal.SIGTERM, self._handle_termination_signal)
            signal.signal(signal.SIGINT, self._handle_termination_signal)
        except (ValueError, OSError):
            pass

        atexit.register(self.execute_clean_shutdown)
        logger.info("CrashGuard reliability hooks successfully installed.")

    def record_crash(self, component: str, exc: Optional[BaseException], tb=None) -> Dict[str, Any]:
        """Records structured crash data with system telemetry."""
        with self._lock:
            now = time.time()
            ts_list = self._crash_timestamps.setdefault(component, [])
            # Purge entries older than 60 seconds
            ts_list = [t for t in ts_list if now - t < 60.0]
            ts_list.append(now)
            self._crash_timestamps[component] = ts_list

            is_loop = len(ts_list) >= self.max_crashes

            # System telemetry snapshot
            mem = psutil.virtual_memory()
            telemetry = {
                "ram_percent": mem.percent,
                "ram_free_mb": round(mem.available / (1024 * 1024), 1),
                "cpu_percent": psutil.cpu_percent(interval=None),
                "active_threads": threading.active_count()
            }

            stack = "".join(traceback.format_exception(type(exc), exc, tb)) if exc else "No traceback"

            record = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "component": component,
                "error_type": type(exc).__name__ if exc else "Unknown",
                "error_message": str(exc) if exc else "No message",
                "crash_count_last_minute": len(ts_list),
                "is_crash_loop": is_loop,
                "telemetry": telemetry,
                "traceback": stack
            }

            try:
                MEMORY_DIR.mkdir(parents=True, exist_ok=True)
                with open(CRASH_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception as e:
                logger.error(f"Failed to write to crash log: {e}")

            if is_loop:
                logger.critical(f"CRASH LOOP DETECTED on {component} ({len(ts_list)} crashes in 60s). Rate limiting.")

            return record

    def is_rate_limited(self, component: str) -> bool:
        """Returns True if the component is in a crash loop and should be throttled."""
        with self._lock:
            now = time.time()
            ts_list = self._crash_timestamps.get(component, [])
            active = [t for t in ts_list if now - t < 60.0]
            return len(active) >= self.max_crashes

    def guard(self, component_name: str, fallback_return: Any = None):
        """Decorator to safely supervise critical functions."""
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                if self.is_rate_limited(component_name):
                    logger.warning(f"Component '{component_name}' is rate-limited due to repeated crashes. Returning fallback.")
                    return fallback_return

                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    self.record_crash(component_name, exc, sys.exc_info()[2])
                    return fallback_return
            return wrapper
        return decorator

    def register_shutdown_hook(self, hook: Callable[[], None]):
        """Registers a callback to execute upon graceful shutdown."""
        SHUTDOWN_HOOKS.append(hook)

    def _handle_termination_signal(self, signum, frame):
        logger.info(f"Received shutdown signal ({signum}). Initiating clean termination.")
        self.execute_clean_shutdown()
        sys.exit(0)

    def execute_clean_shutdown(self):
        """Executes all registered cleanup hooks."""
        logger.info("Executing JARVIS clean shutdown sequence...")
        for hook in SHUTDOWN_HOOKS:
            try:
                hook()
            except Exception as e:
                logger.error(f"Error executing shutdown hook: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Returns statistics on past crashes."""
        total_crashes = 0
        recent_crashes = []
        if CRASH_LOG.exists():
            try:
                with open(CRASH_LOG, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            total_crashes += 1
                            try:
                                recent_crashes.append(json.loads(line))
                            except Exception:
                                pass
            except Exception:
                pass

        return {
            "total_crashes": total_crashes,
            "recent_crashes": recent_crashes[-5:],
            "active_rate_limits": [k for k, v in self._crash_timestamps.items() if self.is_rate_limited(k)]
        }


# Global singleton
_crash_guard_instance: Optional[CrashGuard] = None

def get_crash_guard() -> CrashGuard:
    global _crash_guard_instance
    if _crash_guard_instance is None:
        _crash_guard_instance = CrashGuard()
    return _crash_guard_instance
