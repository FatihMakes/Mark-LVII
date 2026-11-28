"""
tests/test_whatsapp_file_and_browser.py — Comprehensive Unit Tests for WhatsApp File Sending,
Browser Autonomous Agent, and Core Assistant Pillars.
Contributed by Aman Kumar (@iamTechieAman).
"""
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from actions.browser_control import browser_control
from actions.quick_notes import quick_notes
from actions.reminder import reminder
from actions.weather_report import weather_action
from actions.whatsapp_automation import whatsapp_automation
from actions.writing_assistant import writing_assistant
from core.browser_agent import BrowserAgent, get_browser_agent
from core.file_tracker import get_file_tracker
from core.owner_session import get_owner_session
from core.permissions import UserRole, set_current_speaker
from core.whatsapp_desktop_controller import WhatsAppExecutionState, get_whatsapp_controller


class TestWhatsAppDataAndFileSending(unittest.TestCase):
    def setUp(self):
        set_current_speaker(UserRole.OWNER)
        get_owner_session().authenticate_owner("voice_biometrics", confidence=0.95)
        self.controller = get_whatsapp_controller()

    def test_contact_resolution_with_hindi_honorifics(self):
        # Add a known contact
        self.controller.add_or_update_contact("Rahul Sharma", "+919876543210", "Friend")

        # Query with honorifics
        matches_ji = self.controller.resolve_contacts("Rahul ji")
        self.assertTrue(len(matches_ji) >= 1)
        self.assertEqual(matches_ji[0]["name"], "Rahul Sharma")

        matches_bhai = self.controller.resolve_contacts("Rahul bhai")
        self.assertTrue(len(matches_bhai) >= 1)
        self.assertEqual(matches_bhai[0]["name"], "Rahul Sharma")

        matches_direct = self.controller.resolve_contacts("+919876543210")
        self.assertTrue(len(matches_direct) >= 1)

    @patch("subprocess.run")
    def test_whatsapp_send_file_with_latest_tracker(self, mock_sub):
        mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Create a temporary file and register it in tracker
        test_file = Path.home() / "Desktop" / "test_whatsapp_doc.pdf"
        test_file.write_text("dummy pdf content", encoding="utf-8")
        try:
            tracker = get_file_tracker()
            tracker.register_file(str(test_file), action="created", description="Test PDF")

            # Execute send_file via action without explicit file_path (auto-resolves 'latest')
            res = whatsapp_automation(
                {"action": "send_file", "recipient": "Rahul Sharma", "caption": "Here is the document"},
                session_memory={"speaker": "OWNER", "owner_authenticated": True}
            )
            self.assertIn("sent the file", res.lower())
            self.assertIn("test_whatsapp_doc.pdf", res)
        finally:
            test_file.unlink(missing_ok=True)

    @patch("subprocess.run")
    def test_whatsapp_add_contact_action(self, mock_sub):
        res = whatsapp_automation({
            "action": "add_contact",
            "name": "Pooja Verma",
            "phone": "9876500000",
            "relationship": "Colleague"
        })
        self.assertIn("Saved WhatsApp contact", res)
        self.assertIn("Pooja Verma", res)

        # Verify resolution
        resolved = self.controller.resolve_contacts("Pooja")
        self.assertTrue(any(c["name"] == "Pooja Verma" for c in resolved))


class TestAutonomousBrowserAgent(unittest.TestCase):
    def test_browser_agent_understand_goal(self):
        agent = get_browser_agent(headless=True)
        u1 = agent._understand_goal("search for quantum computing papers on arxiv")
        self.assertEqual(u1["type"], "search")
        self.assertIn("arxiv.org", u1["start_url"])

        u2 = agent._understand_goal("https://news.ycombinator.com")
        self.assertEqual(u2["type"], "direct_url")

    def test_browser_agent_check_intent_dispatch(self):
        with patch.object(BrowserAgent, "run_task") as mock_run:
            mock_run.return_value = {
                "success": True,
                "title": "Search Results",
                "extracted": {"items": ["Result A", "Result B"], "category": "search"},
                "summary": "# Browser Report\n- Result A\n- Result B"
            }

            res = browser_control({"action": "agent", "goal": "check top AI headlines"})
            self.assertIn("Autonomous browsing mission complete", res)
            mock_run.assert_called_once()

    def test_browser_control_browse_and_check(self):
        with patch.object(BrowserAgent, "run_task") as mock_run:
            mock_run.return_value = {
                "success": True,
                "title": "Product Page",
                "extracted": {"items": [], "category": "search"},
                "summary": "Product in stock"
            }

            res = browser_control({"action": "browse_and_check", "url": "https://example.com/product"})
            self.assertIn("Autonomous browsing mission complete", res)


class TestCoreAssistantPillars(unittest.TestCase):
    def test_reminder_countdown_timer(self):
        player_mock = MagicMock()
        res = reminder({"duration": "5 minutes", "message": "Boil eggs"}, player=player_mock)
        self.assertIn("Timer set for 5 minutes", res)
        self.assertIn("Boil eggs", res)

    @patch("urllib.request.urlopen")
    def test_weather_live_report(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "current_condition": [{
                "temp_C": "26",
                "FeelsLikeC": "27",
                "weatherDesc": [{"value": "Partly Cloudy"}],
                "humidity": "55",
                "windspeedKmph": "14"
            }]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        player_mock = MagicMock()
        res = weather_action({"city": "Bangalore"}, player=player_mock)
        self.assertIn("Partly Cloudy", res)
        self.assertIn("26°C", res)
        self.assertIn("Bangalore", res)

    def test_quick_notes_lifecycle(self):
        player_mock = MagicMock()
        # Add note
        add_res = quick_notes({"action": "add", "text": "Buy groceries and check email", "tag": "Personal"}, player=player_mock)
        self.assertIn("noted that down", add_res.lower())

        # List notes
        list_res = quick_notes({"action": "list"}, player=player_mock)
        self.assertIn("Buy groceries and check email", list_res)

        # Verify Desktop file exists
        desktop_notes = Path.home() / "Desktop" / "JARVIS_Notes.md"
        self.assertTrue(desktop_notes.exists())
        content = desktop_notes.read_text(encoding="utf-8")
        self.assertIn("Buy groceries and check email", content)

    @patch("core.gemini.text")
    def test_writing_assistant_email(self, mock_gemini):
        mock_gemini.return_value = "Subject: Meeting Reschedule\n\nHi Alex,\nCould we move our meeting to 4pm?\nThanks,\nAman"
        player_mock = MagicMock()

        res = writing_assistant({
            "action": "draft_email",
            "topic": "rescheduling meeting to 4pm",
            "recipient": "Alex",
            "tone": "casual"
        }, player=player_mock)

        self.assertIn("prepared the draft", res.lower())
        self.assertIn("Meeting Reschedule", res)


if __name__ == "__main__":
    unittest.main()
