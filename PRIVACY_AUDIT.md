# JARVIS H3.1 — Security & Privacy Audit Report
**Author:** Aman Kumar ([@iamTechieAman](https://github.com/iamTechieAman))  
**Audit Scope:** On-Device Processing, Network Egress, Voice Storage, and Privacy Kill Switch  
**Status:** FULLY COMPLIANT (Zero External Leakage in Local Private Mode)

---

## 1. Privacy Directives & Compliance Standard

JARVIS H3.1 is engineered according to the **Local-First, Edge-Private AI Manifesto**:
* What the owner speaks or types stays on their own hardware.
* Voice samples, biometric embeddings, and conversation histories are never transmitted to corporate data centers.
* External cloud providers are blocked by default and accessible only under explicit, transparent user consent.

---

## 2. Privacy Kill Switch ("JARVIS, Privacy Lock")

### 2.1 Kill Switch Protocol
* **Voice Command:** Say *"JARVIS, Privacy Lock"* (or *"engage privacy lock"*, *"lock privacy"*).
* **HUD Action:** Click the Lock button inside the `PrivacyCenterOverlay`.
* **Immediate System Response:**
  1. Sets global privacy lock state: `is_privacy_locked() == True`.
  2. Forces `ModelRouter` mode to `OperationMode.LOCAL_PRIVATE`.
  3. Aborts all active HTTP connections and streaming sockets to external providers (Gemini, 7API, OpenAI, Anthropic).
  4. Flushes temporary audio buffers from RAM.
  5. Displays a prominent green locked badge on the HUD: `🔒 PRIVACY LOCK: ZERO EXTERNAL EGRESS`.

### 2.2 Reversal Protocol
* To unlock, the owner must state: *"JARVIS, release privacy lock"* or toggle it from the settings panel.

---

## 3. Network Egress Audit

### 3.1 Local Private Mode
* All LLM inference queries are directed strictly to `http://127.0.0.1:11434` (Ollama) or local GGUF engine.
* Speech recognition runs via local Whisper / Sherpa-ONNX model weights.
* Text-to-speech runs via local Piper engine or native macOS speech synthesizer.
* Netstat and packet inspection verify zero outgoing packets to external IP addresses.

### 3.2 Cloud-Assisted Mode (When Authorized by Owner)
* When the owner deliberately switches to `CLOUD_ASSISTED_MODE`:
  * Telemetry is visibly displayed on screen: provider name, model identifier, and prompt size.
  * API keys are loaded securely from `config/api_keys.json` through `config_manager.py` (never logged to terminal or disk).
  * Streaming responses are stripped of reasoning scratchpads and internal tokens before playback.

---

## 4. Biometric Voice Sample Protection

* Raw audio recordings captured during owner enrollment are stored locally in `memory/voices/`.
* Cloned voice synthesis models run on-device.
* Voice enrollment requires explicit spoken or written consent verification before synthesis is allowed.
* Biometric embedding files (`memory/owner_voice_model.json`) are secured with standard OS file permission masks.
