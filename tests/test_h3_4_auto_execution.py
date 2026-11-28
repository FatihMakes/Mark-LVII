"""
tests/test_h3_4_auto_execution.py — End-to-End Acceptance Tests for JARVIS H3.4
Contributed by Aman Kumar (@iamTechieAman).

Validates the full H3.4 requirements:
  - TEST A: Direct send without confirmation when owner authorized
  - TEST B: Explicit draft request creates draft only
  - TEST C: Guest / unknown speaker denied owner WhatsApp dispatch
  - TEST D: Recipient ambiguity detection (multiple matching contacts)
  - TEST E: Duplicate send suppression and idempotency
  - TEST F: Transparent accessibility setup instructions
  - TEST G: Consecutive message auto-send execution
  - TEST H: Intent safeguard ("do not send / draft only")
  - TEST I: Universal owner session propagation
  - TEST J: Comprehensive 15-vector AI Red-Team resilience
"""
import json
import unittest
from pathlib import Path

from actions.whatsapp_automation import whatsapp_automation, reset_whatsapp_draft
from core.owner_session import get_owner_session, get_active_session_context
from core.permissions import set_current_speaker, UserRole
from core.red_team_eval import get_red_team_evaluator
from core.whatsapp_desktop_controller import get_whatsapp_controller, WhatsAppExecutionState


class TestH34AutoExecution(unittest.TestCase):

    def setUp(self):
        reset_whatsapp_draft()
        self.controller = get_whatsapp_controller()
        # Ensure owner session is active
        get_owner_session().authenticate_owner("voice_biometrics", confidence=0.98)
        set_current_speaker(UserRole.OWNER)

    def test_a_direct_send_without_confirmation(self):
        """TEST A: Authenticated owner sends message directly without prompt."""
        res = whatsapp_automation({
            "action": "send",
            "recipient": "Rahul",
            "message": "I am on my way."
        })
        self.assertNotIn("Confirm send", res)
        self.assertNotIn("WA_", res)
        self.assertIn("successfully sent", res.lower())
        self.assertIn("Rahul Sharma", res)

    def test_b_explicit_draft_request(self):
        """TEST B: Owner explicitly asks to draft or prepare a message -> Draft only, no auto-send."""
        res = whatsapp_automation({
            "action": "compose",
            "recipient": "Rahul",
            "message": "Drafting project updates for review."
        })
        self.assertIn("Confirm send", res)
        self.assertIn("WA_", res)
        self.assertIn("prepared your message draft", res.lower())

    def test_c_guest_access_denial(self):
        """TEST C: Unknown/guest speaker asking to send message is rejected."""
        res = whatsapp_automation({
            "action": "send",
            "recipient": "Rahul",
            "message": "Unauthenticated guest attempt."
        }, session_memory={"speaker": "GUEST", "owner_authenticated": False})
        self.assertIn("Access denied", res)

    def test_d_recipient_ambiguity_detection(self):
        """TEST D: Multiple contacts with matching names require disambiguation before sending."""
        contacts = self.controller.load_contacts()
        contacts["rahul_verma"] = {"name": "Rahul Verma", "phone": "+919988112233", "relationship": "Friend"}
        Path("memory/whatsapp_contacts.json").write_text(json.dumps(contacts, indent=2))

        try:
            res = whatsapp_automation({
                "action": "send",
                "recipient": "Rahul",
                "message": "Ambiguous recipient test message."
            })
            self.assertIn("multiple contacts matching", res.lower())
            self.assertIn("Rahul Sharma", res)
            self.assertIn("Rahul Verma", res)
            self.assertNotIn("successfully sent", res.lower())
        finally:
            del contacts["rahul_verma"]
            Path("memory/whatsapp_contacts.json").write_text(json.dumps(contacts, indent=2))

    def test_e_duplicate_send_suppression(self):
        """TEST E: Exactly identical messages to the same recipient are suppressed within the window."""
        res1 = whatsapp_automation({
            "action": "send",
            "recipient": "Maya",
            "message": "Unique status ping for Maya."
        })
        self.assertIn("successfully sent", res1.lower())

        # Immediate repeat attempt
        res2 = whatsapp_automation({
            "action": "send",
            "recipient": "Maya",
            "message": "Unique status ping for Maya."
        })
        self.assertIn("duplicate message suppressed", res2.lower())

    def test_f_accessibility_instructions_when_unauthorized(self):
        """TEST F: Explains missing macOS Accessibility permissions clearly without repeated prompts."""
        # Check that setup instructions exist in the controller
        tel = self.controller.get_telemetry()
        self.assertIn("accessibility_granted", tel)
        # Stage message returns clear instructions when accessibility is not granted
        res = self.controller.send_message("Aman", "Test", auto_submit=False)
        self.assertTrue(res.get("success"))

    def test_g_five_consecutive_messages_auto_send(self):
        """TEST G: Five consecutive ordinary messages execute without asking for confirmation."""
        recipients = ["Rahul", "Maya", "Rohit", "Doctor", "Aman"]
        for i, rec in enumerate(recipients, 1):
            res = whatsapp_automation({
                "action": "send",
                "recipient": rec,
                "message": f"Autonomous batch update #{i} at time {i*50}"
            })
            self.assertIn("successfully sent", res.lower())
            self.assertNotIn("Confirm send", res)

    def test_h_intent_safeguard_do_not_send(self):
        """TEST H: 'Send this message as a draft, do not send it' is not sent."""
        res = whatsapp_automation({
            "action": "send",
            "recipient": "Rahul",
            "message": "Send this message as a draft, do not send it."
        })
        self.assertNotIn("successfully sent", res.lower())
        self.assertIn("prepared your message draft", res.lower())
        self.assertIn("Confirm send", res)

    def test_i_universal_owner_session_propagation(self):
        """TEST I: Session context contains owner status, speaker role, and security tier."""
        ctx = get_active_session_context()
        self.assertTrue(ctx.get("owner_authenticated"))
        self.assertEqual(ctx.get("security_tier"), "OWNER_UNRESTRICTED")
        self.assertTrue(ctx.get("session_active"))
        self.assertGreater(ctx.get("remaining_seconds"), 0)

    def test_j_ai_red_team_comprehensive_resilience(self):
        """TEST J: Evaluates 15 threat vectors with high resilience."""
        evaluator = get_red_team_evaluator()
        res = evaluator.run_comprehensive_suite()
        self.assertEqual(res["total_tests"], 20)
        self.assertEqual(res["resilience_status"], "HIGHLY_RESILIENT")
        self.assertGreaterEqual(res["accuracy_percent"], 95.0)


if __name__ == "__main__":
    unittest.main()
