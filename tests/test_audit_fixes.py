"""tests/test_audit_fixes.py — Regression tests for audit fixes."""
import unittest
from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestRoutineRules(unittest.TestCase):
    def test_overnight_interval(self):
        """Interval rules spanning midnight should compute the next fire time properly."""
        from core.routines import rules as R

        rule = {
            "type": "interval",
            "minutes": 30,
            "start": "22:00",
            "end": "02:00",
            "days": [1, 2, 3, 4, 5, 6, 7],
        }
        # Given time: 21:00 UTC on a Monday (2026-03-02)
        after = datetime(2026, 3, 2, 21, 0, 0, tzinfo=timezone.utc)
        nxt = R.next_fire(rule, after)
        self.assertIsNotNone(nxt, "Overnight interval returned None")
        self.assertEqual(nxt.hour, 22)
        self.assertEqual(nxt.minute, 0)

        # Given time: 23:45 UTC -> next fire is 00:00 UTC next day
        after_mid = datetime(2026, 3, 2, 23, 45, 0, tzinfo=timezone.utc)
        nxt_mid = R.next_fire(rule, after_mid)
        self.assertIsNotNone(nxt_mid, "Overnight interval at 23:45 returned None")
        self.assertEqual(nxt_mid.hour, 0)
        self.assertEqual(nxt_mid.minute, 0)


class TestCodeCleaner(unittest.TestCase):
    def test_clean_code_with_leading_prose(self):
        """_clean_code should strip introductory text before markdown fences."""
        from actions.code_helper import _clean_code

        sample = (
            "Here is the Python script you requested:\n"
            "```python\n"
            "def hello():\n"
            "    return 'world'\n"
            "```\n"
            "Hope this helps!"
        )
        cleaned = _clean_code(sample)
        self.assertEqual(cleaned, "def hello():\n    return 'world'")


class TestYouTubeSummarize(unittest.TestCase):
    def test_summarize_accepts_parameter_url(self):
        """_handle_summarize should use parameters['url'] instead of asking for URL."""
        from actions import youtube_video

        # Mock _TRANSCRIPT_OK = True
        orig_transcript_ok = youtube_video._TRANSCRIPT_OK
        youtube_video._TRANSCRIPT_OK = True
        try:
            # If it uses the url, it will proceed to call _get_transcript
            # We monkeypatch _get_transcript to return a dummy transcript
            youtube_video._get_transcript = lambda vid: "test transcript"
            youtube_video._summarize_with_gemini = lambda t, u: "test summary"

            # Should NOT call _ask_for_url
            called_ask = []
            youtube_video._ask_for_url = lambda *a: called_ask.append(True)

            res = youtube_video._handle_summarize(
                {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                player=None,
                speak=None,
            )
            self.assertEqual(called_ask, [], "_ask_for_url was called despite url being provided")
            self.assertEqual(res, "test summary")
        finally:
            youtube_video._TRANSCRIPT_OK = orig_transcript_ok


class TestSendMessageOS(unittest.TestCase):
    def test_get_os_non_windows(self):
        """_get_os in send_message should not return 'windows' on Linux when config is empty."""
        import platform
        from actions.send_message import _get_os

        current = platform.system()
        if current == "Linux":
            self.assertEqual(_get_os(), "linux")
        elif current == "Darwin":
            self.assertEqual(_get_os(), "mac")


class TestTaskToolsSandbox(unittest.TestCase):
    def test_file_processor_destination_traversal_blocked(self):
        """file_processor extract action must not allow destination outside task workdir."""
        import tempfile
        import shutil
        from core.tasks.tools import TaskTools

        tmpdir = Path(tempfile.mkdtemp())
        try:
            workdir = tmpdir / "task1"
            outside = tmpdir / "outside"
            outside.mkdir()
            tools = TaskTools(workdir, ["file_processor"], log=lambda x: None)

            # Attempt extract with destination pointing outside workdir
            res = tools.execute("file_processor", {
                "action": "extract",
                "file_path": "dummy.zip",
                "destination": str(outside),
            })
            self.assertTrue(
                "outside" in res.lower() or "denied" in res.lower() or "failed" in res.lower(),
                f"Expected security failure, got: {res}"
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestWebSearch(unittest.TestCase):
    def test_gemini_search_empty_candidates(self):
        """_gemini_search should cleanly handle empty or filtered candidates."""
        from unittest.mock import MagicMock, patch
        from actions import web_search

        mock_resp = MagicMock()
        mock_resp.candidates = []

        with patch("core.gemini.call", return_value=mock_resp), \
             patch("actions.web_search._gemini_available", return_value=True):
            with self.assertRaises(ValueError) as cm:
                web_search._gemini_search("test query")
            self.assertIn("empty response", str(cm.exception))


class TestMetrics(unittest.TestCase):
    def test_metrics_survives_none_net_io(self):
        """_update should handle psutil.net_io_counters() returning None without throwing."""
        try:
            import PyQt6
            import psutil
        except ImportError:
            self.skipTest("PyQt6 or psutil not installed in test environment")

        from unittest.mock import patch
        from gui.metrics import _SysMetrics

        with patch("psutil.net_io_counters", return_value=None):
            sm = _SysMetrics()
            sm._running = False
            # Calling _update with None counters should set net=0.0 and not crash
            sm._update()
            self.assertEqual(sm.net, 0.0)


if __name__ == "__main__":
    unittest.main()
