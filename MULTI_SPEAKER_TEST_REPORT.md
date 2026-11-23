# JARVIS H3.1 — Multi-Speaker Intelligence & Diarization Report
**Author:** Aman Kumar ([@iamTechieAman](https://github.com/iamTechieAman))  
**Component:** `core/speaker_intelligence.py` & `actions/speaker_manager.py`  
**Status:** FULLY VERIFIED (7/7 Dedicated Unit & Biometric Tests Passed)

---

## 1. Objectives & Challenges

Single-microphone home and office environments present severe acoustic challenges for voice AI systems:
1. **Simultaneous Speech (Cross-Talk):** Multiple people speaking at once frequently leads models to hallucinate or execute commands unintended by the owner.
2. **Background Chatter & Ambient Noise:** Nearby conversations, television audio, and cafeteria banter can falsely trigger wake words and action pipelines.
3. **Acoustic Feedback (Echo Loops):** The assistant's own loudspeaker playback gets picked up by the microphone, causing JARVIS to reply to itself in an endless loop.
4. **Speaker Session Continuity:** When the owner is giving a multi-step instruction, casual remarks from bystanders must not disrupt the session.

---

## 2. Technical Implementation

### 2.1 Hybrid Dual-Pitch & Overlapping Speech Detection
The engine evaluates incoming audio frames in the range 75 Hz - 400 Hz (human vocal fundamentals) using a dual-stage architecture:
* **Stage 1 (FFT Spectral Decomposition):** Analyzes `rfft` spectral peaks within the vocal fundamental band. If two peaks exceed 35% of the primary peak and possess a frequency difference $\Delta f > 30\text{ Hz}$ that is not an integer harmonic ($ratio \neq 2.0, 3.0 \pm 0.15$), overlapping speech is flagged.
* **Stage 2 (Normalized Autocorrelation):** Normalizes zero-mean autocorrelation across lags corresponding to 75-400 Hz. Prominent secondary peaks are tested with an octave-error check to ensure pitch halving is not confused with a second speaker.
* **Fail-Safe Policy:** When `is_overlapping == True`, the turn is strictly non-actionable (`actionable_speech = False`). The system outputs:
  > *"Multiple speakers detected. Please repeat your command."*

### 2.2 Active Speaker Lock (Owner Priority Mode)
* Once the owner is biometrically verified (`OWNER_001`), the engine establishes an active lock session (`_lock_active = True`) with an 8.0-second sliding expiration window.
* During active lock, turns originating from unidentified voices or guests are automatically rejected (`"Background voice ignored; active conversation is locked to the owner."`).
* Background chatter with energy below 25% of the primary speaker is cleanly filtered out without interrupting turn processing.

### 2.3 Acoustic Echo Cancellation (AEC)
* The voice pipeline in `main.py` alerts the speaker engine whenever TTS audio is being streamed (`engine.set_tts_playback_active(True)`).
* While active, incoming microphone frames with RMS energy under 3500.0 (laptop speaker acoustic leakage) are attenuated to zero and returned as non-actionable echo events (`"Suppressed acoustic echo of JARVIS TTS output."`), completely eradicating recursive feedback loops.

---

## 3. Unit Test Verification Results

| Test ID | Scenario | Input Characteristics | Expected Outcome | Actual Result | Status |
|---|---|---|---|---|---|
| `test_01` | Owner speech alone | 140 Hz sine (0.6 amp) | `actionable=True`, `is_overlapping=False` | Clean turn accepted, 1 speaker | **PASS** |
| `test_02` | Owner + weak background chatter | 140 Hz (0.7 amp) + 320 Hz (0.1 amp) | `actionable=True`, `is_overlapping=False` | Chatter filtered, turn accepted | **PASS** |
| `test_03` | Simultaneous dual speakers | 130 Hz (0.4 amp) + 220 Hz (0.4 amp) | `actionable=False`, `is_overlapping=True` | "Multiple speakers detected" alert | **PASS** |
| `test_04` | Environmental noise & TV check | Random ambient noise (0.02 amp) | Measured noise floor, media boolean | Returns noise floor (-52 dBFS) | **PASS** |
| `test_05` | Impersonator / Guest during lock | 190 Hz guest while owner locked | `actionable=False`, lock rejection | "Background voice ignored" | **PASS** |
| `test_06` | Multi-user address preference | Address title updates ("Sir", "Aman") | State update verified | Returns configured title | **PASS** |
| `test_07` | TTS acoustic echo suppression | 140 Hz speaker leakage during playback | `actionable=False`, echo suppressed | "Suppressed acoustic echo" | **PASS** |

---

## 4. Architectural Invariant
Under no circumstances will JARVIS attempt to guess or execute a split command when two speakers are talking at once. The system will consistently prompt for repetition, preserving owner authority and data integrity.
