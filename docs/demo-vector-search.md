# Demo the Vector Search Recommender

This is the shortest walkthrough for showing how Apira uses RAG and pgvector.

## What it does

Research files live in `stock-research/` on EC2. The ingestion pipeline:

1. Splits the research into small text chunks.
2. Creates a Gemini embedding for each chunk.
3. Stores the chunks and embeddings in PostgreSQL with pgvector.
4. Lets the agent call `searchVectorDB` to retrieve relevant research for each portfolio holding.

The corpus includes analyst notes, text extracted from company PDFs, and text from SEC earnings releases. The current demo corpus contains **212 chunks from 11 files**.

## Live UI demo

1. Open `http://localhost:3000`.
2. Open the **Recommender** tab.
3. Enter `alice` / `password`.
4. Select **Vector DB (`searchVectorDB` / pgvector)**.
5. Click **Get Recommendations**.

The application logs in the user, retrieves the portfolio, searches pgvector, and returns Hold/Add/Trim advice with the research filenames used.

When Vector DB is selected, the frontend explicitly tells the agent to use `searchVectorDB` only and not `searchLocalFolder`.

## Show the stored research

Run on EC2:

```bash
cd ~/apira-rag
sudo docker compose run --rm rag-server \
  python scripts/purge_vector_index.py --list
```

Expect rows from the analyst notes and the `.from-pdf.txt` / `.from-sec.txt` extracts. The exact chunk count can change when parser or chunking rules improve.

## Show vector search directly

Run on EC2:

```bash
cd ~/apira-rag
sudo docker compose run --rm rag-server python -c "
import json
from rag.search import search_vector_db
print(json.dumps(
    search_vector_db('AAPL outlook and latest earnings', 5),
    indent=2
))
"
```

The result shows matched filenames, text chunks, and similarity scores. This is the same search function used by the `searchVectorDB` MCP tool.

## Files to show

- `server.py` — defines the `searchVectorDB` MCP tool
- `rag/` — chunking, embeddings, ingestion, and semantic search
- `scripts/ingest_research.py` — ingests the research corpus
- `stock-research/` — source research
- [how-stock-recommender-works.md](how-stock-recommender-works.md) — detailed feature explanation
- [setup-pgvector-rds.md](setup-pgvector-rds.md) — RDS and pgvector setup
