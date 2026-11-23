# JARVIS H3.2 — UI Telemetry & Visual State Audit Report

---

## 1. Audit Scope & Ground Truth Verification

The visual interface of JARVIS consists of the PyQt6 desktop HUD (`gui/window.py`, `gui/hud.py`, `gui/widgets.py`, `gui/perplexity_workspace.py`), side drawers, and the real-time telemetry panel.

In prior iterations, certain visual indicators operated statically or displayed misleading states:
- **Header Engine Button:** Initialized to `"● GEMINI LIVE"` and never dynamically updated when the user switched to Local Ollama mode or when network was disconnected.
- **Initial Microphone Indicator:** Showed `"LISTENING"` on startup even when the input microphone was muted.
- **Thread Safety Violations:** Risk of background threads instantiating Qt widgets directly.

---

## 2. Engineering Corrections Applied

### A. Dynamic Engine Pill (`_header_engine_btn`)
Updated `_refresh_identity_rows` in `gui/window.py`:
- Reads live provider state (`get_provider_mode()`).
- In Local Mode (Ollama, LM Studio): Displays `● LOCAL OLLAMA` or `● LOCAL VLLM` in **amber** (`C.AMBER`).
- In Cloud Gemini Mode: Displays `● GEMINI LIVE` in **green** (`C.GREEN`).
- Updates immediately whenever the user switches engines in the Providers panel.

### B. Accurate Microphone State Initialization
- In `gui/window.py`, line 3571: Startup sequence now explicitly inspects `self._muted`.
- If muted: Applies `MUTED` (muted red indicator).
- If unmuted: Applies `LISTENING` (active cyan/green pulse).

### C. Strict Thread-Safety Compliance (`AGENTS.md`)
- All tools in `actions/` and `plugins/` strictly interact with the UI through the thread-safe proxy `player` (`JarvisUI`), emitting PyQt signals (`_write_log_sig`, `_content_sig`, `_video_sig`).
- Zero Qt widgets are created or mutated on worker threads.
