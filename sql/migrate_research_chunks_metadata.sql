-- Metadata columns for ticker/date ranking and change detection.
-- Safe to re-run. apira-rag also applies these via rag/schema.py on ingest/search.

ALTER TABLE research_chunks ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE research_chunks ADD COLUMN IF NOT EXISTS ticker TEXT;
ALTER TABLE research_chunks ADD COLUMN IF NOT EXISTS document_date DATE;
ALTER TABLE research_chunks ADD COLUMN IF NOT EXISTS section_title TEXT;

CREATE INDEX IF NOT EXISTS research_chunks_ticker_date_idx
    ON research_chunks (ticker, document_date DESC NULLS LAST);
