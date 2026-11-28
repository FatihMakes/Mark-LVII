# JARVIS H3.2 — Owner Authentication & Session Persistence Report

---

## 1. Problem Statement & Legacy Flaws

Prior to H3.2, user interaction was plagued by repetitive authorization prompts:
1. **Audio Micro-Chunk Demotion:** `main.py` evaluated speaker identity across 0.25-second audio blocks. If a turn contained natural speech pauses or soft fricatives, the correlation score dipped below threshold, immediately flipping `_current_speaker = UserRole.TEMPORARY_GUEST`.
2. **Aggressive Action Gating:** `core/action_loader.py` defaulted any newly added or unlisted action to `SecurityTier.OWNER_ONLY`. When combined with the chunk demotion bug, nearly every voice command was greeted with: *"Sorry, this operation requires owner authorization"*.
3. **Missing Profile Path:** `identity_engine.load_owner_profile()` looked for `memory/owner_identity.json` (which was empty), while the actual calibrated voiceprint existed at `~/.jarvis_voiceprint.json`.
4. **Hardcoded PIN Vulnerability:** `core/anti_theft.py` and `actions/anti_theft.py` relied on a static hardcoded PIN `"1170"`, presenting an unacceptable security defect.

---

## 2. Engineering Solution Implemented

### A. Persistent Owner Session (`core/owner_session.py`)
- Created `OwnerSessionManager` with a **30-minute sliding session window**.
- When the owner authenticates via calibrated voice biometrics (confidence $\ge 0.55$) or master PIN, an `OwnerSessionState` is established.
- Every speech turn or tool execution touches the session timestamp (`session.touch()`), resetting the 30-minute timer.
- In `core/permissions.py`: If `owner_session.is_owner_session_active()` is True, normal commands execute directly without re-prompting.

### B. Biometric Voiceprint Auto-Synchronization
- `core/identity_engine.py` now checks both `memory/owner_identity.json` and `~/.jarvis_voiceprint.json`.
- If `~/.jarvis_voiceprint.json` exists, it automatically initializes and caches the owner profile for Aman Kumar.

### C. Cryptographic PIN Hashing (PBKDF2-HMAC-SHA256)
- Eliminated all occurrences of hardcoded `"1170"`.
- PINs are salted with 16 bytes of cryptographically secure random bytes (`secrets.token_hex(16)`) and hashed using 100,000 iterations of PBKDF2-HMAC-SHA256.
- PIN comparisons use constant-time `secrets.compare_digest` to prevent timing attacks.
- Failed PIN attempts are throttled: 5 consecutive failures trigger a 60-second lockout.

### D. Risk-Gated Operation Model
- **Normal Operations:** (opening apps, web search, media playback, document generation, coding) proceed immediately under an active owner session.
- **Sensitive Operations:** (irreversible disk wiping, production deployment, real financial transfers) enforce explicit step-up confirmation cards.

---

## 3. Verification & Test Evidence

Validated in `tests/test_h3_2_owner_session.py`:
- `test_01_session_lifecycle`: Verified session creation, validity check, touch, and clean termination.
- `test_02_pin_hashing_and_verification`: Verified PBKDF2 hash verification; confirmed old PIN `1170` is rejected.
- `test_03_rate_limiting_on_repeated_wrong_pins`: Verified 5-attempt threshold and 60s lockout.
- `test_04_permissions_integration_with_active_session`: Verified owner-only actions execute seamlessly when session is active.
- `test_05_risk_gated_execution`: Verified differentiation between standard operations and high-risk operations.
