"""
Unit & Integration Tests for JARVIS H3.2 Anime Entertainment Controller
"""

import os
import json
import unittest
from pathlib import Path
from core.anime_controller import AnimeController, get_anime_controller
from actions.anime_control import anime_control_handler, TOOL


class TestAnimeController(unittest.TestCase):

    def setUp(self):
        self.controller = get_anime_controller()
        self.test_history_path = Path("memory/anime_history.json")

    def test_01_tool_declaration(self):
        self.assertEqual(TOOL["name"], "anime_control")
        self.assertIn("query", TOOL["parameters"]["properties"])
        self.assertIn("action", TOOL["parameters"]["properties"])
        self.assertTrue(callable(TOOL["handler"]))

    def test_02_popular_anime_search(self):
        results = self.controller.search("Naruto", limit=5)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["title"], "Naruto")
        self.assertEqual(results[0]["episodes"], 220)
        self.assertEqual(results[0]["status"], "Finished")

    def test_03_get_episodes_listing(self):
        ep_data = self.controller.get_episodes("Naruto")
        self.assertEqual(ep_data["title"], "Naruto")
        self.assertEqual(ep_data["total_episodes"], 220)
        self.assertTrue(len(ep_data["sample_episodes"]) > 0)
        self.assertTrue(len(ep_data.get("seasons", [])) >= 4)

    def test_04_voice_command_parsing_english(self):
        parsed = self.controller.parse_voice_command("Play Naruto episode 5")
        self.assertEqual(parsed["action"], "play")
        self.assertEqual(parsed["title"], "Naruto")
        self.assertEqual(parsed["episode"], 5)
        self.assertFalse(parsed["dub"])

    def test_05_voice_command_parsing_hindi_hinglish(self):
        parsed = self.controller.parse_voice_command("mere liye One Piece chalao dub mein")
        self.assertEqual(parsed["action"], "play")
        self.assertIn("One Piece", parsed["title"])
        self.assertTrue(parsed["dub"])

    def test_06_voice_command_episodes_intent(self):
        parsed = self.controller.parse_voice_command("search Naruto and show me available episodes")
        self.assertEqual(parsed["action"], "episodes")
        self.assertIn("naruto", parsed["query"].lower())

    def test_07_action_handler_episodes(self):
        res = anime_control_handler({"query": "Naruto", "action": "episodes"})
        self.assertIn("220 episodes available", res)
        self.assertIn("Finished", res)

    def test_08_history_lifecycle(self):
        self.controller.clear_history()
        self.assertEqual(len(self.controller.get_history()), 0)


if __name__ == "__main__":
    unittest.main()
