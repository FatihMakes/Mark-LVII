"""
Unit & Integration Tests for JARVIS H3.2 PDF Studio & Document Synthesizer
"""

import os
import unittest
from pathlib import Path
from core.pdf_studio import generate_pdf, validate_pdf, synthesize_content_if_needed


class TestPDFStudio(unittest.TestCase):

    def setUp(self):
        self.test_pdf = Path("test_artifact.pdf").resolve()

    def tearDown(self):
        if self.test_pdf.exists():
            self.test_pdf.unlink(missing_ok=True)

    def test_01_content_synthesis(self):
        # Even with empty content, must generate structured sections
        synthesized = synthesize_content_if_needed("", query="Neural Network Architecture")
        self.assertTrue(len(synthesized) > 300)
        self.assertIn("Neural Network Architecture", synthesized)
        self.assertIn("Executive Summary", synthesized)

    def test_02_pdf_generation_and_validation(self):
        content = (
            "# Unit Test Document\n\n"
            "This is a paragraph verifying typography and page construction.\n\n"
            "## Code Section\n"
            "```python\n"
            "def test_math():\n"
            "    return 42\n"
            "```\n\n"
            "## Summary\n"
            "End of report.\n"
        )
        res = generate_pdf(
            content=content,
            output_filename=str(self.test_pdf),
            title="Unit Test Specification",
            open_preview=False
        )
        self.assertEqual(res["status"], "success")
        self.assertTrue(self.test_pdf.exists())
        self.assertGreater(res["file_size"], 500)
        self.assertGreaterEqual(res["pages"], 1)

        # PyMuPDF binary verification
        val = validate_pdf(str(self.test_pdf))
        self.assertTrue(val["is_valid"])
        self.assertTrue(val["has_text"])
        self.assertGreater(val["pages"], 0)

    def test_03_invalid_file_validation(self):
        val = validate_pdf("non_existent_file.pdf")
        self.assertFalse(val["is_valid"])


if __name__ == "__main__":
    unittest.main()
