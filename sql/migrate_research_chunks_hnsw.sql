-- HNSW approximate-nearest-neighbor index for cosine vector search.
-- Safe to re-run. apira-rag also applies this via rag/schema.py on ingest/search.
--
-- Search orders by `embedding <=> query_vector`, so the matching operator
-- class is vector_cosine_ops. The defaults shown explicitly here are a good
-- starting point for this corpus.

CREATE INDEX IF NOT EXISTS research_chunks_embedding_hnsw_idx
    ON research_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
