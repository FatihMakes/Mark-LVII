"""
tests/test_h3_3_instagram.py — Tests for Instagram Reels Controller
"""
import unittest
from core.instagram_controller import InstagramController, get_instagram_controller
from actions.instagram_control import instagram_control


class TestInstagramReels(unittest.TestCase):

    def test_controller_initialization(self):
        controller = InstagramController(headless=True)
        self.assertFalse(controller._is_active)
        tel = controller.get_telemetry()
        self.assertFalse(tel.get("active", False))

    def test_action_unknown(self):
        res = instagram_control({"action": "status"})
        self.assertIn("No Instagram session", res)

    def test_action_info_help(self):
        res = instagram_control({"action": "invalid_xyz"})
        self.assertIn("Supported actions", res)


if __name__ == "__main__":
    unittest.main()
