"""Ensure research_chunks has metadata columns used by ingest/search."""

from __future__ import annotations

from rag.db import get_connection

_METADATA_COLUMNS = (
    ("content_hash", "TEXT"),
    ("ticker", "TEXT"),
    ("document_date", "DATE"),
    ("section_title", "TEXT"),
)


def ensure_research_chunk_schema() -> None:
    """Add optional metadata columns if they are missing (idempotent)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
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
