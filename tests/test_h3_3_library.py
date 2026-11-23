"""
tests/test_h3_3_library.py — End-to-End Tests for JARVIS H3.3 Library System
"""
import tempfile
import unittest
from pathlib import Path
from core.library_manager import LibraryManager, get_library_manager


class TestLibrarySystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mgr = LibraryManager(root_dir=Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_read_note(self):
        saved = self.mgr.save_note("Project Architecture", "# Overview\nJARVIS H3.3 is active.")
        self.assertEqual(saved["status"], "success")
        saved_path = Path(saved["path"])
        self.assertTrue(saved_path.is_file())
        text = self.mgr.read_document_text(str(saved_path))
        self.assertIn("JARVIS H3.3 is active.", text)

    def test_list_and_search(self):
        self.mgr.save_note("Alpha Note", "This contains specific keyword quantum.")
        self.mgr.save_note("Beta Note", "Different topic entirely.")

        files = self.mgr.list_files(recursive=True)
        self.assertEqual(len(files), 2)

        results = self.mgr.search_library("quantum")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alpha Note.md")

    def test_create_folder_and_organization(self):
        res = self.mgr.create_folder("Finance")
        self.assertEqual(res["status"], "success")
        folder_path = Path(res["path"])
        self.assertTrue(folder_path.is_dir())
        folders = [f["name"] for f in self.mgr.list_folders()]
        self.assertIn("Finance", folders)

    def test_import_document(self):
        src_file = Path(self.temp_dir.name) / "sample_import.txt"
        src_file.write_text("Exported data for testing.", encoding="utf-8")
        imported = self.mgr.import_document(src_file)
        self.assertEqual(imported["status"], "success")
        dest_path = Path(imported["path"])
        self.assertTrue(dest_path.is_file())
        self.assertEqual(dest_path.name, "sample_import.txt")


if __name__ == "__main__":
    unittest.main()
