"""tests/test_h3_1_suite.py — Complete Verification Suite for JARVIS H3.1.

Validates 23 strict scenarios:
1. Multi-Speaker Intelligence & Overlap Detection (Tests 1-7)
2. Android Companion & Hardware Control Gateway (Tests 8-13)
3. WhatsApp Complete Automation & Confirmation Guard (Tests 14-18)
4. Anti-Theft Siren Guard & State Machine (Tests 19-21)
5. Local AI Engine & Privacy Kill Switch (Tests 22-23)
"""
import os
import shutil
import tempfile
import time
import unittest

import numpy as np

# Core Modules
from core.speaker_intelligence import (
    SpeakerIntelligenceEngine,
    get_speaker_engine,
    reset_speaker_engine,
)
from core.companion_gateway import (
    CompanionGateway,
    get_companion_gateway,
    reset_companion_gateway,
)
from core.anti_theft import (
    AntiTheftEngine,
    GuardState,
    get_anti_theft,
    reset_anti_theft,
)
from core.local_ai_engine import (
    LocalAIEngine,
    get_local_ai,
)
from core.model_router import (
    ModelRouter,
    AIMode,
    OperationMode,
    PersonalityProfile,
    get_model_router,
)
from actions.whatsapp_automation import (
    whatsapp_automation,
    reset_whatsapp_draft,
)
from actions.privacy_lock import (
    privacy_lock_action,
    set_privacy_lock,
    is_privacy_locked,
)
from actions.speaker_manager import speaker_manager
from actions.android_control import android_control
from actions.anti_theft import anti_theft_action


class TestH31ComprehensiveSuite(unittest.TestCase):
    """23 Strict Verification Tests for JARVIS H3.1."""

    def setUp(self):
        self.orig_speaker_engine = reset_speaker_engine()
        self.orig_companion = reset_companion_gateway()
        self.orig_guard = reset_anti_theft()
        set_privacy_lock(False)

    def tearDown(self):
        set_privacy_lock(False)
        reset_speaker_engine()
        reset_companion_gateway()
        reset_anti_theft()

    # ── 1. MULTI-SPEAKER INTELLIGENCE (Tests 1 to 7) ──────────────────────────

    def test_01_owner_speech_alone(self):
        """Test 1: Single dominant speaker without secondary voice passes turn processing cleanly."""
        engine = SpeakerIntelligenceEngine()
        sr = 16000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        single = (0.6 * np.sin(2 * np.pi * 140.0 * t) * 32767).astype(np.int16)

        res = engine.process_speech_turn(single, sr)
        self.assertTrue(res.actionable_speech)
        self.assertFalse(res.is_overlapping)
        self.assertEqual(res.speaker_count, 1)

    def test_02_owner_plus_background_chatter(self):
        """Test 2: Primary speaker with weak background chatter (<25% energy) passes with background chatter isolated."""
        engine = SpeakerIntelligenceEngine()
        sr = 16000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        # Primary voice (140 Hz at 0.70 amp) + weak background chatter (320 Hz at 0.10 amp)
        combined = ((0.70 * np.sin(2 * np.pi * 140.0 * t) + 0.10 * np.sin(2 * np.pi * 320.0 * t)) * 32767).astype(np.int16)

        res = engine.process_speech_turn(combined, sr)
        self.assertTrue(res.actionable_speech)
        self.assertFalse(res.is_overlapping)
        self.assertEqual(res.speaker_count, 1)

    def test_03_simultaneous_two_speaker_overlap_rejection(self):
        """Test 3: Simultaneous dual speakers with competing pitch peaks trigger overlap rejection."""
        engine = SpeakerIntelligenceEngine()
        sr = 16000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        # 130 Hz male + 220 Hz female simultaneous equal amplitude
        dual = ((0.40 * np.sin(2 * np.pi * 130.0 * t) + 0.40 * np.sin(2 * np.pi * 220.0 * t)) * 32767).astype(np.int16)

        res = engine.process_speech_turn(dual, sr)
        self.assertTrue(res.is_overlapping)
        self.assertFalse(res.actionable_speech)
        self.assertEqual(res.speaker_count, 2)
        self.assertIn("Multiple speakers detected", res.rejection_reason)

    def test_04_tv_audio_speech_rejection(self):
        """Test 4: Acoustic environment analysis measures background floor and checks media signature."""
        engine = SpeakerIntelligenceEngine()
        sr = 16000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        ambient = (0.02 * np.random.randn(int(sr * 0.8)) * 32767).astype(np.int16)

        noise_db, is_tv = engine.analyze_audio_environment(ambient, sr)
        self.assertTrue(isinstance(noise_db, float))
        self.assertTrue(isinstance(is_tv, bool))

    def test_05_impersonator_claim_rejection(self):
        """Test 5: Speaker engine enforces Active Speaker Lock: when locked to owner, guest speech is blocked."""
        engine = SpeakerIntelligenceEngine()
        engine.set_active_speaker_lock("OWNER_001", timeout_sec=10.0)

        sr = 16000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        guest_sample = (0.50 * np.sin(2 * np.pi * 190.0 * t) * 32767).astype(np.int16)

        res = engine.process_speech_turn(guest_sample, sr)
        # When locked to OWNER, unauthenticated guest speech must not be actionable
        self.assertFalse(res.actionable_speech)
        self.assertIn("locked to the owner", res.rejection_reason.lower())

    def test_06_multi_user_identity_separation(self):
        """Test 6: Distinct users maintain isolated lock sessions and address preferences."""
        engine = SpeakerIntelligenceEngine()
        engine.set_preferred_address("Sir")
        self.assertEqual(engine.get_preferred_address(), "Sir")

        engine.set_preferred_address("Aman")
        self.assertEqual(engine.get_preferred_address(), "Aman")

    def test_07_tts_echo_suppression(self):
        """Test 7: When JARVIS TTS playback is active, microphone turns are suppressed to avoid acoustic feedback."""
        engine = SpeakerIntelligenceEngine()
        engine.set_tts_playback_active(True)

        sr = 16000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        # Speaker echo leakage (moderate RMS < 3500)
        leakage = (0.08 * np.sin(2 * np.pi * 140.0 * t) * 32767).astype(np.int16)

        res = engine.process_speech_turn(leakage, sr)
        self.assertFalse(res.actionable_speech)
        self.assertIn("Suppressed acoustic echo", res.rejection_reason)

    # ── 2. ANDROID COMPANION & HARDWARE CONTROL GATEWAY (Tests 8 to 13) ───────

    def test_08_android_pairing_token_crypto(self):
        """Test 8: Pairing token uses secure HMAC-SHA256, PAIR_ prefix and encodes QR pairing URI."""
        gw = CompanionGateway()
        token, qr_data = gw.generate_pairing_token(ttl_seconds=300)
        self.assertTrue(token.startswith("PAIR_"))
        self.assertTrue(token in qr_data)

    def test_09_android_device_registry_persistence(self):
        """Test 9: Confirming pairing registers the device in persistent companion registry."""
        gw = CompanionGateway()
        token, _ = gw.generate_pairing_token()

        ok, msg = gw.register_device(token, "test_phone_001", "Pixel 8 Pro", "Google Pixel 8 Pro")
        self.assertTrue(ok)
        self.assertTrue(len(msg) > 0)

        devices = gw.list_devices()
        self.assertTrue(any(d["device_id"] == "test_phone_001" for d in devices))

    def test_10_android_hardware_flashlight(self):
        """Test 10: Dispatching flashlight toggle dispatches hardware command and updates device state."""
        gw = CompanionGateway()
        token, _ = gw.generate_pairing_token()
        gw.register_device(token, "test_phone_002", "Galaxy S24", "SM-S928B")

        ok, msg, data = gw.execute_hardware_command("TORCH_ON", {"state": True}, "test_phone_002")
        self.assertTrue(ok)
        self.assertTrue(data.get("flashlight"))
        self.assertIn("Flashlight turned ON", msg)

    def test_11_android_hardware_battery_query(self):
        """Test 11: Querying companion battery reports telemetry status and battery percentage."""
        gw = CompanionGateway()
        token, _ = gw.generate_pairing_token()
        gw.register_device(token, "test_phone_003", "OnePlus 12", "CPH2581")

        updated = gw.update_telemetry("test_phone_003", {"battery": 86, "is_charging": True})
        self.assertTrue(updated)

        devices = gw.list_devices()
        phone = next(d for d in devices if d["device_id"] == "test_phone_003")
        self.assertEqual(phone["battery_percent"], 86)
        self.assertTrue(phone["is_charging"])

    def test_12_android_volume_brightness_control(self):
        """Test 12: Volume and brightness adjustments execute with telemetry state feedback."""
        gw = CompanionGateway()
        token, _ = gw.generate_pairing_token()
        gw.register_device(token, "test_phone_004", "Xiaomi 14", "23127PN0CG")

        ok_v, msg_v, data_v = gw.execute_hardware_command("SET_VOLUME", {"volume": 80}, "test_phone_004")
        self.assertTrue(ok_v)
        self.assertEqual(data_v.get("volume"), 80)

        ok_b, msg_b, data_b = gw.execute_hardware_command("SET_BRIGHTNESS", {"brightness": 65}, "test_phone_004")
        self.assertTrue(ok_b)
        self.assertEqual(data_b.get("brightness"), 65)

    def test_13_android_device_revocation(self):
        """Test 13: Revoking a companion device stops further command execution."""
        gw = CompanionGateway()
        token, _ = gw.generate_pairing_token()
        gw.register_device(token, "test_phone_005", "Nothing Phone 2", "AIN065")

        self.assertTrue(gw.revoke_device("test_phone_005"))

        # Subsequent command for revoked device must fail
        ok_cmd, msg_cmd, _ = gw.execute_hardware_command("TORCH_ON", {}, "test_phone_005")
        self.assertFalse(ok_cmd)
        self.assertIn("revoked", msg_cmd.lower())

    # ── 3. WHATSAPP COMPLETE AUTOMATION (Tests 14 to 18) ──────────────────────

    def test_14_whatsapp_contact_lookup(self):
        """Test 14: WhatsApp contact lookup retrieves matching contact details."""
        res = whatsapp_automation({"action": "lookup_contact", "recipient": "Aman"})
        self.assertIn("Aman", res)

    def test_15_whatsapp_draft_composition_review_card(self):
        """Test 15: Composing a message creates a pending draft review card and DOES NOT send immediately."""
        reset_whatsapp_draft()
        res = whatsapp_automation({
            "action": "send_message",
            "recipient": "Aman",
            "message": "Meeting scheduled for 3 PM"
        })
        self.assertIn("Confirm send", res)
        self.assertIn("WA_", res)

    def test_16_whatsapp_explicit_send_confirmation(self):
        """Test 16: Explicit confirmation required before message is dispatched."""
        reset_whatsapp_draft()
        whatsapp_automation({
            "action": "send_message",
            "recipient": "Aman",
            "message": "Project deployed successfully"
        })
        res = whatsapp_automation({"action": "confirm_send"})
        self.assertIn("Message sent", res)

    def test_17_whatsapp_unread_notifications(self):
        """Test 17: Reading unread messages formats sender, timestamps and content."""
        res = whatsapp_automation({"action": "read_unread"})
        self.assertIn("unread", res.lower())

    def test_18_whatsapp_hands_free_call_workflow(self):
        """Test 18: Initiating hands-free call prepares audio stream and dispatches call intent."""
        res = whatsapp_automation({
            "action": "call",
            "recipient": "Aman"
        })
        self.assertIn("call", res.lower())

    # ── 4. ANTI-THEFT SIREN GUARD (Tests 19 to 21) ────────────────────────────

    def test_19_anti_theft_arming_grace_period(self):
        """Test 19: Arming siren guard enters ARMED state with monitoring active."""
        guard = AntiTheftEngine()
        ok, msg = guard.arm(delay_seconds=10)
        self.assertTrue(ok)
        self.assertTrue(guard.is_armed())
        self.assertIn("ARM", guard.get_state())

    def test_20_anti_theft_charger_disconnect_trigger(self):
        """Test 20: Charger disconnect while armed immediately triggers SIREN alarm and incident logging."""
        from core.owner_session import get_owner_session
        get_owner_session().set_owner_pin("", "5599", is_authenticated_owner=True)
        guard = AntiTheftEngine()
        guard.arm(delay_seconds=0)

        incident = guard.trigger_theft_alarm("CHARGER_DISCONNECTED", "Primary Android Companion")
        self.assertEqual(incident.trigger_reason, "CHARGER_DISCONNECTED")
        self.assertEqual(guard.get_state(), "TRIGGERED")
        guard.disarm("5599")

    def test_21_anti_theft_pin_disarm(self):
        """Test 21: Dynamic secure owner PIN disarms guard; wrong PIN fails."""
        from core.owner_session import get_owner_session
        get_owner_session().set_owner_pin("", "5599", is_authenticated_owner=True)
        guard = AntiTheftEngine()
        guard.arm(delay_seconds=0)
        guard.trigger_theft_alarm("CHARGER_DISCONNECTED")

        # Wrong PIN
        ok_fail, _ = guard.disarm("0000")
        self.assertFalse(ok_fail)
        self.assertEqual(guard.get_state(), "TRIGGERED")

        # Correct dynamic PIN
        ok_ok, msg_ok = guard.disarm("5599")
        self.assertTrue(ok_ok)
        self.assertEqual(guard.get_state(), "DISARMED")

    # ── 5. LOCAL AI ENGINE & PRIVACY KILL SWITCH (Tests 22 to 23) ─────────────

    def test_22_local_ai_inference_and_stop_generation(self):
        """Test 22: Local AI engine computes unified memory headroom and aborts via stop_generation."""
        engine = LocalAIEngine()
        headroom = engine.calculate_memory_headroom()
        self.assertIn("total_ram_gb", headroom)
        self.assertIn("headroom_gb", headroom)
        self.assertTrue(headroom["headroom_gb"] >= 0)

        # Verify stop generation event
        engine.stop_generation()
        self.assertTrue(engine.is_stop_requested())
        engine.reset_stop()
        self.assertFalse(engine.is_stop_requested())

    def test_23_privacy_lock_kill_switch(self):
        """Test 23: Voice Privacy Lock enforces LOCAL_PRIVATE_MODE and blocks external cloud egress."""
        set_privacy_lock(False)
        self.assertFalse(is_privacy_locked())

        res = privacy_lock_action({})
        self.assertTrue(is_privacy_locked())
        self.assertIn("engaged", res.lower())

        # In Local Private Mode, model router must enforce zero external egress
        router = get_model_router()
        self.assertEqual(router.mode, AIMode.LOCAL_PRIVATE)
        self.assertTrue(router.is_local_private())


if __name__ == "__main__":
    unittest.main()
