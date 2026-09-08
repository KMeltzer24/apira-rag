"""Ensure research_chunks exists with metadata columns and search indexes."""

from __future__ import annotations

from rag.db import get_connection

_METADATA_COLUMNS = (
    ("content_hash", "TEXT"),
    ("ticker", "TEXT"),
    ("document_date", "DATE"),
    ("section_title", "TEXT"),
)


def ensure_research_chunk_schema() -> None:
    """Create the table if needed; add metadata columns and indexes (idempotent)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS research_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(768) NOT NULL,
                    content_hash TEXT,
                    ticker TEXT,
                    document_date DATE,
                    section_title TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (relative_path, chunk_index)
                )
                """
            )
            for name, sql_type in _METADATA_COLUMNS:
                cur.execute(
                    f"""
                    ALTER TABLE research_chunks
                    ADD COLUMN IF NOT EXISTS {name} {sql_type}
                    """
                )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS research_chunks_ticker_date_idx
                ON research_chunks (ticker, document_date DESC NULLS LAST)
                """
            )
            # Search uses cosine distance (`embedding <=> query_vector`), so
            # this HNSW index must use the matching vector_cosine_ops class.
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS research_chunks_embedding_hnsw_idx
                ON research_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
                """
            )
