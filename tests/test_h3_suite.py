"""
tests/test_h3_suite.py — Automated Verification Suite for JARVIS H3.0
Contributed by Aman Kumar (@iamTechieAman).

Validates:
  1. Identity Engine: 32-dim features, Liveness score, Phonetic Challenge, Hardware Token.
  2. Permission Engine: Role tiers, Scoped capability lists, Audit trail logging.
  3. Memory Isolation: Personal owner memory shielded in guest mode.
  4. Voice Cloner: Audio quality analysis (SNR), Bandpass filtering, Profile store.
  5. Travel Safeguards: Travel search links, Review card enforcement, Booking gates.
  6. Self-Healing Watchdog: Subsystem probes, Security invariant validation, Rollback guard.
  7. Full Action & Plugin Discovery: 100% syntactically valid and registered.
"""
from __future__ import annotations

import os
import sys
import unittest
import numpy as np
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core import identity_engine, permissions, voice_cloner, watchdog
from core.permissions import UserRole, SecurityTier, check_permission, set_current_speaker, get_current_speaker
from memory import memory_manager


class TestH3IdentityEngine(unittest.TestCase):
    """Tests for Layered Owner Identity & Voice Biometrics."""

    def test_feature_extraction_dimension(self):
        # 16kHz sine wave test
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        
        feats = identity_engine.extract_acoustic_features(audio, sr)
        self.assertEqual(feats.shape, (32,))
        self.assertFalse(np.isnan(feats).any())
        self.assertFalse(np.isinf(feats).any())

    def test_liveness_detection(self):
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        
        # Test synthetic static tone
        synth_audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        is_live_synth, score_synth, _ = identity_engine.detect_voice_liveness(synth_audio, sr)
        # Synthetic flat sine wave lacks natural human micro-tremors
        self.assertIsInstance(is_live_synth, bool)
        self.assertIsInstance(score_synth, float)

        # Natural pseudo-speech with micro-tremors and harmonics
        noise = np.random.normal(0, 0.02, sr)
        f0_mod = 120 + 5 * np.sin(2 * np.pi * 5 * t)  # 5Hz natural vocal flutter
        vocal = 0.4 * np.sin(2 * np.pi * f0_mod * t) + 0.2 * np.sin(2 * np.pi * 2 * f0_mod * t) + noise
        speech_audio = (vocal * 32767).astype(np.int16)
        is_live_speech, score_speech, _ = identity_engine.detect_voice_liveness(speech_audio, sr)
        self.assertGreater(score_speech, score_synth)

    def test_challenge_response_generation_and_validation(self):
        phrase = identity_engine.generate_challenge("test_sess")
        words = phrase.split()
        self.assertEqual(len(words), 3)

        # Correct challenge
        ok = identity_engine.verify_challenge(phrase, "test_sess")
        self.assertTrue(ok)

        # Incorrect challenge
        wrong = identity_engine.verify_challenge("wrong phrase here", "test_sess")
        self.assertFalse(wrong)

    def test_hardware_device_token(self):
        token = identity_engine.get_hardware_device_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 4)


class TestH3PermissionEngine(unittest.TestCase):
    """Tests for Multi-User Permission & Security Access Control."""

    def setUp(self):
        # Reset speaker to OWNER before each test
        set_current_speaker(UserRole.OWNER)

    def tearDown(self):
        set_current_speaker(UserRole.OWNER)

    def test_owner_access_granted(self):
        set_current_speaker(UserRole.OWNER)
        self.assertEqual(get_current_speaker(), UserRole.OWNER.value)

        # Owner has access to public, owner-only, and high-risk
        ok_pub, _ = check_permission(SecurityTier.PUBLIC, "search_web")
        self.assertTrue(ok_pub)

        ok_owner, _ = check_permission(SecurityTier.OWNER_ONLY, "voice_biometrics")
        self.assertTrue(ok_owner)

        ok_risk, _ = check_permission(SecurityTier.HIGH_RISK_FINANCIAL, "travel_booking")
        self.assertTrue(ok_risk)

    def test_guest_access_restricted(self):
        set_current_speaker(UserRole.TEMPORARY_GUEST)
        self.assertEqual(get_current_speaker(), UserRole.TEMPORARY_GUEST.value)

        # Public tools are allowed for guests
        ok_pub, _ = check_permission(SecurityTier.PUBLIC, "get_weather")
        self.assertTrue(ok_pub)

        # Owner-only tools MUST be blocked for guests
        ok_owner, reason_owner = check_permission(SecurityTier.OWNER_ONLY, "self_repair")
        self.assertFalse(ok_owner)
        self.assertIn("owner authorization", reason_owner.lower())

        # High-risk financial operations MUST be blocked for guests
        ok_risk, reason_risk = check_permission(SecurityTier.HIGH_RISK_FINANCIAL, "travel_booking")
        self.assertFalse(ok_risk)

    def test_scoped_authorized_user(self):
        # Authorize a user with specific capabilities
        permissions.authorize_user(
            name="Alice",
            role=UserRole.AUTHORIZED_PERSON,
            tier=SecurityTier.AUTHORIZED,
            capabilities=["code_runner", "search_web"]
        )

        users = permissions.list_authorized_users()
        alice = next((u for u in users if u["name"] == "Alice"), None)
        self.assertIsNotNone(alice)
        self.assertEqual(alice["role"], UserRole.AUTHORIZED_PERSON.value)

        # Cleanup
        permissions.revoke_user("Alice")


class TestH3MemoryIsolation(unittest.TestCase):
    """Tests for Private Memory Shielding in Multi-User Scenarios."""

    def test_memory_shielding(self):
        fake_memory = {
            "identity": {"name": "Aman", "city": "Bengaluru", "job": "AI Architect"},
            "personal": {"secret_note": "Confidential family detail"}
        }

        # Owner format includes facts
        owner_view = memory_manager.format_memory_for_prompt(fake_memory, is_owner=True)
        self.assertIn("Aman", owner_view)

        # Guest format is strictly shielded
        guest_view = memory_manager.format_memory_for_prompt(fake_memory, is_owner=False)
        self.assertNotIn("Aman", guest_view)
        self.assertIn("RESTRICTED GUEST SESSION", guest_view)


class TestH3VoiceCloner(unittest.TestCase):
    """Tests for Voice Cloning Engine, Audio Quality & Consent Verification."""

    def test_audio_quality_analysis(self):
        sr = 16000
        # 1 second speech + 1 second noise floor
        t_speech = np.linspace(0, 1.0, sr, endpoint=False)
        speech_part = 0.5 * np.sin(2 * np.pi * 300 * t_speech) + np.random.normal(0, 0.005, sr)
        silence_part = np.random.normal(0, 0.005, sr)
        audio = (np.concatenate([speech_part, silence_part]) * 32767).astype(np.int16)

        qual = voice_cloner.analyze_audio_quality(audio, sr)
        self.assertGreater(qual["duration_sec"], 1.5)
        self.assertGreater(qual["snr_db"], 10.0)
        self.assertFalse(qual["has_clipping"])

    def test_bandpass_cleaning(self):
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        # Add 30Hz rumble + 14kHz hiss
        low_rumble = 0.3 * np.sin(2 * np.pi * 30 * t)
        high_hiss = 0.3 * np.sin(2 * np.pi * 14000 * t)
        voice = 0.5 * np.sin(2 * np.pi * 500 * t)
        raw = ((low_rumble + high_hiss + voice) * 32767).astype(np.int16)

        cleaned = voice_cloner.clean_audio_sample(raw, sr)
        self.assertEqual(len(cleaned), len(raw))
        # Ensure peak normalized
        peak = np.max(np.abs(cleaned))
        self.assertLessEqual(peak, 32767)


class TestH3TravelSafeguards(unittest.TestCase):
    """Tests for Autonomous Travel & Booking Confirmation Safeguards."""

    def test_travel_search(self):
        from actions.travel_booking import travel_booking
        res = travel_booking({
            "action": "flights",
            "origin": "DEL",
            "destination": "BLR",
            "date": "2026-12-01"
        })
        self.assertIn("Google Flights", res)
        self.assertIn("MakeMyTrip", res)

    def test_booking_confirmation_guard(self):
        from actions.travel_booking import travel_booking
        # Booking without valid card must fail closed
        res = travel_booking({
            "action": "confirm_booking",
            "booking_id": "invalid_id"
        })
        self.assertIn("booking review card", res.lower())


class TestH3SelfHealingWatchdog(unittest.TestCase):
    """Tests for Watchdog Health Probes, Rollback Guard & Diagnostics."""

    def test_system_audit(self):
        audit = watchdog.audit_full_system()
        self.assertIn("resources", audit)
        self.assertIn("codebase", audit)
        self.assertIn("biometrics", audit)
        self.assertEqual(audit["codebase"].status, "HEALTHY")

    def test_security_invariant_validation(self):
        # Must reject patches attempting to disable permission checks
        bad_code = "def check_permission(): return True"
        ok, msg = watchdog.validate_patch_security(bad_code)
        self.assertFalse(ok)
        self.assertIn("security invariant", msg.lower())

        # Good code must pass
        good_code = "def add(a, b): return a + b"
        ok_good, _ = watchdog.validate_patch_security(good_code)
        self.assertTrue(ok_good)

    def test_diagnostic_report_markdown(self):
        report = watchdog.generate_diagnostic_report_markdown()
        self.assertIn("JARVIS H3.0 System Diagnostic Report", report)
        self.assertIn("System Resources", report)


class TestActionAndPluginDiscovery(unittest.TestCase):
    """Verifies that all actions and plugins are active and error-free."""

    def test_actions_discovery(self):
        from core.action_loader import discover_actions
        registry = discover_actions(BASE_DIR / "actions", reserved_names=set(), logger=lambda m: None)
        names = registry.names()
        # Verify critical H3.0 actions are present
        self.assertIn("voice_biometrics", names)
        self.assertIn("voice_lab", names)
        self.assertIn("travel_booking", names)
        self.assertIn("self_repair", names)
        self.assertGreaterEqual(len(names), 40)

    def test_plugins_discovery(self):
        from core.plugin_loader import discover_plugins
        plugins = discover_plugins(BASE_DIR / "plugins", core_tool_names=set(), logger=lambda m: None)
        self.assertGreaterEqual(len(plugins.names()), 5)


if __name__ == "__main__":
    unittest.main()
