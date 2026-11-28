"""
tests/test_language_and_mute_stall.py
Tests verifying dynamic language detection, language mirroring,
and microphone long-mute idle recovery in JARVIS.
"""
import time
import unittest
from unittest.mock import MagicMock, patch

from core.language_detector import detect_language, get_language_directive
from core.context_resolver import ContextResolver


class TestLanguageAndMuteStall(unittest.TestCase):

    def test_language_detection_english(self):
        english_samples = [
            "What is the current time in New York?",
            "Open Google Chrome and search for latest AI news.",
            "Please turn up the volume a little bit.",
            "Can you check if there are any new emails for me?",
            "Send this document to my desktop.",
        ]
        for s in english_samples:
            lang = detect_language(s)
            self.assertEqual(lang, "ENGLISH", f"Failed for: {s}")

    def test_language_detection_hindi_devanagari(self):
        hindi_samples = [
            "आज का मौसम कैसा है?",
            "समय क्या हुआ है जार्विस?",
            "मेरी आज की मीटिंग्स क्या हैं?",
            "कृपया लाइट बंद कर दो।",
            "यह फाइल व्हाट्सएप पर भेज दो।",
        ]
        for s in hindi_samples:
            lang = detect_language(s)
            self.assertEqual(lang, "HINDI", f"Failed for: {s}")

    def test_language_detection_hinglish(self):
        hinglish_samples = [
            "aaj ka mausam kaisa hai jarvis",
            "yeh file mummy ko whatsapp pe bhej do",
            "kya haal hai bhai kya chal raha hai",
            "thoda volume badhao aur gana play karo",
            "mujhe kal subah 7 baje ka alarm lagao",
            "abhi time kya ho raha hai batao",
        ]
        for s in hinglish_samples:
            lang = detect_language(s)
            self.assertEqual(lang, "HINGLISH", f"Failed for: {s}")

    def test_language_directive_generation(self):
        dir_en = get_language_directive("ENGLISH")
        self.assertIn("English", dir_en)
        self.assertIn("[LANGUAGE REQUIREMENT: ENGLISH]", dir_en)

        dir_hi = get_language_directive("HINDI")
        self.assertIn("Hindi", dir_hi)
        self.assertIn("[LANGUAGE REQUIREMENT: HINDI]", dir_hi)

        dir_hing = get_language_directive("HINGLISH")
        self.assertIn("Hinglish", dir_hing)
        self.assertIn("[LANGUAGE REQUIREMENT: HINGLISH]", dir_hing)

    def test_context_resolver_active_language(self):
        resolver = ContextResolver()
        self.assertEqual(resolver.get_active_language(), "ENGLISH")

        resolver.record_turn("user", "Can you open my files?")
        self.assertEqual(resolver.get_active_language(), "ENGLISH")

        resolver.record_turn("user", "aaj ka mausam kaisa hai bhai")
        self.assertEqual(resolver.get_active_language(), "HINGLISH")

        resolver.record_turn("user", "आज का मौसम कैसा है")
        self.assertEqual(resolver.get_active_language(), "HINDI")

        resolver.record_turn("user", "What about tomorrow's weather?")
        self.assertEqual(resolver.get_active_language(), "ENGLISH")

    def test_mute_unmute_recovery_logic(self):
        import queue

        class MockQueue:
            def __init__(self):
                self._items = ["audio1", "audio2"]
            def empty(self):
                return len(self._items) == 0
            def get_nowait(self):
                if not self._items:
                    raise queue.Empty
                return self._items.pop(0)

        # Mock JarvisLive instance attributes
        class MockJarvis:
            def __init__(self):
                self._muted_at = 0.0
                self._interrupted = False
                self._awake = False
                self._last_user_speech = 0.0
                self.out_queue = MockQueue()
                self.audio_in_queue = MockQueue()
                self.session = MagicMock()
                self._send_task = MagicMock()
                self._send_task.done.return_value = False
                self._recv_task = MagicMock()
                self._recv_task.done.return_value = False
                self.ui = MagicMock()
                self._reconnect_called = False
                self._reconnect_reason = ""

            def request_reconnect(self, keep_context=True, reason=""):
                self._reconnect_called = True
                self._reconnect_reason = reason

            def interrupt(self):
                self._interrupted = True

        from main import JarvisLive
        # 1. Test mute
        jarvis = MockJarvis()
        JarvisLive._on_ui_mute_change(jarvis, muted=True)
        self.assertGreater(jarvis._muted_at, 0.0)
        self.assertTrue(jarvis._interrupted)

        # 2. Test short unmute (<20s, session alive)
        jarvis._muted_at = time.monotonic() - 5.0
        jarvis._reconnect_called = False
        JarvisLive._on_ui_mute_change(jarvis, muted=False)
        self.assertFalse(jarvis._reconnect_called)
        self.assertTrue(jarvis._awake)
        self.assertEqual(jarvis._muted_at, 0.0)

        # 3. Test long unmute (>=20s) -> should refresh session with context preserved
        jarvis._muted_at = time.monotonic() - 45.0
        jarvis._reconnect_called = False
        JarvisLive._on_ui_mute_change(jarvis, muted=False)
        self.assertTrue(jarvis._reconnect_called)
        self.assertEqual(jarvis._reconnect_reason, "unmuted after idle")

        # 4. Test unmute when session is dead (e.g. _send_task done)
        jarvis._muted_at = time.monotonic() - 5.0
        jarvis._send_task.done.return_value = True
        jarvis._reconnect_called = False
        JarvisLive._on_ui_mute_change(jarvis, muted=False)
        self.assertTrue(jarvis._reconnect_called)
        self.assertEqual(jarvis._reconnect_reason, "unmuted after idle")


if __name__ == "__main__":
    unittest.main()
