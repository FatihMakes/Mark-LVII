"""
tests/test_h3_3_whatsapp.py — Tests for WhatsApp Desktop Integration
"""
import unittest
from core.whatsapp_desktop_controller import get_whatsapp_controller
from actions.whatsapp_automation import whatsapp_automation


class TestWhatsAppDesktop(unittest.TestCase):

    def setUp(self):
        self.controller = get_whatsapp_controller()

    def test_installed_telemetry(self):
        tel = self.controller.get_telemetry()
        self.assertIn("installed", tel)
        self.assertIn("running", tel)
        self.assertIn("contacts_count", tel)
        self.assertTrue(tel["installed"])  # Verified /Applications/WhatsApp.app exists on this Mac

    def test_contact_resolution(self):
        c = self.controller.resolve_contact("aman")
        self.assertIsNotNone(c)
        self.assertEqual(c["name"], "Aman Kumar")

        # Direct number
        c_num = self.controller.resolve_contact("+919876543210")
        self.assertIsNotNone(c_num)

    def test_automation_action_status(self):
        res = whatsapp_automation({"action": "status"})
        self.assertIn("WhatsApp Desktop is installed", res)

    def test_automation_action_contacts(self):
        res = whatsapp_automation({"action": "contacts"})
        self.assertIn("saved WhatsApp contacts", res)

    def test_compose_draft(self):
        res = whatsapp_automation({
            "action": "compose",
            "recipient": "Aman",
            "message": "System test automated dispatch."
        })
        self.assertIn("Confirm send WA_", res)


if __name__ == "__main__":
    unittest.main()
