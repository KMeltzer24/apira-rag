from rag.config import DEFAULT_SEARCH_LIMIT
from rag.db import get_connection
from rag.embeddings import embed_text


def search_vector_db(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> dict:
    """Semantic search over ingested research chunks using pgvector."""
    if not query.strip():
        raise ValueError("query must not be empty")

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
