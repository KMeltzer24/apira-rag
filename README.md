# Apira RAG

Research ingestion and retrieval service for the Apira stock recommender.

It owns:

- `searchLocalFolder` — keyword search over research files (`stock-research/`)
- `searchVectorDB` — semantic search over pgvector
- PDF and SEC extraction
- Chunking and Gemini embeddings
- The `stock-research/` corpus
- Ingest, purge, and rebuild scripts

The service exposes MCP over Streamable HTTP at `http://localhost:8200/mcp`. Apira's **research** specialist in [apira-agent](https://github.com/KMeltzer24/apira-agent) calls these tools; login/portfolio tools stay on `apira-mcp` (the **portfolio** specialist).

## Architecture

```text
apira-agent
├── apira-mcp :8000 → login, get_portfolio
└── apira-rag :8200 → searchLocalFolder, searchVectorDB
                         ├── stock-research/
                         ├── Gemini embeddings
                         └── Postgres research_chunks (pgvector)
```

The vector table lives in the **same local PostgreSQL** as the backend (`docker-compose.local.yml` in apira). See [apira run-locally.md](https://github.com/KMeltzer24/apira/blob/main/docs/run-locally.md).

## Chunking, metadata, and search ranking

Ingest splits each research file into overlapping chunks (~800 chars). The
chunker prefers markdown / Source headings, then paragraphs and sentences
(not a blind fixed-window split).

Each `research_chunks` row stores:

| Column | Purpose |
|--------|---------|
| `content` + embedding | Semantic search |
| `ticker` | From filename / headers when detectable |
| `document_date` | From FY/Q patterns in the filename when present |
| `section_title` | Heading at the start of the chunk when present |
| `content_hash` | Skip unchanged files in `ingest_changed` |

`searchVectorDB` ranks by similarity, then **prefers newer `document_date`
values for the same ticker** so older overlapping chunks lose to newer ones.

Vector search is backed by an **HNSW** approximate-nearest-neighbor index on the
`embedding` column (`vector_cosine_ops`, `m=16`, `ef_construction=64`), applied
idempotently by `rag/schema.py` and mirrored in `sql/migrate_research_chunks_hnsw.sql`.
No re-embedding is needed to add it. At a small corpus size PostgreSQL may still
choose a sequential scan, which is expected.

- Full rebuild (re-embed everything): `scripts/ingest_research.py`
- New/changed files only: `scripts/ingest_changed.py`

Details: [docs/how-stock-recommender-works.md](docs/how-stock-recommender-works.md).  
Vector params (`similarity`, `limit`, prefer-newer): [docs/vector-search-params.md](docs/vector-search-params.md).

## Local setup

```bash
cp .env.example .env
# DATABASE_URL=postgresql+psycopg2://apira:apira@host.docker.internal:5432/apira
# GOOGLE_API_KEY=<gemini-key>   # needed for searchVectorDB / ingest
docker compose up -d --build
```

Run tests:

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

Ingest the committed corpus (full rebuild — re-embeds every file):

```bash
docker compose run --rm rag-server python scripts/ingest_research.py
```

Ingest only **new or changed** files (recommended when adding a PDF):

```bash
docker compose run --rm rag-server python scripts/ingest_changed.py
```

Re-extract PDFs and refresh the vector index:

```bash
docker compose run --rm rag-server bash scripts/rebuild_vector_corpus.sh
```

For mentor demos, **Local folder** search works without ingest. Vector DB needs the ingest step above.

## Logging and correlation

The RAG service emits structured JSON logs to stdout for MCP tool calls, local
and vector searches, database operations, embedding retries, PDF extraction,
and ingestion. It accepts or generates `X-Request-ID` and returns it to the
caller. Logs include counts, filenames, model names, statuses, and durations;
they omit query text, document contents, vectors, credentials, and tool argument
values.

```bash
docker compose logs -f rag-server
docker compose logs --since=10m rag-server | grep '<request-id>'
```

See the shared [logging contract](https://github.com/KMeltzer24/apira/blob/main/docs/logging.md)
and [how logging works](https://github.com/KMeltzer24/apira/blob/main/docs/how-logging-works.md).

## Documentation

- [How the stock recommender works](docs/how-stock-recommender-works.md)
- [Vector search parameters (similarity, limit, prefer-newer, HNSW)](docs/vector-search-params.md)
- [Run the full stack locally](https://github.com/KMeltzer24/apira/blob/main/docs/run-locally.md)
