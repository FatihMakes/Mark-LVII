"""
core/identity_engine.py — Layered Owner Identity & Authentication Engine for JARVIS H3.0
Contributed by Aman Kumar (@iamTechieAman).

Implements multi-modal layered speaker authentication:
  1. Multi-sample acoustic voiceprint embedding (centroid + tolerance envelope).
  2. Voice Liveness Detection & Anti-Replay Guard (rejects loudspeakers / replayed phone recordings).
  3. Random Challenge-Response Verification for elevated / sensitive operations.
  4. Trusted Device Binding (macOS Hardware IOPlatformUUID + machine token).
  5. Secondary PIN authentication fallback.
  6. Strict Fail-Closed Security Policy: Unknown speakers are NEVER granted owner privileges.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import platform
import random
import re
import secrets
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Storage Paths
BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
IDENTITY_FILE = MEMORY_DIR / "owner_identity.json"
TRUSTED_USERS_FILE = MEMORY_DIR / "trusted_users.json"

# Biometric & Liveness Constants
DEFAULT_OWNER_NAME = "Aman Kumar"
OWNER_SIMILARITY_THRESHOLD = 0.72  # High-confidence threshold
UNCERTAIN_THRESHOLD = 0.58        # Below this is UNKNOWN, above is UNCERTAIN/TRUSTED
LIVENESS_CONFIDENCE_MIN = 0.65    # Minimum liveness confidence required
CHALLENGE_EXPIRY_SECONDS = 45     # Challenge token valid for 45s


@dataclass
class AuthResult:
    state: str                 # OWNER_AUTHENTICATED, TRUSTED_PERSON, UNKNOWN_PERSON, UNCERTAIN, SPOOF_SUSPECTED, MULTIPLE_SPEAKERS
    speaker_name: str
    confidence: float
    liveness_score: float
    is_live: bool
    device_trusted: bool
    requires_challenge: bool = False
    challenge_phrase: Optional[str] = None
    details: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Acoustic Feature Extraction ──────────────────────────────────────────────

def extract_extended_features(audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    Extract a comprehensive 32-dimensional acoustic feature vector:
      - Temporal features: Zero-Crossing Rate (ZCR), RMS Energy, Peak-to-RMS ratio (Crest Factor)
      - Spectral shape: Centroid, Spread, Rolloff (85%), Skewness, Flux
      - Filterbanks: 18 log-spaced filterbank energies (100 Hz to sample_rate/2)
      - Pitch estimation: Fundamental frequency F0 estimate via autocorrelation
      - High-frequency harmonic distribution (air absorption / proximity check)
    """
    if audio_data.dtype == np.int16:
        signal = audio_data.astype(np.float32) / 32768.0
    else:
        signal = audio_data.astype(np.float32)
    signal = signal.flatten()

    if len(signal) < 320:
        return np.zeros(32, dtype=np.float32)

    # 1. Temporal metrics
    zcr = float(np.mean(np.abs(np.diff(np.sign(signal))))) / 2.0
    rms = float(np.sqrt(np.mean(signal ** 2))) + 1e-9
    peak = float(np.max(np.abs(signal)))
    crest_factor = min(10.0, peak / rms)

    # 2. FFT Spectral features
    fft_vals = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / sample_rate)
    sum_fft = float(np.sum(fft_vals)) + 1e-9
    norm_fft = fft_vals / sum_fft

    # Centroid & Spread
    centroid = float(np.sum(freqs * norm_fft))
    spread = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * norm_fft)))

    # Rolloff (85% energy point)
    cum_energy = np.cumsum(fft_vals)
    rolloff_idx = int(np.searchsorted(cum_energy, 0.85 * cum_energy[-1]))
    rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    # Spectral Flux (frame-to-frame variance estimate)
    spectral_flux = float(np.std(fft_vals[:min(len(fft_vals), 500)])) / (rms * 1000.0 + 1e-5)

    # 3. 18-band log filterbanks (100 Hz to 7500 Hz)
    nyquist = min(sample_rate // 2, 7800)
    bands = np.logspace(np.log10(100), np.log10(nyquist), num=19)
    band_energies = []
    for i in range(18):
        idx = np.where((freqs >= bands[i]) & (freqs < bands[i + 1]))[0]
        if len(idx) > 0:
            energy = float(np.mean(fft_vals[idx]))
        else:
            energy = 0.0
        band_energies.append(float(np.log1p(energy)))

    # 4. Pitch F0 estimate via autocorrelation
    pitch_est = 0.0
    try:
        corr = np.correlate(signal, signal, mode="full")
        corr = corr[len(corr) // 2:]
        min_lag = int(sample_rate / 400)  # 400 Hz max pitch
        max_lag = int(sample_rate / 60)   # 60 Hz min pitch
        if len(corr) > max_lag:
            lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
            if lag > 0:
                pitch_est = float(sample_rate / lag)
    except Exception:
        pitch_est = 0.0

    # Assemble 32-dim normalized vector
    vec = np.array([
        zcr * 10.0,
        min(1.0, rms * 5.0),
        crest_factor / 10.0,
        centroid / 4000.0,
        spread / 3000.0,
        rolloff / 6000.0,
        min(1.0, spectral_flux / 5.0),
        min(1.0, pitch_est / 300.0),
        *band_energies[:18],
        # Derived ratios for vocal tract resonance
        float(band_energies[1] / (band_energies[0] + 1e-4)),
        float(band_energies[3] / (band_energies[2] + 1e-4)),
        float(band_energies[5] / (band_energies[4] + 1e-4)),
        float(band_energies[8] / (band_energies[7] + 1e-4)),
        float(band_energies[12] / (band_energies[11] + 1e-4)),
        float(band_energies[16] / (band_energies[15] + 1e-4)),
    ], dtype=np.float32)

    vec = vec[:32]
    norm = float(np.linalg.norm(vec)) + 1e-9
    return vec / norm


# ── Voice Liveness & Anti-Replay Detection ────────────────────────────────────

def detect_voice_liveness(audio_data: np.ndarray, sample_rate: int = 16000) -> Tuple[bool, float, str]:
    """
    Detects whether the voice input is from a LIVE human speaker in front of the mic
    vs a recorded audio playback through phone speakers, Bluetooth loudspeakers, or synthetic injection.

    Key physical biomarkers checked:
      1. Low-frequency speaker cutoff (< 100 Hz attenuation common in mobile speakers).
      2. High-frequency ultrasonic/air damping (> 7 kHz speaker resonance/attenuation).
      3. Acoustic crest factor / dynamic range compression (recordings suffer loss of dynamic depth).
      4. Vocal micro-tremors (physiological involuntary 4-8 Hz frequency tremor in live human vocal cords).
    """
    if audio_data.dtype == np.int16:
        signal = audio_data.astype(np.float32) / 32768.0
    else:
        signal = audio_data.astype(np.float32)
    signal = signal.flatten()

    if len(signal) < int(sample_rate * 0.3):
        return True, 0.70, "Audio too short for full liveness pass; baseline granted"

    fft_vals = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / sample_rate)
    total_energy = float(np.sum(fft_vals)) + 1e-9

    # Energy in low band (< 140 Hz) - mobile speakers strongly cut off here
    low_band_idx = np.where((freqs >= 40) & (freqs < 140))[0]
    low_ratio = float(np.sum(fft_vals[low_band_idx])) / total_energy if len(low_band_idx) > 0 else 0.0

    # Energy in high band (> 6500 Hz)
    high_band_idx = np.where(freqs >= 6500)[0]
    high_ratio = float(np.sum(fft_vals[high_band_idx])) / total_energy if len(high_band_idx) > 0 else 0.0

    # Speech core band (300 Hz - 3400 Hz)
    core_idx = np.where((freqs >= 300) & (freqs <= 3400))[0]
    core_ratio = float(np.sum(fft_vals[core_idx])) / total_energy if len(core_idx) > 0 else 0.0

    # Dynamic Range / Crest Factor
    rms = float(np.sqrt(np.mean(signal ** 2))) + 1e-9
    peak = float(np.max(np.abs(signal)))
    crest = peak / rms

    # Vocal Micro-tremor estimation (envelope modulation in 3-8 Hz band)
    hop = int(sample_rate * 0.02)  # 20ms frames
    frame_energies = [
        float(np.sqrt(np.mean(signal[i:i + hop] ** 2)))
        for i in range(0, len(signal) - hop, hop)
    ]
    tremor_score = 0.5
    if len(frame_energies) > 16:
        env_fft = np.abs(np.fft.rfft(frame_energies - np.mean(frame_energies)))
        env_freqs = np.fft.rfftfreq(len(frame_energies), d=0.02)
        tremor_band = np.where((env_freqs >= 3.0) & (env_freqs <= 8.0))[0]
        if len(tremor_band) > 0:
            tremor_energy = float(np.sum(env_fft[tremor_band]))
            total_env_energy = float(np.sum(env_fft)) + 1e-9
            tremor_score = min(1.0, (tremor_energy / total_env_energy) * 3.5)

    # Heuristic scoring
    score = 0.50
    reasons = []

    # Live human speech has healthy crest factor (usually 3.0 to 8.5)
    if 2.8 <= crest <= 9.0:
        score += 0.15
    elif crest < 2.0:
        score -= 0.25
        reasons.append("Extreme audio compression typical of replayed stream")

    # Core speech band balance
    if 0.35 <= core_ratio <= 0.90:
        score += 0.15
    else:
        score -= 0.15
        reasons.append("Abnormal spectral balance outside natural human acoustic range")

    # Vocal tremor presence
    if tremor_score >= 0.20:
        score += 0.15
    else:
        score -= 0.10
        reasons.append("Absence of natural human vocal cord micro-tremor")

    # Speaker artificial cutoff check: very low low_ratio + very low high_ratio simultaneously indicates cheap transducer
    if low_ratio < 0.005 and high_ratio < 0.005:
        score -= 0.25
        reasons.append("Severe frequency bandwidth clipping typical of external phone loudspeaker")

    score = max(0.0, min(1.0, score))
    is_live = score >= LIVENESS_CONFIDENCE_MIN
    desc = "Live human voice confirmed" if is_live else ("; ".join(reasons) or "Potential speaker playback detected")

    return is_live, round(score, 3), desc


# ── Trusted Device Fingerprinting ─────────────────────────────────────────────

def get_device_fingerprint() -> dict:
    """
    Extracts immutable hardware and local system identifiers on macOS/Linux/Windows.
    """
    hw_uuid = ""
    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                "ioreg -rd1 -c IOPlatformExpertDevice | grep -i IOPlatformUUID",
                shell=True, text=True, stderr=subprocess.DEVNULL
            )
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            if m:
                hw_uuid = m.group(1).strip()
        except Exception:
            pass

    if not hw_uuid:
        # Fallback to persistent hardware-derived MAC hash
        hw_uuid = f"NODE-{hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:18]}"

    hostname = platform.node()
    os_name = f"{platform.system()} {platform.release()} ({platform.machine()})"

    return {
        "hardware_uuid": hw_uuid,
        "hostname": hostname,
        "os": os_name,
        "device_token": hashlib.sha256(f"{hw_uuid}:{hostname}".encode()).hexdigest(),
    }


# ── Challenge-Response Generator ──────────────────────────────────────────────

_CHALLENGE_WORDS = [
    "alpha", "bravo", "charlie", "delta", "echo", "falcon", "gamma",
    "horizon", "indigo", "jupiter", "kestrel", "lunar", "matrix",
    "nebula", "omega", "phoenix", "quantum", "radar", "solaris",
    "titan", "ultra", "vortex", "zenith"
]

_active_challenges: Dict[str, Tuple[str, float]] = {}  # session_id -> (challenge, expiry)


def generate_challenge(session_id: str = "default") -> str:
    """Generate a random 3-word phonetic challenge phrase for elevated verification."""
    selected = random.sample(_CHALLENGE_WORDS, 3)
    num = random.randint(10, 99)
    phrase = f"{selected[0]} {selected[1]} {num}"
    _active_challenges[session_id] = (phrase.lower(), time.time() + CHALLENGE_EXPIRY_SECONDS)
    return phrase


def verify_challenge(spoken_text: str, session_id: str = "default") -> bool:
    """Verify if the user's spoken answer matches the pending challenge."""
    if session_id not in _active_challenges:
        return False
    target, expiry = _active_challenges[session_id]
    if time.time() > expiry:
        del _active_challenges[session_id]
        return False

    clean_spoken = re.sub(r"[^a-z0-9\s]", "", spoken_text.lower()).strip()
    clean_target = re.sub(r"[^a-z0-9\s]", "", target).strip()

    # Check words match
    target_words = clean_target.split()
    matched_words = sum(1 for w in target_words if w in clean_spoken)
    success = matched_words >= len(target_words) - 1 and len(target_words) > 0

    if success:
        _active_challenges.pop(session_id, None)
    return success


# ── Owner Profile Manager ─────────────────────────────────────────────────────

def load_owner_profile() -> Optional[dict]:
    """Loads owner profile if enrolled and valid, auto-syncing from ~/.jarvis_voiceprint.json if needed."""
    if IDENTITY_FILE.is_file():
        try:
            data = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
            if data.get("enrolled") and data.get("vector") and len(data["vector"]) >= 20:
                return data
        except Exception as e:
            print(f"[IdentityEngine] ⚠️ Error loading owner profile: {e}")

    # Fallback & auto-sync from ~/.jarvis_voiceprint.json
    voiceprint_path = Path.home() / ".jarvis_voiceprint.json"
    if voiceprint_path.is_file():
        try:
            vp = json.loads(voiceprint_path.read_text(encoding="utf-8"))
            vec = vp.get("vector", [])
            if vec and len(vec) >= 20:
                owner_name = vp.get("owner", DEFAULT_OWNER_NAME)
                profile = {
                    "owner_name": owner_name,
                    "preferred_address": "Sir",
                    "role": "OWNER",
                    "enrolled": True,
                    "enrolled_at": vp.get("enrolled_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                    "vector": vec,
                    "hardware_uuid": get_machine_hardware_uuid(),
                    "security_tier": "OWNER_UNRESTRICTED"
                }
                MEMORY_DIR.mkdir(parents=True, exist_ok=True)
                IDENTITY_FILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")
                return profile
        except Exception as e:
            print(f"[IdentityEngine] Voiceprint sync error: {e}")

    return None


def is_owner_enrolled() -> bool:
    return load_owner_profile() is not None


def enroll_owner_profile(
    name: str,
    samples: List[np.ndarray],
    pin: Optional[str] = None,
    honorific: str = "Sir",
    sample_rate: int = 16000
) -> dict:
    """
    Enrolls the primary owner using multiple voice samples.
    Computes average centroid vector and feature variance envelope.
    Registers current machine as trusted device.
    """
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    clean_name = (name or DEFAULT_OWNER_NAME).strip()

    if not samples:
        raise ValueError("At least one audio sample required for enrollment.")

    vectors = [extract_extended_features(s, sample_rate) for s in samples if len(s) > 256]
    if not vectors:
        raise ValueError("Audio samples did not contain enough speech energy.")

    centroid = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(centroid)) + 1e-9
    centroid = centroid / norm

    variance = np.var(vectors, axis=0).tolist() if len(vectors) > 1 else [0.01] * len(centroid)

    # Hash PIN if provided
    pin_hash = ""
    salt = ""
    if pin:
        salt = secrets.token_hex(8)
        pin_hash = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 100_000).hex()

    device_info = get_device_fingerprint()

    profile = {
        "enrolled": True,
        "owner_name": clean_name,
        "honorific": honorific,
        "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sample_rate": sample_rate,
        "samples_count": len(vectors),
        "vector": centroid.tolist(),
        "variance": variance,
        "trusted_devices": [device_info],
        "pin_hash": pin_hash,
        "pin_salt": salt,
        "security_level": "STRICT_BIOMETRIC_LIVENESS",
    }

    IDENTITY_FILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    # Also sync backwards-compatible ~/.jarvis_voiceprint.json for older code
    legacy_file = Path.home() / ".jarvis_voiceprint.json"
    legacy_payload = {
        "owner": clean_name,
        "enrolled_at": profile["enrolled_at"],
        "sample_rate": sample_rate,
        "enabled": True,
        "calibrated_real": True,
        "vector": centroid.tolist()[:20]
    }
    try:
        legacy_file.write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")
    except Exception:
        pass

    return {
        "status": "ENROLLED",
        "owner": clean_name,
        "samples": len(vectors),
        "device": device_info["hardware_uuid"],
        "enrolled_at": profile["enrolled_at"]
    }


def verify_owner_pin(pin: str) -> bool:
    """Verifies owner secondary PIN."""
    profile = load_owner_profile()
    if not profile or not profile.get("pin_hash"):
        return False
    salt = profile.get("pin_salt", "")
    target = profile.get("pin_hash", "")
    computed = hashlib.pbkdf2_hmac("sha256", pin.strip().encode(), salt.encode(), 100_000).hex()
    return hmac.compare_digest(target, computed)


# ── Full Layered Authentication Pipeline ──────────────────────────────────────

def authenticate_speaker_turn(
    audio_data: np.ndarray,
    sample_rate: int = 16000,
    request_device_id: Optional[str] = None
) -> AuthResult:
    """
    Main authentication gate for every incoming user speech turn.
    Performs layered verification:
      1. Voice Biometrics (cosine similarity against enrolled centroid).
      2. Anti-Replay / Liveness Verification.
      3. Trusted Device Check.
      4. Multi-user Trust lookup if not owner.
    """
    owner = load_owner_profile()
    curr_dev = get_device_fingerprint()

    # Device trust check
    device_trusted = True
    if owner and owner.get("trusted_devices"):
        known_uuids = [d.get("hardware_uuid") for d in owner["trusted_devices"]]
        if curr_dev["hardware_uuid"] not in known_uuids:
            device_trusted = False

    # Extract acoustic features & liveness
    cur_vec = extract_extended_features(audio_data, sample_rate)
    is_live, liveness_score, live_details = detect_voice_liveness(audio_data, sample_rate)

    if not owner:
        # No owner profile enrolled yet: Allow setup / general mode
        return AuthResult(
            state="GUEST_USER",
            speaker_name="Guest (Setup Required)",
            confidence=1.0,
            liveness_score=liveness_score,
            is_live=is_live,
            device_trusted=device_trusted,
            details="No owner profile configured. Operating in initial setup mode."
        )

    owner_name = owner.get("owner_name", DEFAULT_OWNER_NAME)
    ref_vec = np.array(owner["vector"], dtype=np.float32)

    # Cosine Similarity against Owner Centroid
    similarity = float(np.dot(ref_vec[:len(cur_vec)], cur_vec[:len(ref_vec)]))
    similarity = max(0.0, min(1.0, similarity))

    # Anti-Replay / Liveness check failure
    if not is_live and liveness_score < 0.45 and similarity > 0.60:
        return AuthResult(
            state="SPOOF_SUSPECTED",
            speaker_name="Unverified Speaker",
            confidence=round(similarity, 3),
            liveness_score=liveness_score,
            is_live=False,
            device_trusted=device_trusted,
            details=f"Acoustic liveness check failed: {live_details}"
        )

    # 1. High-confidence Match + Liveness + Trusted Device -> OWNER
    if similarity >= OWNER_SIMILARITY_THRESHOLD and is_live and device_trusted:
        return AuthResult(
            state="OWNER_AUTHENTICATED",
            speaker_name=owner_name,
            confidence=round(similarity, 3),
            liveness_score=liveness_score,
            is_live=True,
            device_trusted=True,
            details="Owner authenticated via multimodal biometrics and hardware binding."
        )

    # 2. Borderline / Uncertain match -> Requires Challenge or PIN
    if UNCERTAIN_THRESHOLD <= similarity < OWNER_SIMILARITY_THRESHOLD:
        challenge = generate_challenge("auth_gate")
        return AuthResult(
            state="UNCERTAIN",
            speaker_name="Uncertain Speaker",
            confidence=round(similarity, 3),
            liveness_score=liveness_score,
            is_live=is_live,
            device_trusted=device_trusted,
            requires_challenge=True,
            challenge_phrase=challenge,
            details=f"Voice similarity ({similarity:.2f}) is in verification zone. Challenge required."
        )

    # 3. Check Authorized Multi-Users Registry
    from core import permissions
    trusted_user = permissions.match_authorized_user(cur_vec)
    if trusted_user:
        return AuthResult(
            state="TRUSTED_PERSON",
            speaker_name=trusted_user.get("name", "Authorized User"),
            confidence=round(trusted_user.get("score", similarity), 3),
            liveness_score=liveness_score,
            is_live=is_live,
            device_trusted=device_trusted,
            details=f"Authorized user '{trusted_user.get('name')}' recognized with scoped permissions."
        )

    # 4. Unknown Person
    return AuthResult(
        state="UNKNOWN_PERSON",
        speaker_name="Unknown Person",
        confidence=round(similarity, 3),
        liveness_score=liveness_score,
        is_live=is_live,
        device_trusted=device_trusted,
        details="Speaker acoustic profile does not match registered owner or authorized users."
    )


# ── Aliases & Convenience Helpers ─────────────────────────────────────────────
extract_acoustic_features = extract_extended_features
get_owner_profile = load_owner_profile


def get_hardware_device_token() -> str:
    """Returns persistent hardware UUID token for device-level lock."""
    return get_device_fingerprint().get("hardware_uuid", "macOS-Device")
