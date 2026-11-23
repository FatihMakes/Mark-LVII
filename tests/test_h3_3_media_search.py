"""
tests/test_h3_3_media_search.py — Tests for Local Media Search & Duplicate Detection
"""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from core.media_search import MediaSearchEngine, get_media_search_engine
from actions.media_search import media_search


class TestMediaSearch(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.engine = MediaSearchEngine(search_dirs=[self.test_dir])

        # Create two identical dummy images
        self.img1_path = self.test_dir / "sample_photo_a.png"
        self.img2_path = self.test_dir / "sample_photo_b.png"
        img = Image.new("RGB", (200, 150), color=(73, 109, 137))
        img.save(self.img1_path)
        img.save(self.img2_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_search_media(self):
        results = self.engine.search_media("sample", limit=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["dimensions"], "200x150")

    def test_find_duplicates(self):
        dupes = self.engine.find_duplicates(self.test_dir)
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["count"], 2)

    def test_get_image_info(self):
        info = self.engine.get_image_info(self.img1_path)
        self.assertEqual(info["name"], "sample_photo_a.png")
        self.assertEqual(info["dimensions"], "200x150")
        self.assertGreater(info["size_kb"], 0)

    def test_action_media_search_duplicates(self):
        res = media_search({"action": "duplicates", "directory": str(self.test_dir)})
        self.assertIn("Found 1 sets of duplicate images", res)


if __name__ == "__main__":
    unittest.main()
