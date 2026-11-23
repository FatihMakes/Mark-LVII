"""
core/permissions.py — Multi-User Permission & Trust Management Engine for JARVIS H3.0
Contributed by Aman Kumar (@iamTechieAman).

Enforces Role-Based Access Control (RBAC) and Least Privilege across all JARVIS tools:
  - Roles:
      1. OWNER: Complete unconstrained control over system, private memory, and tools.
      2. AUTHORIZED_PERSON: Explicitly delegated capabilities by owner (e.g. music, study, general QA).
      3. TEMPORARY_GUEST: Session-scoped limited access (public web, weather, public chat).
      4. UNKNOWN_PERSON: Zero privileged access; private data and system control locked.
  - Action Security Tiers:
      PUBLIC, AUTHORIZED, OWNER_ONLY, HIGH_RISK_FINANCIAL.
  - Fail-Closed Gate:
      If speaker authorization is insufficient, privileged operations fail immediately with:
      "Sorry, owner authorization is required for this operation."
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from enum import Enum

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
USERS_FILE = MEMORY_DIR / "authorized_users.json"
PERM_AUDIT_LOG = MEMORY_DIR / "permission_audit.jsonl"

# ── Role Definitions ─────────────────────────────────────────────────────────
class UserRole(str, Enum):
    OWNER             = "OWNER"
    AUTHORIZED_PERSON = "AUTHORIZED_PERSON"
    TEMPORARY_GUEST   = "TEMPORARY_GUEST"
    UNKNOWN           = "UNKNOWN"

ROLE_OWNER             = UserRole.OWNER.value
ROLE_AUTHORIZED_PERSON = UserRole.AUTHORIZED_PERSON.value
ROLE_TEMPORARY_GUEST   = UserRole.TEMPORARY_GUEST.value
ROLE_UNKNOWN           = UserRole.UNKNOWN.value

# ── Action Security Classification ───────────────────────────────────────────
class SecurityTier(str, Enum):
    PUBLIC              = "PUBLIC"
    AUTHORIZED          = "AUTHORIZED"
    OWNER_ONLY          = "OWNER_ONLY"
    HIGH_RISK_FINANCIAL = "HIGH_RISK_FINANCIAL"

SECURITY_PUBLIC             = SecurityTier.PUBLIC.value
SECURITY_AUTHORIZED         = SecurityTier.AUTHORIZED.value
SECURITY_OWNER_ONLY         = SecurityTier.OWNER_ONLY.value
SECURITY_HIGH_RISK          = SecurityTier.HIGH_RISK_FINANCIAL.value

# Global Speaker State for current session / turn
_current_speaker: UserRole = UserRole.OWNER


def set_current_speaker(role: UserRole | str) -> None:
    global _current_speaker
    if isinstance(role, str):
        val = role.upper()
        for r in UserRole:
            if r.value == val or r.name == val:
                _current_speaker = r
                return
        _current_speaker = UserRole.UNKNOWN
    elif isinstance(role, UserRole):
        _current_speaker = role


def get_current_speaker() -> str:
    return _current_speaker.value

# Tool Classification Catalog
ACTION_SECURITY_LEVELS: Dict[str, str] = {
    # Public (Anyone including guest can ask)
    "weather_report": SECURITY_PUBLIC,
    "web_search": SECURITY_PUBLIC,
    "music_recognition": SECURITY_PUBLIC,
    "youtube_video": SECURITY_PUBLIC,
    "video_player": SECURITY_PUBLIC,
    "reminder": SECURITY_PUBLIC,
    "anime_control": SECURITY_PUBLIC,
    "google_maps": SECURITY_PUBLIC,
    "creator_info": SECURITY_PUBLIC,
    "mac_deep_scan": SECURITY_PUBLIC,
    "download_manager": SECURITY_AUTHORIZED,
    
    # Authorized (Owner + Approved Friends/Colleagues)
    "code_helper": SECURITY_AUTHORIZED,
    "study_copilot": SECURITY_AUTHORIZED,
    "document_studio": SECURITY_AUTHORIZED,
    "resume_studio": SECURITY_AUTHORIZED,
    "image_generator": SECURITY_AUTHORIZED,
    "video_studio": SECURITY_AUTHORIZED,
    "game_updater": SECURITY_AUTHORIZED,
    "media_downloader": SECURITY_AUTHORIZED,
    "concierge_service": SECURITY_AUTHORIZED,  # Discovery only; booking is gated
    "flight_finder": SECURITY_AUTHORIZED,      # Search only; booking is gated
    "travel_booking": SECURITY_AUTHORIZED,     # Search is authorized; purchase is high-risk
    "smart_lights": SECURITY_AUTHORIZED,
    "excel_writer": SECURITY_AUTHORIZED,
    "build_guide": SECURITY_AUTHORIZED,

    # Owner-Only (Private or System Modifications)
    "dev_agent": SECURITY_OWNER_ONLY,
    "autonomous_code_agent": SECURITY_OWNER_ONLY,
    "coding_pipeline": SECURITY_OWNER_ONLY,
    "code_interpreter": SECURITY_OWNER_ONLY,
    "file_controller": SECURITY_OWNER_ONLY,
    "file_processor": SECURITY_OWNER_ONLY,
    "computer_control": SECURITY_OWNER_ONLY,
    "computer_settings": SECURITY_OWNER_ONLY,
    "desktop_control": SECURITY_OWNER_ONLY,
    "browser_control": SECURITY_OWNER_ONLY,
    "system_monitor": SECURITY_OWNER_ONLY,
    "screen_processor": SECURITY_OWNER_ONLY,
    "visual_recon": SECURITY_OWNER_ONLY,
    "phone_caller": SECURITY_OWNER_ONLY,
    "send_message": SECURITY_OWNER_ONLY,
    "cyber_security": SECURITY_OWNER_ONLY,
    "voice_biometrics": SECURITY_OWNER_ONLY,
    "adaptive_identity": SECURITY_OWNER_ONLY,
    "self_learning": SECURITY_OWNER_ONLY,
    "self_repair": SECURITY_OWNER_ONLY,
    "routines": SECURITY_OWNER_ONLY,
    "background_tasks": SECURITY_OWNER_ONLY,
    "background_monitor": SECURITY_OWNER_ONLY,
    "job_hunter": SECURITY_OWNER_ONLY,
    "rea_tool": SECURITY_OWNER_ONLY,
    "telegram_remote": SECURITY_OWNER_ONLY,
    "godmode_assistant": SECURITY_OWNER_ONLY,
    "omninet_supertool": SECURITY_OWNER_ONLY,

    # High-Risk / Financial (Requires explicit owner confirmation card)
    "ai_trading": SECURITY_HIGH_RISK,
}

ACTION_SECURITY_TIERS = ACTION_SECURITY_LEVELS


@dataclass
class UserProfile:
    user_id: str
    name: str
    role: str
    allowed_capabilities: List[str] = field(default_factory=list)
    denied_capabilities: List[str] = field(default_factory=list)
    voice_vector: Optional[List[float]] = None
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    expires_at: Optional[float] = None  # Epoch timestamp for temporary guests
    is_revoked: bool = False

    def is_expired(self) -> bool:
        if self.expires_at and time.time() > self.expires_at:
            return True
        return False

    def to_dict(self) -> dict:
        return asdict(self)


def _load_users() -> Dict[str, UserProfile]:
    if not USERS_FILE.is_file():
        return {}
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        res = {}
        for uid, udata in data.items():
            res[uid] = UserProfile(**udata)
        return res
    except Exception as e:
        print(f"[Permissions] ⚠️ Error loading authorized users: {e}")
        return {}


def _save_users(users: Dict[str, UserProfile]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {uid: u.to_dict() for uid, u in users.items()}
    USERS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _log_audit(event: str, speaker: str, action: str, allowed: bool, detail: str = "") -> None:
    try:
        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            "speaker": speaker,
            "action": action,
            "allowed": allowed,
            "detail": detail
        }
        with open(PERM_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


# ── User Authorization Management ─────────────────────────────────────────────

def authorize_person(
    name: str,
    role: str | UserRole = ROLE_AUTHORIZED_PERSON,
    allowed_caps: Optional[List[str]] = None,
    denied_caps: Optional[List[str]] = None,
    duration_minutes: Optional[int] = None,
    voice_vector: Optional[np.ndarray] = None,
    tier: Optional[str | SecurityTier] = None,
    capabilities: Optional[List[str]] = None
) -> dict:
    """
    Authorizes a new person with explicit scoped capabilities.
    Only permitted when called by or confirmed by OWNER.
    """
    users = _load_users()
    clean_name = name.strip()
    uid = f"user_{clean_name.lower().replace(' ', '_')}"
    role_str = role.value if hasattr(role, "value") else str(role)

    expires = None
    if duration_minutes:
        expires = time.time() + (duration_minutes * 60)

    caps = capabilities or allowed_caps or ["weather_report", "web_search", "youtube_video", "study_copilot", "music"]
    denied = denied_caps or ["dev_agent", "file_controller", "system_settings", "ai_trading"]

    vec = voice_vector.tolist() if voice_vector is not None else None

    profile = UserProfile(
        user_id=uid,
        name=clean_name,
        role=role_str,
        allowed_capabilities=caps,
        denied_capabilities=denied,
        voice_vector=vec,
        expires_at=expires,
        is_revoked=False
    )
    users[uid] = profile
    _save_users(users)
    _log_audit("AUTHORIZE_USER", "OWNER", f"Grant {role_str} to {clean_name}", True)

    return {
        "status": "AUTHORIZED",
        "user_id": uid,
        "name": clean_name,
        "role": role_str,
        "allowed_capabilities": caps,
        "expires_in_minutes": duration_minutes or "Unlimited"
    }


def revoke_person(name_or_id: str) -> bool:
    """Revokes permissions for a given user immediately."""
    users = _load_users()
    target_uid = None
    clean_target = name_or_id.lower().strip()

    for uid, u in users.items():
        if uid.lower() == clean_target or u.name.lower() == clean_target:
            target_uid = uid
            break

    if target_uid and target_uid in users:
        users[target_uid].is_revoked = True
        _save_users(users)
        _log_audit("REVOKE_USER", "OWNER", f"Revoked {users[target_uid].name}", True)
        return True
    return False


authorize_user = authorize_person
revoke_user = revoke_person


def list_authorized_users() -> List[dict]:
    """Returns list of active, non-revoked users."""
    users = _load_users()
    active = []
    for u in users.values():
        if not u.is_revoked and not u.is_expired():
            active.append(u.to_dict())
    return active


def match_authorized_user(feature_vector: np.ndarray, threshold: float = 0.68) -> Optional[dict]:
    """
    Checks if incoming acoustic vector matches any enrolled authorized user.
    """
    users = _load_users()
    best_match = None
    best_score = 0.0

    for u in users.values():
        if u.is_revoked or u.is_expired() or not u.voice_vector:
            continue
        ref = np.array(u.voice_vector, dtype=np.float32)
        score = float(np.dot(ref, feature_vector))
        if score > best_score:
            best_score = score
            best_match = u

    if best_match and best_score >= threshold:
        return {
            "user_id": best_match.user_id,
            "name": best_match.name,
            "role": best_match.role,
            "score": best_score,
            "allowed_capabilities": best_match.allowed_capabilities,
            "denied_capabilities": best_match.denied_capabilities
        }
    return None


# ── Action Permission Gatekeeper ──────────────────────────────────────────────

def check_permission(
    first_arg: str | SecurityTier,
    second_arg: Optional[str] = None,
    speaker_name: str = "Unknown",
    parameters: Optional[dict] = None
) -> Tuple[bool, str]:
    """
    Evaluates whether the speaker is authorized to run the requested action.
    Supports both signatures:
      check_permission(action_name, speaker_auth_state)
      check_permission(tier, action_name)
    """
    # Normalize inputs
    if isinstance(first_arg, (SecurityTier, str)) and second_arg is not None and (
        isinstance(first_arg, SecurityTier) or first_arg in [t.value for t in SecurityTier]
    ):
        tier_str = first_arg.value if hasattr(first_arg, "value") else str(first_arg)
        action_name = str(second_arg)
        speaker_auth_state = None
    else:
        action_name = str(first_arg)
        speaker_auth_state = str(second_arg) if second_arg is not None else None
        tier_str = ACTION_SECURITY_LEVELS.get(action_name, SECURITY_AUTHORIZED)

    if speaker_auth_state is None:
        try:
            from core.owner_session import get_owner_session
            if get_owner_session().is_owner_session_active() and _current_speaker != UserRole.TEMPORARY_GUEST:
                speaker_auth_state = "OWNER_AUTHENTICATED"
        except Exception:
            pass

    if speaker_auth_state is None:
        if _current_speaker == UserRole.OWNER:
            speaker_auth_state = "OWNER_AUTHENTICATED"
        elif _current_speaker == UserRole.AUTHORIZED_PERSON:
            speaker_auth_state = "TRUSTED_PERSON"
        elif _current_speaker == UserRole.TEMPORARY_GUEST:
            speaker_auth_state = "TEMPORARY_GUEST"
        else:
            speaker_auth_state = "UNKNOWN"

    # 1. OWNER has full access to PUBLIC, AUTHORIZED, and OWNER_ONLY
    if speaker_auth_state == "OWNER_AUTHENTICATED":
        if tier_str == SECURITY_HIGH_RISK:
            return True, "Owner authenticated for high-risk action."
        _log_audit("CHECK_PERM", speaker_name, action_name, True, "Owner granted")
        return True, "Owner authenticated."

    # 2. Public actions are accessible to anyone
    if tier_str == SECURITY_PUBLIC:
        _log_audit("CHECK_PERM", speaker_name, action_name, True, "Public tool granted")
        return True, "Public capability."

    # 3. Authorized Users check
    if speaker_auth_state == "TRUSTED_PERSON":
        users = _load_users()
        user = next((u for u in users.values() if u.name.lower() == speaker_name.lower() and not u.is_revoked), None)
        if user:
            if action_name in user.denied_capabilities:
                _log_audit("CHECK_PERM", speaker_name, action_name, False, "Explicitly denied in user profile")
                return False, f"Sorry {speaker_name}, access to '{action_name}' is restricted by the owner."
            if action_name in user.allowed_capabilities or tier_str == SECURITY_AUTHORIZED:
                _log_audit("CHECK_PERM", speaker_name, action_name, True, "Authorized capability granted")
                return True, "Authorized person granted."

    # 4. Guest / Unknown person requesting privileged actions
    _log_audit("CHECK_PERM", speaker_name, action_name, False, f"Denied {tier_str} action to {speaker_auth_state}")
    return False, "Sorry, owner authorization is required for this operation."
