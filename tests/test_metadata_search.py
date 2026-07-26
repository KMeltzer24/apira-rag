import unittest
from datetime import date
from pathlib import Path

from rag.chunking import chunk_text
from rag.metadata import extract_document_date, extract_ticker
from rag.ranking import prefer_newer


class MetadataTests(unittest.TestCase):
    def test_ticker_and_quarter_date_from_filename(self):
        path = Path("extracted/aapl-fy2025-q4-earnings.from-pdf.txt")
        self.assertEqual(extract_ticker(path), "AAPL")
        self.assertEqual(extract_document_date(path), date(2025, 12, 31))

    def test_ticker_from_research_note_header(self):
        path = Path("notes.md")
        text = "# Apple Inc. (AAPL) — Research Note\n\nHold.\n"
        self.assertEqual(extract_ticker(path, text), "AAPL")


class IntelligentChunkingTests(unittest.TestCase):
    def test_splits_on_markdown_headings(self):
        text = (
            "# Revenue\n"
            + ("Growth continued across regions. " * 20)
            + "\n# Outlook\n"
            + ("Guidance remains unchanged for now. " * 20)
        )
        chunks = chunk_text(text, chunk_size=120, overlap=20)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(any(chunk.startswith("# Revenue") for chunk in chunks))
        self.assertTrue(any("# Outlook" in chunk for chunk in chunks))


class PreferNewerTests(unittest.TestCase):
    def test_drops_older_ticker_chunks_when_newer_exists(self):
        rows = [
            ("old.txt", "old.txt", 0, "old aapl", 0.91, "AAPL", date(2024, 3, 31), None),
            ("new.txt", "new.txt", 0, "new aapl", 0.90, "AAPL", date(2025, 12, 31), None),
            ("msft.txt", "msft.txt", 0, "msft", 0.88, "MSFT", date(2025, 6, 30), None),
        ]
        selected = prefer_newer(rows, limit=2)
        paths = [row[1] for row in selected]
        self.assertIn("new.txt", paths)
        self.assertNotIn("old.txt", paths)
        self.assertIn("msft.txt", paths)


if __name__ == "__main__":
    unittest.main()
