"""
Unit & Integration Tests for JARVIS H3.2 macOS Deep Scan & Download Manager
"""

import os
import unittest
from pathlib import Path
from core.mac_analyzer import MacAnalyzer, get_mac_analyzer
from actions.mac_scan import mac_scan_handler, TOOL as SCAN_TOOL
from actions.download_manager import download_manager_handler, TOOL as DL_TOOL


class TestMacFilesystemAndDownload(unittest.TestCase):

    def setUp(self):
        self.analyzer = get_mac_analyzer()

    def test_01_tool_definitions(self):
        self.assertEqual(SCAN_TOOL["name"], "mac_deep_scan")
        self.assertEqual(DL_TOOL["name"], "download_manager")

    def test_02_system_audit_metrics(self):
        audit = self.analyzer.run_system_audit()
        self.assertEqual(audit["status"], "success")
        self.assertIn("Memory", audit["metrics"])
        self.assertIn("Disk", audit["metrics"])
        self.assertIn("CPU", audit["metrics"])
        self.assertTrue(len(audit["findings"]) > 0)

    def test_03_heavy_processes_discovery(self):
        procs = self.analyzer.get_heavy_processes(limit=5)
        self.assertTrue(len(procs) > 0)
        self.assertIn("pid", procs[0])
        self.assertIn("memory_mb", procs[0])

    def test_04_download_manager_rejects_bad_protocols(self):
        res = download_manager_handler({"url": "ftp://malicious.host/bad.bin"})
        self.assertIn("Invalid URL protocol", res)

    def test_05_download_manager_rejects_empty_url(self):
        res = download_manager_handler({"url": ""})
        self.assertIn("valid download URL", res)


if __name__ == "__main__":
    unittest.main()
