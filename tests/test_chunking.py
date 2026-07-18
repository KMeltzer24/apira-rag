import unittest

from rag.chunking import chunk_text


class ChunkTextTests(unittest.TestCase):
    def test_prefers_sentence_boundaries(self):
        text = (
            "Revenue increased during the quarter. "
            "Services continued to grow across regions. "
            "Management raised its full-year guidance. "
            "Operating margin also improved year over year."
        )

        chunks = chunk_text(text, chunk_size=90, overlap=15)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].endswith("."))
        self.assertTrue(all(chunk for chunk in chunks))

    def test_rejects_invalid_overlap(self):
        with self.assertRaises(ValueError):
            chunk_text("some text", chunk_size=10, overlap=10)


if __name__ == "__main__":
    unittest.main()
