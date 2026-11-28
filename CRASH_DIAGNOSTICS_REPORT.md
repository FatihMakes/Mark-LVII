# JARVIS H3.2 — Crash Diagnostics & Service Reliability Report

---

## 1. Reliability Architecture (`core/crash_guard.py`)

To prevent process instability and infinite error loops from degrading the user experience on macOS, JARVIS H3.2 introduces a centralized reliability layer:

```
[System / Thread Execution]
            │
            ├── Global sys.excepthook
            ├── Threading excepthook (Python 3.8+)
            └── @crash_guarded(component_name, fallback)
                        │
                        ▼
            core/crash_guard.py
     ┌──────────────────┴──────────────────┐
     ▼                                     ▼
[Rate Limiter]                      [Structured Logger]
- Sliding 60s crash window          - Appends to memory/crash_reports.jsonl
- Max 3 crashes/minute              - Captures RAM/CPU telemetry
- Throttles crash-looping tasks     - Full stack trace & exception class
```

---

## 2. Key Reliability Features

1. **Global Unhandled Exception Trapping:**
   Captures both main thread crashes (`sys.excepthook`) and worker thread crashes (`threading.excepthook`), logging them immediately without crashing the application.
2. **Crash-Loop Rate Limiting:**
   Maintains a sliding 60-second window of crash timestamps per component. If a component (e.g. an unstable external plugin) fails more than 3 times within 60 seconds, `CrashGuard` automatically throttles execution, logs a `CRITICAL` alert, and returns a safe fallback.
3. **Supervised Worker Decorator:**
   Critical tasks wrapped with `@guard(component_name, fallback_return)` trap exceptions cleanly and preserve system uptime.
4. **Clean Graceful Shutdown:**
   Registers signal handlers for `SIGTERM` and `SIGINT`, plus an `atexit` cleanup hook, executing all registered shutdown callbacks (closing SQLite connections, terminating child processes, flushing logs).

---

## 3. Verification & Test Evidence

Validated in `tests/test_h3_2_crash_recovery.py`:
- `test_01_crash_recording`: Confirmed structured JSON logging with error type, message, telemetry, and timestamp.
- `test_02_crash_loop_detection_and_rate_limiting`: Confirmed detection of repeated failures and automatic rate limiting.
- `test_03_supervised_decorator`: Confirmed that protected workers catch exceptions and bypass faulty functions when throttled.
- `test_04_shutdown_hooks_execution`: Confirmed shutdown handlers execute sequentially on termination.
