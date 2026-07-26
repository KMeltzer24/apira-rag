import importlib
import sys
import types
import unittest
from unittest.mock import patch

from rag import embeddings


class _Models:
    def __init__(self):
        self.calls = 0

    def embed_content(self, **_kwargs):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return types.SimpleNamespace(
            embeddings=[types.SimpleNamespace(values=[0.1, 0.2, 0.3])]
        )


class RagEventTests(unittest.TestCase):
    def test_embedding_retries_emit_safe_events(self):
        client = types.SimpleNamespace(models=_Models())
        events = []

        def capture(_logger, _level, event, _message, **fields):
            events.append((event, fields))

        with (
            patch.object(embeddings, "_client", return_value=client),
            patch.object(embeddings.time, "sleep") as sleep,
            patch.object(embeddings, "log_event", side_effect=capture),
        ):
            vector = embeddings.embed_text("private query text")

        self.assertEqual(vector, [0.1, 0.2, 0.3])
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(
            [event for event, _fields in events].count(
                "rag.embedding.rate_limited"
            ),
            2,
        )
        self.assertIn("rag.embedding.completed", [event for event, _ in events])
        self.assertNotIn("private query text", repr(events))
        retry_fields = [
            fields
            for event, fields in events
            if event == "rag.embedding.rate_limited"
        ]
        self.assertTrue(all(fields["error_code"] == 429 for fields in retry_fields))

    def test_database_search_logs_match_count_without_query(self):
        rows = [
            (
                "report.md",
                "report.md",
                0,
                "result text",
                0.91,
                "AAPL",
                None,
                "Revenue",
            )
        ]

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def execute(self, *_args):
                pass

            def fetchall(self):
                return rows

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def cursor(self):
                return Cursor()

        fake_db = types.ModuleType("rag.db")
        fake_db.get_connection = Connection
        previous_db = sys.modules.get("rag.db")
        sys.modules["rag.db"] = fake_db
        sys.modules.pop("rag.search", None)
        try:
            search = importlib.import_module("rag.search")
            events = []

            def capture(_logger, _level, event, _message, **fields):
                events.append((event, fields))

            with (
                patch.object(search, "embed_text", return_value=[0.1, 0.2]),
                patch.object(search, "ensure_research_chunk_schema"),
                patch.object(search, "log_event", side_effect=capture),
            ):
                result = search.search_vector_db("private search query", 3)
        finally:
            sys.modules.pop("rag.search", None)
            if previous_db is None:
                sys.modules.pop("rag.db", None)
            else:
                sys.modules["rag.db"] = previous_db

        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["matches"][0]["ticker"], "AAPL")
        self.assertIn(
            ("rag.db_search.completed", 1),
            [(event, fields.get("match_count")) for event, fields in events],
        )
        self.assertNotIn("private search query", repr(events))


if __name__ == "__main__":
    unittest.main()
