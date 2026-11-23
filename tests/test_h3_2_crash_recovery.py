"""
Unit & Integration Tests for JARVIS H3.2 Crash Guard & Reliability Monitor
"""

import time
import unittest
from core.crash_guard import CrashGuard


class TestCrashGuard(unittest.TestCase):

    def setUp(self):
        # Fresh instance with low crash threshold for testing
        self.guard = CrashGuard(max_crashes_per_minute=2)

    def test_01_crash_recording(self):
        try:
            raise RuntimeError("Test error condition")
        except Exception as e:
            rec = self.guard.record_crash("test_comp", e)

        self.assertEqual(rec["component"], "test_comp")
        self.assertEqual(rec["error_type"], "RuntimeError")
        self.assertFalse(rec["is_crash_loop"])

    def test_02_crash_loop_detection_and_rate_limiting(self):
        self.assertFalse(self.guard.is_rate_limited("fragile_comp"))
        # 1st crash
        self.guard.record_crash("fragile_comp", ValueError("Err1"))
        self.assertFalse(self.guard.is_rate_limited("fragile_comp"))
        # 2nd crash triggers rate limit (threshold = 2)
        rec2 = self.guard.record_crash("fragile_comp", ValueError("Err2"))
        self.assertTrue(rec2["is_crash_loop"])
        self.assertTrue(self.guard.is_rate_limited("fragile_comp"))

    def test_03_supervised_decorator(self):
        call_count = 0

        @self.guard.guard("monitored_worker", fallback_return="SAFE_FALLBACK")
        def faulty_worker():
            nonlocal call_count
            call_count += 1
            raise ZeroDivisionError("division by zero")

        # 1st call executes and catches
        val1 = faulty_worker()
        self.assertEqual(val1, "SAFE_FALLBACK")
        self.assertEqual(call_count, 1)

        # 2nd call triggers rate limit
        val2 = faulty_worker()
        self.assertEqual(val2, "SAFE_FALLBACK")
        self.assertEqual(call_count, 2)

        # 3rd call is throttled before executing func
        val3 = faulty_worker()
        self.assertEqual(val3, "SAFE_FALLBACK")
        self.assertEqual(call_count, 2)  # Function body bypassed due to rate limit!

    def test_04_shutdown_hooks_execution(self):
        hook_ran = False

        def my_hook():
            nonlocal hook_ran
            hook_ran = True

        self.guard.register_shutdown_hook(my_hook)
        self.guard.execute_clean_shutdown()
        self.assertTrue(hook_ran)


if __name__ == "__main__":
    unittest.main()
