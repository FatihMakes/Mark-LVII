"""
Unit & Integration Tests for JARVIS H3.2 Google Maps Engine
"""

import os
import unittest
from core.google_maps_engine import GoogleMapsEngine, get_maps_engine
from actions.google_maps import google_maps_handler, TOOL


class TestGoogleMapsEngine(unittest.TestCase):

    def setUp(self):
        self.engine = get_maps_engine()

    def test_01_tool_declaration(self):
        self.assertEqual(TOOL["name"], "google_maps")
        self.assertIn("command", TOOL["parameters"]["properties"])
        self.assertIn("origin", TOOL["parameters"]["properties"])
        self.assertIn("destination", TOOL["parameters"]["properties"])

    def test_02_missing_key_behavior(self):
        # Explicit engine with empty key must not crash, must return clear error
        engine_no_key = GoogleMapsEngine(api_key="")
        res = engine_no_key.geocode("1600 Amphitheatre Parkway, Mountain View, CA")
        self.assertEqual(res["status"], "config_error")
        self.assertIn("GOOGLE_MAPS_API_KEY", res["error"])

    def test_03_handler_directions_missing_key_clean_reply(self):
        # Handler must report status cleanly without traceback
        engine_no_key = GoogleMapsEngine(api_key="")
        res = google_maps_handler({"command": "directions", "origin": "SF", "destination": "Oakland"})
        self.assertTrue("unavailable" in res.lower() or "route" in res.lower())

    def test_04_directions_mode_validation(self):
        # Must handle invalid mode gracefully
        engine = GoogleMapsEngine(api_key="TEST_MOCK_KEY")
        # Should not raise exception
        res = engine.directions("A", "B", mode="INVALID_FLIGHT_MODE")
        self.assertIn("status", res)

    def test_05_reverse_geocode_input_guard(self):
        engine = GoogleMapsEngine(api_key="")
        res = engine.reverse_geocode("37.422,-122.084")
        self.assertEqual(res["status"], "config_error")

    def test_06_timezone_input_guard(self):
        engine = GoogleMapsEngine(api_key="")
        res = engine.timezone("35.6585,139.7454")
        self.assertEqual(res["status"], "config_error")


if __name__ == "__main__":
    unittest.main()
