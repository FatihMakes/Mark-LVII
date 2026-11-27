"""
tests/test_h35_openjarvis_voice_polish.py
Unit tests verifying H3.5 OpenJarvis integration, anti-self-talk defenses,
vocal gender demographics, and macOS native messaging.
"""
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from core.speaker_intelligence import detect_speaker_gender
from core.echo import (
    suppress_mic_window,
    is_mic_suppressed,
    record_assistant_utterance,
    is_self_talk_echo,
)
from core.context_resolver import ContextResolver
from actions.send_message import _resolve_platform, _send_imessage
from actions.quick_notes import quick_notes, _sync_to_apple_notes
from core.file_tracker import get_file_tracker, FileTrackerEngine
from core.whatsapp_desktop_controller import get_whatsapp_controller


class TestH35OpenJarvisAndVoicePolish(unittest.TestCase):

    def test_vocal_gender_pitch_detection(self):
        sr = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)

        # 1. Male pitch: 120 Hz sine wave
        male_wave = (0.5 * np.sin(2 * np.pi * 120 * t)).astype(np.float32)
        gender_m, addr_m, pitch_m = detect_speaker_gender(male_wave, sample_rate=sr)
        self.assertEqual(gender_m, "MALE")
        self.assertEqual(addr_m, "Sir")

        # 2. Female pitch: 220 Hz sine wave
        female_wave = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        gender_f, addr_f, pitch_f = detect_speaker_gender(female_wave, sample_rate=sr)
        self.assertEqual(gender_f, "FEMALE")
        self.assertEqual(addr_f, "Ma'am")

    def test_anti_self_talk_echo_filter(self):
        # 1. Suppress mic window
        suppress_mic_window(seconds=1.0)
        self.assertTrue(is_mic_suppressed())

        # 2. Record utterance
        record_assistant_utterance("Your boiling egg reminder is ringing, sir.")

        # Test identical or high-similarity echo
        self.assertTrue(is_self_talk_echo("Your boiling egg reminder is ringing, sir."))
        self.assertTrue(is_self_talk_echo("your boiling egg reminder is ringing"))

        # Test distinct user utterance
        self.assertFalse(is_self_talk_echo("Turn on the room lights please."))

    def test_context_resolver_demographics(self):
        resolver = ContextResolver()
        resolver.set_speaker_demographics("Ma'am", "FEMALE")
        self.assertEqual(resolver.get_speaker_address(), "Ma'am")
        self.assertEqual(resolver.get_speaker_gender(), "FEMALE")

        resolver.set_speaker_demographics("Sir", "MALE")
        self.assertEqual(resolver.get_speaker_address(), "Sir")

    def test_imessage_platform_resolution(self):
        handler1 = _resolve_platform("imessage")
        handler2 = _resolve_platform("Messages")
        handler3 = _resolve_platform("sms")
        self.assertEqual(handler1, _send_imessage)
        self.assertEqual(handler2, _send_imessage)
        self.assertEqual(handler3, _send_imessage)

    @patch("subprocess.run")
    def test_send_imessage_applescript_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "OK"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        with patch("sys.platform", "darwin"):
            res = _send_imessage("+1234567890", "Hello from JARVIS")
            self.assertIn("status=done", res)
            self.assertIn("iMessage", res)

    @patch("subprocess.run")
    def test_quick_notes_with_apple_notes(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        result = quick_notes({"action": "add", "text": "Test OpenJarvis note sync", "tag": "Idea"})
        self.assertIn("noted that down", result)

    def test_file_tracker_find_file(self):
        tracker = get_file_tracker()
        self.assertTrue(hasattr(tracker, "find_file"))
        res = tracker.find_file("JARVIS_Notes")
        self.assertIsInstance(res, list)

    def test_whatsapp_desktop_search_fallback(self):
        controller = get_whatsapp_controller()
        matches = controller.resolve_contacts("NonExistentContactNameXYZ", allow_desktop_search=True)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Nonexistentcontactnamexyz")
        self.assertEqual(matches[0]["relationship"], "WhatsApp Search Target")


if __name__ == "__main__":
    unittest.main()
