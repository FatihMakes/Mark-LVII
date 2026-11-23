"""
Unit & Integration Tests for JARVIS H3.2 UI Actions & Creator Intelligence
"""

import unittest
from actions.creator_info import creator_info_handler, TOOL as CREATOR_TOOL
from actions.anime_control import anime_control_handler
from actions.google_maps import google_maps_handler
from actions.mac_scan import mac_scan_handler
from core.permissions import check_permission, SecurityTier


class MockPlayer:
    """Simulates thread-safe JarvisUI player object."""
    def __init__(self):
        self.logs = []
        self.contents = []

    def write_log(self, text: str):
        self.logs.append(text)

    def show_content(self, title: str, text: str):
        self.contents.append((title, text))


class TestH32UIActions(unittest.TestCase):

    def setUp(self):
        self.player = MockPlayer()

    def test_01_creator_info_tool(self):
        self.assertEqual(CREATOR_TOOL["name"], "creator_info")
        res = creator_info_handler({"topic": "identity"}, player=self.player)
        self.assertIn("Aman Kumar", res)
        self.assertIn("@iamTechieAman", res)
        self.assertTrue(len(self.player.logs) > 0)
        self.assertTrue(len(self.player.contents) > 0)

    def test_02_anime_control_thread_safety(self):
        res = anime_control_handler({"query": "Naruto", "action": "episodes"}, player=self.player)
        self.assertIn("Naruto", res)
        self.assertTrue(any("Anime" in log for log in self.player.logs))

    def test_03_mac_scan_thread_safety(self):
        res = mac_scan_handler({"mode": "audit"}, player=self.player)
        self.assertIn("System audit complete", res)
        self.assertTrue(any("System" in log for log in self.player.logs))

    def test_04_permission_security_tiers(self):
        # Verify that H3.2 actions are properly mapped in permissions
        allowed_anime, _ = check_permission(SecurityTier.PUBLIC, "anime_control")
        self.assertTrue(allowed_anime)

        allowed_maps, _ = check_permission(SecurityTier.PUBLIC, "google_maps")
        self.assertTrue(allowed_maps)

        allowed_creator, _ = check_permission(SecurityTier.PUBLIC, "creator_info")
        self.assertTrue(allowed_creator)


if __name__ == "__main__":
    unittest.main()
