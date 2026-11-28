# JARVIS H3.1 — Architectural Upgrade & Capability Report
**Release Version:** Mark-LVII v57.1 (H3.1)  
**Author / Lead Engineer:** Aman Kumar ([@iamTechieAman](https://github.com/iamTechieAman))  
**Target Architecture:** Apple Silicon Mac (M-Series Unified Memory) + Android Companion  
**Verification Status:** 139 Tests Passed (100% Pass Rate: 99 Provider Tests + 17 H3 Tests + 23 H3.1 Tests)

---

## 1. Executive Summary

JARVIS H3.1 represents a massive leap from a single-speaker voice assistant into an **Autonomous, Multi-Speaker Aware, Edge-Private Personal AI Operating System**. Built on top of the foundation established in H3.0, H3.1 integrates advanced dual-pitch autocorrelation and FFT diarization, an uncensored local on-device LLM engine adapted from Reference A (*Uncensored-Local-AI-Multiplatform*), a multi-provider router with 7 personality profiles adapted from Reference B (*7API uncensored-ai-api*), a native Android Companion Hardware Control Gateway, WhatsApp end-to-end automation with mandatory explicit confirmation guards, and an Anti-Theft Siren Guard.

Every single existing feature—including the Voice HUD, 3D Reactor Core, Perplexity-inspired sidebar and workspace, Telegram Remote, Torvis agent tools, and all 40+ actions—has been strictly preserved and augmented with non-destructive, thread-safe extensions.

---

## 2. Reference Repository Studies & Architectural Adaptations

### 2.1 Reference A: Uncensored Local AI Multiplatform (`ref_a`)
* **Repository Analysis:** Examined GGUF on-device model execution, memory buffer headroom allocation, real-time token generation velocity metering, abort controller events (`stop_generation`), and native mobile companion bridge protocols.
* **Integrated Implementation:**
  * Created `core/local_ai_engine.py`: Employs `psutil` Apple Silicon unified RAM headroom verification to prevent swap thrashing or system freezes before model weights are loaded.
  * Real-time Token Generation Meter: Tracks token-per-second (TPS) velocity across streaming inference.
  * Deterministic Stop Interrupt: Implemented `stop_generation()` via thread-safe `threading.Event`, allowing immediate voice-command cancellation of local text synthesis within 100ms.
  * Local GGUF/Ollama Model Catalog: Catalogues installed local models with quantization profiles (Q4_K_M, Q8_0) and context window budgets.

### 2.2 Reference B: 7API Uncensored AI API (`ref_b`)
* **Repository Analysis:** Investigated multi-provider API gateways, dynamic routing fallback ladders, Anthropic/OpenAI schema adapters, personality profile prompt templates, and streaming failovers.
* **Integrated Implementation:**
  * Created `core/model_router.py`: Dual-mode orchestration engine:
    1. `LOCAL_PRIVATE_MODE` (Default): 100% on-device processing via Ollama/GGUF, strict zero-network packet egress.
    2. `CLOUD_ASSISTED_MODE`: Transparent provider routing across Gemini, 7API, OpenAI, and Anthropic with visible user telemetry.
  * 7 Tuned Personality Profiles:
    * `GENERAL_ASSISTANT`: Balanced, courteous, proactive.
    * `ADVANCED_REASONING`: Deep analytical chain-of-thought.
    * `CODING_EXPERT`: Strict, minimal, dependency-conscious software engineering.
    * `RESEARCH_EXPERT`: Fact-checking, citations, academic synthesis.
    * `CREATIVE_ASSISTANT`: Narrative, visual, stylistic composition.
    * `UNRESTRICTED_CREATIVE`: Completely unfiltered brainstorming and creative design.
    * `LOCAL_PRIVACY`: Minimalist local responses with no cloud dependencies.

---

## 3. Core H3.1 Functional Upgrades

### 3.1 Multi-Speaker Diarization & Active Speaker Lock
* **Hybrid Dual-Pitch Analysis:** Employs normalized autocorrelation paired with FFT spectral decomposition across human vocal ranges (75 Hz - 400 Hz) with octave-error mitigation to distinguish multiple speakers talking at once.
* **Overlap Rejection Invariant:** When two distinct speakers speak simultaneously, JARVIS refuses to guess:
  `"Multiple speakers detected. Please repeat your command."`
* **Active Speaker Lock (Owner Priority Mode):** Once the owner begins a session, ambient chatter (<25% energy) and guest voices are ignored for an 8-second window.
* **Acoustic Echo Cancellation (AEC):** Tracks TTS playback status (`is_tts_playback_active`) to discard microphone feedback, preventing self-trigger loops.

### 3.2 Android Companion & Hardware Gateway
* **Architecture:** Zero-cloud, local WebSocket/HTTP hardware broker in `core/companion_gateway.py` paired with Kotlin Android service (`android_companion/src/HardwareControlBridge.kt`).
* **Cryptographic Pairing:** 300-second expiring HMAC-SHA256 pairing tokens (`PAIR_...`) with QR code enrollment.
* **Hardware Operations Dispatched:**
  * Flashlight toggle (`TORCH_ON` / `TORCH_OFF`)
  * Media volume & display brightness adjustments [0-100%]
  * Battery telemetry monitoring (percentage + charging state)
  * Hardware application launching (WhatsApp, Camera, Maps)
  * System Settings intents (Wi-Fi, Bluetooth, Hotspot)

### 3.3 Complete WhatsApp Automation
* **Safety Invariant:** Composing a WhatsApp message NEVER dispatches immediately. A structured confirmation review card is displayed on screen and held in `_PENDING_DISPATCH` until the user explicitly speaks `"Confirm send <draft_id>"`.
* **Capabilities:**
  * Contact disambiguation with fuzzy matching and relationship hierarchy.
  * Unread notification read-aloud.
  * Hands-Free Voice Calling via companion bridge or URI scheme.
  * Hands-Free Driving Mode toggle.

### 3.4 Anti-Theft Siren Guard
* **State Machine:** `DISARMED` -> `ARMING` (10s countdown grace period) -> `ARMED` -> `TRIGGERED`.
* **Sensor Detection:** Triggers upon power/charger disconnect or unauthorized motion.
* **Alarm Response:** Sets companion volume to 100%, triggers local audio alarm (`afplay`), and logs incidents into `memory/theft_incidents.jsonl`.
* **Disarm Protocol:** Silences sirens only upon receipt of the owner's master PIN (`1170`) or authenticated owner biometric voice.

### 3.5 Privacy Lock Kill Switch
* **Trigger:** Say *"JARVIS, Privacy Lock"* or click the Privacy Center toggle.
* **Action:** Immediately terminates cloud streaming, switches system mode to `LOCAL_PRIVATE_MODE`, and guarantees zero external packet transmission.

---

## 4. UI/UX & Navigation Extensions

All overlays are styled with the official JARVIS theme palette (`gui/theme.py`) and typography (`gui/style.py`), running entirely off the Qt main thread via `MainWindow` signals and `JarvisUI` thread-safe methods:
* **Multi-Speaker Overlay:** Displays real-time pitch telemetry, overlap indicators, active speaker lock status, and address mode configuration.
* **Local AI Overlay:** Displays RAM headroom, TPS meters, stop generation button, and model switching dropdown.
* **Android Gateway Overlay:** Displays paired devices, battery levels, torch toggles, and new QR pairing buttons.
* **Privacy Center Overlay:** Displays operational mode badge, kill switch toggle, and zero-egress audit log.
* **Sidebar Integration:** Added collapsible navigation buttons in `PerplexitySidebar` (`gui/perplexity_nav.py`) for all new panels.

---

## 5. Test & Quality Assurance Summary

* **providers/_tests.py:** 99 / 99 PASSED (0 failures)
* **tests/test_h3_suite.py:** 17 / 17 PASSED (0 failures)
* **tests/test_h3_1_suite.py:** 23 / 23 PASSED (0 failures)
* **Combined Test Suite Total:** **139 / 139 PASSED (100% Pass Rate)**
* **macOS Artifacts:**
  * Official App: `/Applications/Jarvis.app`
  * DMG Installer: `~/Desktop/Jarvis-Mark-LVII.dmg`
