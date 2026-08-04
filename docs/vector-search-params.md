# Vector search parameters

How `searchVectorDB` turns a query into ranked research chunks, and what each
knob means.

## Call shape

```text
searchVectorDB(query: str, limit: int = 5) → {
  query, match_count, matches: [
    { filename, relative_path, chunk_index, content,
      similarity, ticker, document_date, section_title }
  ]
}
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `query` | required | Natural-language search text. Embedded with Gemini as `RETRIEVAL_QUERY`, then compared to stored chunk embeddings (`RETRIEVAL_DOCUMENT` at ingest). |
| `limit` | `5` (`RAG_SEARCH_LIMIT`) | Max matches returned **after** ranking and prefer-newer filtering. |

Env overrides (ingest/search process):

| Env | Default | Role |
|-----|---------|------|
| `RAG_SEARCH_LIMIT` | `5` | Default `limit` when the tool omits it |
| `RAG_CHUNK_SIZE` | `800` | Target characters per chunk at ingest |
| `RAG_CHUNK_OVERLAP` | `100` | Overlap between adjacent chunks |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model |
| `EMBEDDING_DIMENSION` | `768` | Vector size in pgvector |

## Similarity score

pgvector stores one embedding per chunk. Search orders by **cosine distance**
(`embedding <=> query_vector`). The API exposes the complement as similarity:

```text
similarity = 1 - (embedding <=> query_vector)
```

| Similarity | Rough meaning |
|------------|----------------|
| closer to `1.0` | Chunk embedding is nearly the same direction as the query |
| around `0.5`–`0.7` | Related but not a tight match (common for short financial snippets) |
| closer to `0` | Weak match; still may appear if nothing better exists in the top candidates |

Notes:

- There is **no minimum similarity threshold** today. Raising `limit` only
  returns more of the nearest neighbors; it does not drop weak scores.
- Scores are rounded to 4 decimal places in the tool response.
- Compare scores **within one query**, not across different queries or models.

## Candidate pool vs returned limit

Raw SQL fetches more rows than `limit` so prefer-newer can drop older docs
without starving the result set:

```text
candidate_limit = max(limit * 4, limit)
```

(`_CANDIDATE_MULTIPLIER = 4` in `rag/search.py`.)

Flow:

1. Embed `query`
2. `ORDER BY embedding <=> query` with `LIMIT candidate_limit`
3. Run `prefer_newer(rows, limit)`
4. Return up to `limit` matches

## Prefer-newer (same-ticker override)

After similarity ranking, `rag/ranking.py` keeps the newest
`document_date` per `ticker` when both an old and a new doc match:

1. Scan candidates; for each ticker with dates, remember the newest date
2. Walk similarity order; **skip** chunks whose `document_date` is older than
   that ticker’s newest date among candidates
3. If fewer than `limit` remain, backfill from remaining candidates
   (including undated / other tickers)

So for Alice’s AAPL holding, a newer FY26 Q2 earnings extract can displace an
older FY25 Q4 chunk that scored slightly higher on pure similarity.

Metadata sources (`rag/metadata.py`):

| Field | Typical source |
|-------|----------------|
| `ticker` | Filename prefix (`aapl-…`, `tsla-…`) or note header |
| `document_date` | `fy2026-q2` / `q2-2026` / `q4-fy2026` patterns → quarter-end date |
| `section_title` | Leading markdown / `Source:` line in the chunk |

Quarter-end approximation when only FY/Q is known: Q1→Mar 31, Q2→Jun 30,
Q3→Sep 30, Q4→Dec 31 (calendar), based on the year in the filename.

## What is *not* parameterized (yet)

| Idea | Status |
|------|--------|
| Similarity floor (`min_score`) | Not implemented — weak matches can still return |
| HNSW / IVFFlat index params | Table uses pgvector; ANN index tuning is a separate backlog item |
| Hybrid keyword + vector | Separate tool: `searchLocalFolder` |
| Per-ticker quotas in `limit` | Prefer-newer only; no hard “one chunk per ticker” |

## Quick checks

List indexed files:

```bash
sudo docker compose run --rm rag-server \
  python scripts/purge_vector_index.py --list
```

Inspect scores and dates for one query:

```bash
sudo docker compose run --rm rag-server python -c "
import json
from rag.search import search_vector_db
print(json.dumps(
    search_vector_db('AAPL fiscal 2026 second quarter earnings', 5),
    indent=2
))
"
```

Expect newer AAPL / TSLA / MSFT extracts (when ingested) to appear ahead of
older same-ticker chunks when both are in the candidate pool.

## Related docs

- [how-stock-recommender-works.md](how-stock-recommender-works.md) — end-to-end recommender + ingest
- [setup-pgvector-rds.md](setup-pgvector-rds.md) — RDS / pgvector setup
- [stock-research/pdfs/README.md](../stock-research/pdfs/README.md) — PDF corpus
