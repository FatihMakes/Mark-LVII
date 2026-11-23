"""
Unit & Integration Tests for JARVIS H3.2 Owner Session & Persistent Authorization
"""

import time
import unittest
from core.owner_session import OwnerSessionManager, get_owner_session
from core.permissions import (
    check_permission,
    set_current_speaker,
    get_current_speaker,
    UserRole,
    SecurityTier
)


class TestOwnerSession(unittest.TestCase):

    def setUp(self):
        self.mgr = get_owner_session()
        self.mgr.revoke_session()

    def test_01_session_lifecycle(self):
        self.assertFalse(self.mgr.is_owner_session_active())
        self.mgr.authenticate_owner("TEST_BIOMETRIC")
        self.assertTrue(self.mgr.is_owner_session_active())
        self.assertEqual(self.mgr.current_auth_method, "TEST_BIOMETRIC")
        self.mgr.revoke_session()
        self.assertFalse(self.mgr.is_owner_session_active())

    def test_02_pin_hashing_and_verification(self):
        # Set a test PIN
        self.mgr.set_pin("4321")
        self.assertTrue(self.mgr.verify_pin("4321"))
        self.assertFalse(self.mgr.verify_pin("0000"))
        self.assertFalse(self.mgr.verify_pin("1170"))  # Old hardcoded PIN must fail

    def test_03_rate_limiting_on_repeated_wrong_pins(self):
        self.mgr.set_pin("9999")
        # Fail 5 times
        for _ in range(5):
            self.mgr.verify_pin("wrong")
        self.assertTrue(self.mgr.is_locked_out())
        # Even correct PIN rejected when locked out
        self.assertFalse(self.mgr.verify_pin("9999"))
        self.mgr.clear_lockout()
        self.assertFalse(self.mgr.is_locked_out())

    def test_04_permissions_integration_with_active_session(self):
        # With active session, normal and owner-only actions execute without repetitive prompts
        self.mgr.authenticate_owner("VOICE_PRINT")
        set_current_speaker(UserRole.OWNER)
        
        allowed, reason = check_permission(SecurityTier.OWNER_ONLY, "document_studio")
        self.assertTrue(allowed)
        self.assertIn("Owner", reason)

    def test_05_risk_gated_execution(self):
        # Normal actions execute directly
        self.mgr.authenticate_owner("VOICE_PRINT")
        can_exec, msg = self.mgr.gate_operation("open_app", is_sensitive=False)
        self.assertTrue(can_exec)

        # Sensitive financial/system-wipe requires step-up
        can_exec_sens, msg_sens = self.mgr.gate_operation("ai_trading", is_sensitive=True)
        self.assertFalse(can_exec_sens)
        self.assertIn("Step-up", msg_sens)


if __name__ == "__main__":
    unittest.main()
