# JARVIS H3.1 — Known Limitations & System Requirements
**Author:** Aman Kumar ([@iamTechieAman](https://github.com/iamTechieAman))  
**Document Purpose:** Transparent disclosure of hardware boundaries, operating system permissions, and environment expectations.

---

## 1. Hardware & Operating System Prerequisites

### 1.1 Apple Silicon Mac (macOS 12.0 Monterey or Later)
* **Unified Memory (RAM):**
  * **8 GB RAM:** Supports lightweight 3.8B - 7B Q4_K_M quantized local models (`phi3.5`, `qwen2.5:7b-instruct-q4_K_M`).
  * **16 GB RAM or Higher:** Recommended for 8B - 14B models (`llama3.1:8b`, `deepseek-r1:7b`) with extended context windows (32k - 128k tokens).
* **OS Permissions Required:**
  * **Microphone Access:** Prompted on first launch; required for voice stream and multi-speaker diarization.
  * **Accessibility Permissions:** Required under *System Settings > Privacy & Security > Accessibility* for automated keystroke injection and frontmost window interaction.
  * **Screen Recording Permissions:** Required for `actions/screen_vision.py` to capture active desktop displays.

### 1.2 Android Companion Device (Android 10.0+ / API 29+)
* **Local Network Connectivity:** The Android phone and host Mac must reside on the same Wi-Fi subnet or connect over an ad-hoc hotspot / USB reverse tethering.
* **Android System Permissions:**
  * `CAMERA`: Required for flashlight torch toggle.
  * `WRITE_SETTINGS`: Required for display brightness adjustments.
  * `MODIFY_AUDIO_SETTINGS`: Required for media volume control.
  * `NOTIFICATION_LISTENER`: Required for reading unread WhatsApp messages aloud.

---

## 2. Operational & Model Boundaries

### 2.1 Multi-Speaker Overlap Handling
* In environments with extreme acoustic reverberation (e.g., tiled rooms with echoes), secondary harmonics may momentarily resemble competing voices. The engine includes an octave-ratio filter ($ratio \neq 2.0, 3.0 \pm 0.15$) to prevent pitch-halving errors.
* When overlap confidence exceeds 40%, the system deliberately refuses to execute commands, requiring the speaker to repeat. This is a deliberate security guard, not a failure.

### 2.2 WhatsApp Automation Delivery
* In compliance with WhatsApp terms and end-to-end encryption protocols, messages are routed via official URI schemes (`https://api.whatsapp.com/send`) or through the companion intent bridge.
* Direct background socket injection without user confirmation is prohibited to protect against account bans and accidental dispatches.

### 2.3 Anti-Theft Siren Guard
* Power detachment detection on macOS monitors `pmset -g batt` state transitions from AC to Battery.
* If testing on a desktop Mac (Mac mini, Mac Studio, Mac Pro) with no battery, power disconnect monitoring requires an external UPS telemetry signal. On MacBooks (Air/Pro), it functions instantly upon cable detachment.

---

## 3. Recommended Environment Configurations

* **Ollama Local Runner:** Install Ollama (`brew install ollama` or download from [ollama.com](https://ollama.com)) and run `ollama serve`. Pull the default model: `ollama pull qwen2.5:7b-instruct-q4_K_M`.
* **Local Voice Pipeline:** Set piper voice path in `config/api_keys.json` or use native macOS text-to-speech.
