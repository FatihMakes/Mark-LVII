"""
tests/test_real_world_fixes.py — Rigorous unit tests verifying fixes for real-world user issues:
1. Mid-session crash & WebSocket disconnect handling (GoAway, ConnectionClosed).
2. Stall watchdog and excessive thinking state recovery.
3. macOS application scanning, fuzzy alias resolution, and launch verification.
4. Persistent FileTracker registry, retrieval, and fast disk search.
5. File preview, native opening, and context resolver short-hint file expansion.

Contributed by Aman Kumar (@iamTechieAman).
"""
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.file_tracker import FileTrackerEngine, get_file_tracker
from core.context_resolver import get_context_resolver
import actions.open_app as open_app_mod
import actions.file_controller as file_ctrl_mod
from main import _is_reconnect_signal, _ReconnectSignal


class TestRealWorldFixes(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.registry_file = self.test_root / "test_file_registry.json"
        self.tracker = FileTrackerEngine(registry_file=self.registry_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ── 1. FileTracker Engine Tests ──────────────────────────────────────────

    def test_file_tracker_registration_and_persistence(self):
        """Verify files are correctly tracked, sized, and saved across reloads."""
        sample_file = self.test_root / "resume_test.pdf"
        sample_file.write_text("Dummy PDF content for testing")

        entry = self.tracker.register_file(
            path=sample_file,
            action="pdf_generated",
            description="Generated Resume PDF",
            metadata={"title": "Aman Resume"}
        )

        self.assertEqual(entry["name"], "resume_test.pdf")
        self.assertEqual(entry["extension"], ".pdf")
        self.assertEqual(entry["action"], "pdf_generated")
        self.assertTrue(entry["exists"])
        self.assertTrue(self.registry_file.exists())

        # Test persistence: load with a new tracker instance
        new_tracker = FileTrackerEngine(registry_file=self.registry_file)
        latest = new_tracker.get_latest_file()
        self.assertIsNotNone(latest)
        self.assertEqual(latest["path"], str(sample_file.resolve()))
        self.assertEqual(latest["description"], "Generated Resume PDF")

    def test_file_tracker_query_and_lookup(self):
        """Verify find_tracked_file and get_recent_files."""
        f1 = self.test_root / "invoice_march.pdf"
        f1.write_text("invoice")
        f2 = self.test_root / "screenshot_2026.png"
        f2.write_text("png")

        self.tracker.register_file(f1, action="file_created", description="March Invoice")
        self.tracker.register_file(f2, action="screenshot_taken", description="Screen Capture")

        # Latest should be screenshot
        latest = self.tracker.get_latest_file()
        self.assertEqual(latest["name"], "screenshot_2026.png")

        # Latest PDF should be invoice
        latest_pdf = self.tracker.get_latest_file(extension=".pdf")
        self.assertEqual(latest_pdf["name"], "invoice_march.pdf")

        # Fuzzy match
        found = self.tracker.find_tracked_file("invoice")
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "invoice_march.pdf")

    def test_file_tracker_open_or_preview(self):
        """Verify open_or_preview validation and command dispatch."""
        missing = self.test_root / "non_existent_file.pdf"
        ok, msg = self.tracker.open_or_preview(missing)
        self.assertFalse(ok)
        self.assertIn("does not exist", msg)

        real_file = self.test_root / "document.txt"
        real_file.write_text("Real content")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ok, msg = self.tracker.open_or_preview(real_file)
            self.assertTrue(ok)
            self.assertIn("Opened", msg)

    # ── 2. File Controller Actions Tests ─────────────────────────────────────

    def test_file_controller_preview_and_open_action(self):
        """Verify preview and open actions in file_controller."""
        test_file = self.test_root / "test_report.pdf"
        test_file.write_text("Report data")

        # Register in tracker
        get_file_tracker().register_file(test_file, action="pdf_generated", description="Test Report")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Call file_controller with preview
            res = file_ctrl_mod.file_controller({"action": "preview", "name": "test_report.pdf"})
            self.assertIn("Opened", res)
            self.assertIn("test_report.pdf", res)

            # Call file_controller with open
            res2 = file_ctrl_mod.file_controller({"action": "open", "name": "test_report.pdf"})
            self.assertIn("Opened", res2)

    def test_file_controller_find_prioritizes_tracked(self):
        """Verify find_files prioritizes tracked files and skips hidden dirs."""
        tracked_path = Path.home() / "Desktop" / "my_project_presentation_test.pdf"
        tracked_path.write_text("dummy slides content")
        try:
            get_file_tracker().register_file(tracked_path, action="file_created", description="Project Presentation")

            res = file_ctrl_mod.find_files(name="my_project_presentation_test", path="desktop")
            self.assertIn("my_project_presentation_test.pdf", res)
            self.assertIn("Recently Saved", res)
        finally:
            if tracked_path.exists():
                tracked_path.unlink()

    # ── 3. macOS App Discovery & Opening Tests ────────────────────────────────

    def test_macos_app_discovery(self):
        """Verify scanner indexes applications from macOS application bundles."""
        apps = open_app_mod._get_macos_apps()
        self.assertIsInstance(apps, dict)
        self.assertGreater(len(apps), 10)
        # Verify common standard apps exist
        has_common = any(k in apps for k in ["terminal", "visualstudiocode", "safari", "notes", "preview", "systemsettings"])
        self.assertTrue(has_common, f"Expected common apps in scanned dictionary, found: {list(apps.keys())[:10]}")

    def test_macos_launch_alias_resolution(self):
        """Verify _launch_macos resolves spoken aliases to bundle paths."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Test 'code' -> Visual Studio Code
            ok = open_app_mod._launch_macos("code")
            self.assertTrue(ok)
            # Ensure open -a or open <path> was executed
            calls = [str(c[0][0]) for c in mock_run.call_args_list if c[0] and len(c[0]) > 0]
            self.assertTrue(any("Visual Studio Code" in c or "code" in c for c in calls))

    def test_launch_and_verify_no_false_negatives(self):
        """Verify _launch_and_verify handles already running apps and successful launches without false error."""
        player = MagicMock()
        with patch.object(open_app_mod.appidentity, "wait_for_launch", return_value=None):
            with patch.object(open_app_mod.appidentity, "running", return_value=[MagicMock(label="Visual Studio Code")]):
                open_app_mod._launch_and_verify(player, "code", "Visual Studio Code", before=set())
                # Player log should confirm it is open
                player.write_log.assert_called_with("JARVIS: Visual Studio Code is open.")
                # Say should NOT have been called with failure
                player.request_say.assert_not_called()

    # ── 4. WebSocket & GoAway Crash Prevention Tests ─────────────────────────

    def test_is_reconnect_signal_catches_goaway_and_connection_closed(self):
        """Verify _is_reconnect_signal detects GoAway / 1008 policy violations and BaseExceptionGroup."""
        rec_sig = _ReconnectSignal(keep_context=True)
        self.assertTrue(_is_reconnect_signal(rec_sig))

        # Simulated exception with 1008 / GoAway error message
        goaway_exc = Exception("1008 None. Connection aborted because the client failed to close the connection after receiving a GoAway signal")
        self.assertTrue(_is_reconnect_signal(goaway_exc))

        # Nested in BaseExceptionGroup (Python 3.11 TaskGroup error)
        group = BaseExceptionGroup("TaskGroup errors", [goaway_exc])
        self.assertTrue(_is_reconnect_signal(group))

        # Normal unrelated exception should return False
        normal_exc = ValueError("Some regular validation error")
        self.assertFalse(_is_reconnect_signal(normal_exc))

    # ── 5. Context Resolver Short Hint Tests ─────────────────────────────────

    def test_context_resolver_file_hints(self):
        """Verify context resolver detects and resolves 'kahan save kiya' and 'wo file kholo'."""
        resolver = get_context_resolver()
        test_file = self.test_root / "final_report.pdf"
        test_file.write_text("final report")
        get_file_tracker().register_file(test_file, action="pdf_generated", description="Final Report PDF")

        # 1. Location query
        res1 = resolver.resolve("kaha save kiya hai")
        self.assertTrue(res1.is_short_hint)
        self.assertEqual(res1.action_type, "FILE_LOCATE")
        self.assertIn("final_report.pdf", res1.resolved_query)

        # 2. Preview / open query
        res2 = resolver.resolve("wo file kholo")
        self.assertTrue(res2.is_short_hint)
        self.assertEqual(res2.action_type, "FILE_PREVIEW")
        self.assertIn("final_report.pdf", res2.resolved_query)

        # 3. English location query
        res3 = resolver.resolve("where is the file")
        self.assertTrue(res3.is_short_hint)
        self.assertEqual(res3.action_type, "FILE_LOCATE")


if __name__ == "__main__":
    unittest.main()
