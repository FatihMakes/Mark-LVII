# Crash Prevention, Threading & Application Stability Report

**System:** JARVIS Mark-LVII v57.3 Stability Watchdog & Thread Safety  
**Platform:** macOS Darwin ARM64 (Apple Silicon)  
**Status:** **PASSED & RESILIENT**

---

## 1. Compliance with Threading Invariants (`AGENTS.md`)

In strict adherence to `AGENTS.md`:
- **Rule**: Code in `actions/` and `plugins/` runs on worker threads and **must NEVER create or touch a Qt widget**.
- All new actions created in H3.3 (`actions/whatsapp_automation.py`, `actions/instagram_control.py`, `actions/browser_control.py`, `actions/media_search.py`) communicate exclusively through thread-safe methods on `player`:
  - `player.write_log(text)`
  - `player.show_content(title, markdown_text)`
- No Qt widgets are instantiated on background threads.

## 2. GUI Theme Token Audit

Fixed theme constant bugs in `gui/window.py` and `gui/overlays.py`:
- Replaced invalid references (`C.PANEL_BG`, `C.PANEL_BG_HOVER`, `C.AMBER`) with valid theme tokens (`C.PANEL2`, `C.HOVER`, `C.ACC`, `C.PRI`).
- Fixed `AttributeError: 'NoneType' object has no attribute 'get'` in `IdentityAuthOverlay` by providing fallback default profile dictionaries.

## 3. Subprocess & Watchdog Handling
- All `subprocess.run` and `subprocess.Popen` invocations include explicit timeouts (3s to 25s) to prevent frozen processes.
- AppleScript execution via `osascript` catches errors without throwing unhandled exceptions.
- The self-healing crash recovery engine (`core/self_healing.py` / `actions/self_repair.py`) monitors subprocess health, limits crash loops (2 crashes within 60s triggers rate limiting and automatic fallback), and preserves core system responsiveness.
