import logging
from time import perf_counter

from apira_logging import get_logger, log_event
from rag.config import DEFAULT_SEARCH_LIMIT
from rag.db import get_connection
from rag.embeddings import embed_text

logger = get_logger("apira-rag")


def search_vector_db(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> dict:
    """Semantic search over ingested research chunks using pgvector."""
    if not query.strip():
        raise ValueError("query must not be empty")

    started = perf_counter()
    log_event(
        logger,
        logging.INFO,
        "rag.db_search.started",
        "Database vector search started",
        limit=limit,
    )
    try:
        vector = embed_text(query.strip(), task_type="RETRIEVAL_QUERY")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        filename,
                        relative_path,
                        chunk_index,
                        content,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM research_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vector, vector, limit),
                )
                rows = cur.fetchall()
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "rag.db_search.failed",
            "Database vector search failed",
            limit=limit,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            error_type=type(exc).__name__,
        )
        raise

    log_event(
        logger,
        logging.INFO,
        "rag.db_search.completed",
        "Database vector search completed",
        limit=limit,
        match_count=len(rows),
        duration_ms=round((perf_counter() - started) * 1000, 2),
    )

    matches = [
        {
            "filename": row[0],
            "relative_path": row[1],
            "chunk_index": row[2],
            "content": row[3],
            "similarity": round(float(row[4]), 4),
        }
        for row in rows
    ]

    return {
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }
