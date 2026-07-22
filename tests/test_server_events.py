import asyncio
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class _FastMCP:
    def __init__(self, _name):
        pass

    def add_middleware(self, _middleware):
        pass

    def tool(self):
        return lambda function: function


fastmcp = types.ModuleType("fastmcp")
fastmcp.FastMCP = _FastMCP
sys.modules.setdefault("fastmcp", fastmcp)

request_logging = types.ModuleType("request_logging")
request_logging.RequestLoggingMiddleware = type("RequestLoggingMiddleware", (), {})
request_logging.RequestIdHeaderMiddleware = type("RequestIdHeaderMiddleware", (), {})
sys.modules.setdefault("request_logging", request_logging)

rag_db = types.ModuleType("rag.db")
rag_db.get_connection = lambda: None
sys.modules.setdefault("rag.db", rag_db)

import server  # noqa: E402


class ServerEventTests(unittest.TestCase):
    def test_local_and_vector_search_log_counts_without_queries(self):
        events = []

        def capture(_logger, _level, event, _message, **fields):
            events.append((event, fields))

        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "research.md").write_text(
                "Revenue and operating income improved.", encoding="utf-8"
            )
            with (
                patch.object(server, "STOCK_RESEARCH_DIR", directory),
                patch.object(server, "log_event", side_effect=capture),
            ):
                local_result = asyncio.run(server.searchLocalFolder("revenue"))

        with (
            patch.object(
                server,
                "search_vector_db",
                return_value={"query": "private", "match_count": 2, "matches": []},
            ),
            patch.object(server, "log_event", side_effect=capture),
        ):
            vector_result = asyncio.run(server.searchVectorDB("private", 2))

        self.assertEqual(local_result["file_count"], 1)
        self.assertEqual(vector_result["match_count"], 2)
        self.assertIn(
            ("rag.local_search.completed", 1),
            [(event, fields.get("match_count")) for event, fields in events],
        )
        self.assertIn(
            ("rag.vector_search.completed", 2),
            [(event, fields.get("match_count")) for event, fields in events],
        )
        self.assertNotIn("revenue", repr(events).lower())
        self.assertNotIn("private", repr(events).lower())


if __name__ == "__main__":
    unittest.main()
