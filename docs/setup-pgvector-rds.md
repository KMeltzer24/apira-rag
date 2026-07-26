# pgvector on AWS RDS — Setup for Phase II

Phase II stores research embeddings in **the same RDS PostgreSQL database** as `users` and `portfolios`, using the **pgvector** extension. You do **not** need a new database instance or a separate vector DB service.

---

## What you need to change on AWS

| Item | Change required? | Action |
|------|------------------|--------|
| **New RDS instance** | No | Reuse existing PostgreSQL RDS |
| **EC2 security group** | No | apira-rag runs on EC2; RDS already allows EC2 on port 5432 |
| **New public inbound port** | No | The co-located agent reaches apira-rag on host port 8200 |
| **pgvector extension** | Yes (one-time) | Run `CREATE EXTENSION vector;` on the database |
| **New table** | Yes (one-time) | Run the SQL below (already applied on our RDS instance) |
| **apira-rag `.env` on EC2** | Yes | Add `DATABASE_URL` (same as backend) + `GOOGLE_API_KEY` |

### RDS PostgreSQL version

pgvector is available on **RDS PostgreSQL 15+** (and many 14+ instances). If `CREATE EXTENSION vector` fails, check your engine version in the RDS console and upgrade if needed.

### Who connects to RDS after Phase II

| Service | Connects to RDS? | Tables |
|---------|------------------|--------|
| user-service | Yes | `users` |
| portfolio-service | Yes | `portfolios` |
| **apira-rag** | Yes | `research_chunks` (pgvector) |

Frontend, agent, and Gemini never connect to RDS directly.

---

## One-time database setup

Connect to RDS the same way you did for seed data (pgAdmin over SSH tunnel, or `psql` from EC2) and run:

```sql
-- Requires pgvector (RDS PostgreSQL 15+)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS research_chunks (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (relative_path, chunk_index)
);
```

That creates:

- `vector` extension
- `research_chunks` table with an `embedding vector(768)` column (Gemini `gemini-embedding-001`)

Optional metadata columns (ticker, document date, content hash) are in
`sql/migrate_research_chunks_metadata.sql` and are also applied automatically by
`rag/schema.py` on ingest/search.

**Note:** This has already been run on the project RDS instance. Keep the SQL here for reference only.

---

## apira-rag environment on EC2

Edit `~/apira-rag/.env`:

```bash
DATABASE_URL=postgresql+psycopg2://<user>:<password>@<rds-host>:5432/<dbname>
GOOGLE_API_KEY=<your-gemini-key>
EMBEDDING_MODEL=gemini-embedding-001
```

Then rebuild the RAG server:

```bash
cd ~/apira-rag && sudo docker compose up -d --build
cd ~/apira-agent && sudo docker compose restart
```

---

## Ingest research files into pgvector

After apira-rag is running with `DATABASE_URL` and `GOOGLE_API_KEY`:

```bash
# on EC2 — ingest all .txt / .md under stock-research/
cd ~/apira-rag
sudo docker compose run --rm rag-server python scripts/ingest_research.py
```

Re-run after adding or changing research files. This is **not automatic** — dropping files on disk does nothing until you run ingest.

**Full demo corpus** (ticker PDFs + SEC earnings + analyst notes):

```bash
sudo docker compose run --rm rag-server bash scripts/ingest_ticker_research.sh
```

---

## PDF injector

Copy a ticker-specific PDF (earnings, investor presentation) into the research corpus and ingest it:

```bash
# on EC2
sudo docker compose run --rm rag-server \
  python scripts/pdf_inject.py /data/stock-research/pdfs/aapl-fy2025-q4-earnings.pdf

# from your Mac — copy PDF to EC2 first, then:
scp -i my-ec2-key.pem report.pdf ec2-user@<EC2_IP>:~/apira-rag/stock-research/pdfs/
ssh ... "cd ~/apira-rag && sudo docker compose run --rm rag-server \
  python scripts/pdf_inject.py /data/stock-research/pdfs/report.pdf"
```

The script:

1. Extracts text with `pypdf`, **skipping fluff pages** (cover, copyright, TOC) via `rag/pdf_extract.py`
2. Saves the PDF under `stock-research/pdfs/`
3. Saves extracted text under `stock-research/extracted/<name>.txt`
4. Embeds chunks into `research_chunks`

Use `--include-all-pages` to keep every page.

---

## SEC HTML exhibits (when PDF is not available)

Many earnings releases are HTML on SEC (Exhibit 99.1), not PDF:

```bash
sudo docker compose run --rm rag-server python scripts/fetch_sec_exhibit.py \
  "https://www.sec.gov/Archives/edgar/data/789019/000119312526191457/msft-ex99_1.htm" \
  "msft-q3-fy2026-earnings"
```

Or fetch the bundled MSFT/GOOGL/AMZN demo set:

```bash
sudo docker compose run --rm rag-server bash scripts/fetch_ticker_earnings.sh
```

---

## Verify vector search

```bash
# list tools — should include searchVectorDB
# then use Recommender tab with "Vector DB" selected, or curl the agent (see how-stock-recommender-works.md)
```

Check rows exist:

```sql
SELECT COUNT(*) FROM research_chunks;
SELECT filename, chunk_index, LEFT(content, 80) FROM research_chunks LIMIT 5;
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `extension "vector" is not available` | Upgrade RDS PostgreSQL or enable pgvector in your region/engine |
| `GOOGLE_API_KEY is not set` | Add to `~/apira-rag/.env` and rebuild |
| `relation "research_chunks" does not exist` | Run the SQL in [One-time database setup](#one-time-database-setup) |
| `searchVectorDB` returns empty | Run `scripts/ingest_research.py` |
| Dimension mismatch error | Table uses `vector(768)` — do not change `output_dimensionality` without updating SQL |

---

## Further reading

- [how-stock-recommender-works.md](how-stock-recommender-works.md) — Phase I + II feature flow
- [apira: how-the-database-works.md](https://github.com/KMeltzer24/apira/blob/main/docs/how-the-database-works.md) — SQLAlchemy connection for backend services
