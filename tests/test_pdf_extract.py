from pathlib import Path
import types
import unittest
from unittest.mock import patch

from rag.pdf_extract import (
    _clean_page,
    _repeated_edge_keys,
    extract_pdf_text,
    fluff_reason,
    is_fluff_page,
)


class PdfExtractTests(unittest.TestCase):
    def test_image_only_page_is_skipped(self):
        self.assertEqual(fluff_reason(""), "empty or image-only")

    def test_short_financial_table_is_kept(self):
        text = (
            "Net sales $102,466 $94,930\n"
            "Net income $27,466 $14,736\n"
            "Earnings per share $1.85 $0.97"
        )
        self.assertFalse(is_fluff_page(text))

    def test_short_cover_is_skipped(self):
        self.assertTrue(is_fluff_page("2025 Investor Presentation\nApple Inc."))

    def test_repeated_headers_and_page_numbers_are_removed(self):
        pages = [
            "ACME Q4 2025 Investor Update\nRevenue grew 12 percent.\nPage 1",
            "ACME Q4 2025 Investor Update\nOperating income improved.\nPage 2",
            "ACME Q4 2025 Investor Update\nCash flow reached $4 billion.\nPage 3",
        ]
        repeated = _repeated_edge_keys(pages)
        cleaned, removed = _clean_page(pages[0], repeated)

        self.assertNotIn("ACME Q4 2025 Investor Update", cleaned)
        self.assertNotIn("Page 1", cleaned)
        self.assertIn("Revenue grew", cleaned)
        self.assertEqual(removed, 2)

    def test_extraction_logs_only_summary_metadata(self):
        page = types.SimpleNamespace(
            extract_text=lambda: (
                "Net sales $102,466 $94,930\n"
                "Net income $27,466 $14,736\n"
                "Earnings per share $1.85 $0.97"
            )
        )
        events = []

        def capture(_logger, _level, event, _message, **fields):
            events.append((event, fields))

        with (
            patch("rag.pdf_extract.PdfReader", return_value=types.SimpleNamespace(pages=[page])),
            patch("rag.pdf_extract.log_event", side_effect=capture),
        ):
            result = extract_pdf_text(Path("quarterly-report.pdf"))

        self.assertEqual(result["total_pages"], 1)
        self.assertEqual(events[0][0], "rag.pdf_extraction.completed")
        self.assertEqual(events[0][1]["filename"], "quarterly-report.pdf")
        self.assertNotIn("Net sales", repr(events))


if __name__ == "__main__":
    unittest.main()
