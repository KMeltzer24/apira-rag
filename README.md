# Apira RAG

Research ingestion and retrieval service for the Apira stock recommender.

It owns:

- `searchLocalFolder` — keyword search over research files on EC2
- `searchVectorDB` — semantic search over pgvector
- PDF and SEC extraction
- Chunking and Gemini embeddings
- The `stock-research/` corpus
- Ingest, purge, and rebuild scripts

The service exposes MCP over Streamable HTTP at `http://<host>:8200/mcp`. The Apira agent connects to this server for research tools and to `apira-mcp` for login/portfolio tools.

## Architecture

```text
apira-agent
├── apira-mcp :8000 → login, get_portfolio
└── apira-rag :8200 → searchLocalFolder, searchVectorDB
                         ├── stock-research/
                         ├── Gemini embeddings
                         └── RDS research_chunks (pgvector)
```

The vector table remains in the same RDS PostgreSQL database as the backend. See [docs/setup-pgvector-rds.md](docs/setup-pgvector-rds.md).

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

- Full rebuild (re-embed everything): `scripts/ingest_research.py`
- New/changed files only: `scripts/ingest_changed.py`

Details: [docs/how-stock-recommender-works.md](docs/how-stock-recommender-works.md).

## Local setup

```bash
cp .env.example .env
# Set DATABASE_URL and GOOGLE_API_KEY
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

## Deploy to EC2

From the repository root on your Mac:

```bash
tar czf /tmp/apira-rag-deploy.tgz \
  server.py apira_logging.py request_logging.py requirements.txt \
  Dockerfile .dockerignore docker-compose.yml \
  .env.example rag scripts sql stock-research docs tests

scp -i ../apira/my-ec2-key.pem /tmp/apira-rag-deploy.tgz \
  ec2-user@<EC2_PUBLIC_IP>:/tmp/

ssh -i ../apira/my-ec2-key.pem ec2-user@<EC2_PUBLIC_IP> \
  "mkdir -p ~/apira-rag && \
   tar xzf /tmp/apira-rag-deploy.tgz -C ~/apira-rag && \
   cd ~/apira-rag && \
   test -f .env || cp .env.example .env && \
   sudo docker compose up -d --build"
```

Set `DATABASE_URL` and `GOOGLE_API_KEY` in `~/apira-rag/.env`. Port `8200` only needs to be reachable from the co-located agent; it does not need a public security-group rule.

## Logging and correlation

The RAG service emits structured JSON logs to stdout for MCP tool calls, local
and vector searches, database operations, embedding retries, PDF extraction,
and ingestion. It accepts or generates `X-Request-ID` and returns it to the
caller. Logs include counts, filenames, model names, statuses, and durations;
they omit query text, document contents, vectors, credentials, and tool argument
values.

```bash
sudo docker compose logs -f rag-server
sudo docker compose logs --since=10m rag-server | grep '<request-id>'
```

See the shared [logging contract](https://github.com/KMeltzer24/apira/blob/main/docs/logging.md),
[how logging works](https://github.com/KMeltzer24/apira/blob/main/docs/how-logging-works.md),
and [how logging works](https://github.com/KMeltzer24/apira/blob/main/docs/how-logging-works.md).

## Documentation

- [How the stock recommender works](docs/how-stock-recommender-works.md)
- [pgvector/RDS setup](docs/setup-pgvector-rds.md)
