import sys
import types
import unittest
from unittest.mock import patch

# Keep this unit test independent of psycopg2/pgvector installation.
fake_db = types.ModuleType("rag.db")
fake_db.get_connection = lambda: None
sys.modules.setdefault("rag.db", fake_db)

from rag import schema


class _Cursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement):
        self.statements.append(" ".join(statement.split()))


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def cursor(self):
        return self.cursor_instance


class SchemaTests(unittest.TestCase):
    def test_ensure_schema_creates_cosine_hnsw_index_idempotently(self):
        connection = _Connection()

        with patch.object(schema, "get_connection", return_value=connection):
            schema.ensure_research_chunk_schema()

        sql = "\n".join(connection.cursor_instance.statements)
        self.assertIn(
            "CREATE INDEX IF NOT EXISTS research_chunks_embedding_hnsw_idx",
            sql,
        )
        self.assertIn(
            "USING hnsw (embedding vector_cosine_ops)",
            sql,
        )
        self.assertIn(
            "WITH (m = 16, ef_construction = 64)",
            sql,
        )


if __name__ == "__main__":
    unittest.main()
