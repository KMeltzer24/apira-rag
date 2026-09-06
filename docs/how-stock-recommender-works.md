# How the Stock Recommender Works (Phase I & II)

This doc explains the stock-recommendation feature across two phases:

- **Phase I** — `searchLocalFolder` reads `.txt` / `.md` files from `stock-research/` in this repo
- **Phase II** — RAG pipeline ingests those files into **pgvector on local Postgres**; `searchVectorDB` does semantic search

The Recommender tab lets you pick **local folder** or **vector DB** search via a radio button.

**Related repos:**

| Repo | Role in this feature |
|------|----------------------|
| **apira-rag** (this repo) | Research tools, RAG pipeline, and `stock-research/` corpus |
| [apira-mcp](https://github.com/KMeltzer24/apira-mcp) | `login` and `get_portfolio` tools |
| [apira-agent](https://github.com/KMeltzer24/apira-agent) | LangGraph supervisor + portfolio/research specialists |
| [apira-frontend](https://github.com/KMeltzer24/apira-frontend) | Recommender tab — sends one `POST /chat` prompt |
| [apira](https://github.com/KMeltzer24/apira) | Backend APIs (`login`, `get_portfolio`) via MCP |

**Phase II:** `searchVectorDB` + RAG ingestion into PostgreSQL/pgvector on the **same local Postgres** as the backend. See [apira run-locally.md](https://github.com/KMeltzer24/apira/blob/main/docs/run-locally.md) and [vector-search-params.md](vector-search-params.md).

---

## The big picture

Research files live in `stock-research/` in this repo, mounted into the apira-rag container. When a user clicks **Get Recommendations**, the frontend sends a structured prompt to the agent. The **supervisor** routes to the **portfolio** specialist (`login`, `get_portfolio`) then the **research** specialist (`searchLocalFolder` or `searchVectorDB`), then finishes with natural-language recommendations.

```
User (Recommender tab)
  │
  ▼
apira-frontend (:3000 on Mac)
  │  POST /chat { message: "Log in as alice… searchLocalFolder…" }
  ▼
apira-agent (:8100)
  │  supervisor → portfolio → research
  │
  ├── apira-mcp (:8000)
  ├── login          → user-service (:8001) → Postgres
  ├── get_portfolio  → portfolio-service (:8002) → Postgres
  │
  └── apira-rag (:8200)
      ├── searchLocalFolder → stock-research/
      └── searchVectorDB    → research_chunks in Postgres
  ▼
Gemini (research specialist) → { "reply": "…hold AAPL… trim TSLA…" }
  ▼
Frontend renders reply
```

The frontend never calls MCP or reads files directly. It only talks to the agent API, same as Agent Chat.

---

## What lives where

| Piece | Location | Notes |
|-------|----------|-------|
| Research files | `stock-research/` in this repo | Analyst notes, PDFs, and extracted text |
| RAG mount | `/data/stock-research` inside container | Docker volume |
| `searchLocalFolder` | `server.py` in this repo | Scans `.txt` and `.md` only |
| Specialist prompts | `graph.py` in apira-agent | Supervisor routes; research specialist picks one search tool |
| UI trigger | `StockRecommenderScreen` in apira-frontend | Username + password → preset prompt |

---

## Step-by-step flow

When the user opens the **Recommender** tab, enters `alice` / `password`, and clicks **Get Recommendations**:

1. **Frontend** builds a fixed prompt (see below) and sends `POST http://localhost:8100/chat`.

2. **Agent** receives the message. On the first request it connects to both MCP servers, partitions tools onto specialists (`login` / `get_portfolio` vs the two search tools), and compiles the supervisor graph.

3. **Supervisor** routes. Typical order:
   - **portfolio** specialist: `login("alice", "password")` → `{ user_id: 1, … }`, then `get_portfolio(1)` → holdings
   - **research** specialist: `searchLocalFolder("AAPL")`, `searchLocalFolder("MSFT")`, … (or `searchVectorDB` if that mode was selected)
   - supervisor finishes with the research specialist's Hold/Add/Trim text

4. **`searchLocalFolder`** walks `/data/stock-research`, reads matching files, returns JSON:

   ```json
   {
     "query": "AAPL",
     "folder": "/data/stock-research",
     "file_count": 1,
     "files": [
       {
         "filename": "aapl-outlook.md",
         "relative_path": "aapl-outlook.md",
         "content": "# Apple Inc. (AAPL) — Research Note\n…"
       }
     ]
   }
   ```

5. **Gemini** reads tool results and writes recommendations: for each holding, hold / add / trim with rationale, citing filenames like `aapl-outlook.md`.

6. **Agent** returns `{ "reply": "…" }` to the frontend.

7. **Frontend** displays the reply in the read-only output area.

The exact tool-call sequence can vary — the LLM chooses how many `searchLocalFolder` calls to make. The system prompt guides it to search per ticker and cite sources.

---

## The `searchLocalFolder` tool

Defined in `server.py`:

```python
@mcp.tool()
async def searchLocalFolder(query: str = "") -> dict:
    """Search stock research files on the server for content matching a query."""
```

| Parameter | Behavior |
|-----------|----------|
| `query` empty or `"all"` | Return every `.txt` / `.md` file in the folder |
| `query` = `"AAPL"` | Return files whose **name or content** contains `AAPL` (case-insensitive) |
| `query` = `"tech"` | Same — matches `tech-sector-overview.md`, etc. |

**Limits (learning project):**

- Only `.txt` and `.md` extensions
- Max ~32 KB per file; ~96 KB total per tool call (truncates if exceeded)
- Only reads from `STOCK_RESEARCH_DIR` (default `/data/stock-research`) — no arbitrary paths

**Sample files** in `stock-research/`:

| File | Covers |
|------|--------|
| `aapl-outlook.md` | Apple — hold / slight overweight |
| `msft-analysis.txt` | Microsoft — bullish |
| `googl-notes.md` | Alphabet — buy |
| `amzn-outlook.txt` | Amazon — neutral |
| `tsla-analysis.md` | Tesla — hold, high volatility |
| `tech-sector-overview.md` | Sector themes and allocation guidance |

To add research, drop a new `.md` or `.txt` into `stock-research/` and redeploy this repo (Phase I). For Phase II, also run the ingest scripts — see [Research corpus & ingestion](#research-corpus--ingestion) below.

---

## Research corpus & ingestion

### What the research files are for

Sample files are **ticker-specific analyst-style notes** — rating, outlook, risks, and hold/add/trim guidance. The recommender compares them against the user's portfolio holdings from `get_portfolio`.

| File | Covers |
|------|--------|
| `aapl-outlook.md` | Apple — hold / slight overweight |
| `msft-analysis.txt` | Microsoft — bullish |
| `googl-notes.md` | Alphabet — buy |
| `amzn-outlook.txt` | Amazon — neutral |
| `tsla-analysis.md` | Tesla — hold, high volatility |
| `tech-sector-overview.md` | Sector themes and allocation guidance |

Additional **live earnings data** lives under `stock-research/pdfs/` (PDF) and `stock-research/extracted/` (text from PDFs or SEC HTML). These files are **committed to the repo** — they are not re-downloaded each time. See [stock-research/pdfs/README.md](../stock-research/pdfs/README.md).

Extracted filenames show origin: `*.from-pdf.txt` (from a PDF) or `*.from-sec.txt` (from SEC HTML). Each file starts with a `# Source: …` header.

### Local folder vs vector DB storage

| Mode | Where research lives | How agent reads it |
|------|---------------------|-------------------|
| **Local folder** | `.md` / `.txt` in the container mount | `searchLocalFolder` reads files directly at query time |
| **Vector DB** | Same files, plus `extracted/` text | Files are chunked, embedded, stored in Postgres `research_chunks`; `searchVectorDB` does semantic search |

### Ingest does not call `searchLocalFolder`

Both modes use the **same** `stock-research/` folder. Ingest scripts (`ingest_research.py`, `pdf_inject.py`, etc.) read that folder **directly from disk** — they do not invoke the `searchLocalFolder` MCP tool. Local search reads files when the user asks; vector search reads files when you run ingest, then queries the embeddings later via `searchVectorDB`. After adding or changing research files, run ingest so vector search stays in sync.

### Ingestion is manual (not automatic)

Nothing ingests when you drop a file on disk. You must run a script:

```
New .md / .txt in stock-research/
        │
        ▼
scripts/ingest_research.py  ──► chunk → embed → research_chunks (Postgres)

New PDF in stock-research/pdfs/
        │
        ▼
scripts/pdf_inject.py  ──► extract text (skip fluff pages)
        │                  save to extracted/*.txt
        ▼
                  embed chunks → research_chunks

SEC earnings HTML (no PDF available)
        │
        ▼
scripts/fetch_sec_exhibit.py  ──► extracted/*.txt → embed
```

**One-command embed** (uses committed files on disk — no download):

```bash
bash scripts/ingest_ticker_research.sh
```

To replace PDFs/SEC extracts (rare): `bash scripts/refresh_ticker_corpus.sh`, then commit and redeploy.

### What “chunks” means

The vector DB does not store whole files. Each `.txt` / `.md` is split into pieces of about **800 characters** (with overlap). The chunker first splits on markdown / Source headings, then prefers paragraph, sentence, and word boundaries. Each piece gets a Gemini embedding and one row in `research_chunks`, plus metadata:

- `ticker` — from filename or research-note header
- `document_date` — from FY/Q patterns in the filename when present
- `section_title` — heading at the start of the chunk when present
- `content_hash` — used so `ingest_changed` can skip unchanged files

Example: 6 analyst notes + 5 earnings extracts might produce ~80–120 chunks total. That number is **pieces of text**, not file count.

**Ingest modes:**

| Command | Behavior |
|---------|----------|
| `scripts/ingest_changed.py` | New/changed files only (best when adding a PDF) |
| `scripts/ingest_research.py` | Full rebuild of every file |

`searchVectorDB` ranks by similarity, then **prefers newer `document_date` values for the same ticker** so older earnings chunks lose to newer ones when both match. Parameter reference (similarity formula, `limit`, candidate pool): [vector-search-params.md](vector-search-params.md).

Optional SQL (also applied automatically by the app):
`sql/migrate_research_chunks_metadata.sql` and
`sql/migrate_research_chunks_hnsw.sql`. The HNSW index uses
`vector_cosine_ops`, matching the `<=>` cosine-distance search, and does not
require re-embedding existing chunks.

### PDF fluff-page skipping

`rag/pdf_extract.py` extracts text only (embedded images are not sent to the vector DB), then removes low-value content before ingest:

- Skip empty/image-only pages, covers, divider pages, copyright pages, and tables of contents
- Detect and remove headers and footers repeated across multiple pages
- Remove standalone page numbers, URLs, confidentiality labels, and navigation lines
- Skip legal/publication boilerplate when it has little company or investment content
- Keep short pages when they contain financial table terms and meaningful numeric data
- Normalize broken hyphenation and whitespace while preserving page markers

`pdf_inject.py` reports pages kept, pages skipped with reasons, and the number of repeated/noise lines removed. Use `--include-all-pages` to disable filtering.

### Finding new research (Google → PDF)

To find new research PDFs:

1. Search ticker-specific queries, e.g. `MSFT earnings Q3 2026 filetype:pdf`
2. Google **Tools → Advanced search → File type: PDF**
3. Prefer official sources: company newsroom, investor relations, SEC EDGAR
4. Copy into `stock-research/pdfs/` and run `pdf_inject.py`

If the best result is SEC HTML (Exhibit 99.1), use `fetch_sec_exhibit.py` instead — many companies publish earnings as HTML on SEC, not PDF.

---

## Frontend prompt (what the Recommender tab sends)

The UI does not expose MCP or file paths. It only sends this template (with the user's credentials filled in):

```
Log in as user 'alice' with password 'password'.
Retrieve their portfolio holdings.
Use searchLocalFolder to find stock research files for each ticker.
Respond with one entry per holding, in this exact format:

**TICKER (Company)** — Hold / Add / Trim
Files: filename1, filename2
One or two short sentences of reasoning.

Keep it concise. No sector overview. No bullet lists of current holdings.
```

That single string is the entire contract between frontend and agent.

---

## Agent prompts

Standing instructions live in [apira-agent/graph.py](https://github.com/KMeltzer24/apira-agent/blob/main/graph.py):

- **Supervisor** — route to `portfolio`, `research`, or finish (chat with no tools)
- **Portfolio specialist** — log in before `get_portfolio`
- **Research specialist** — use the search tool named in the user message (never both unless asked); cite files; Hold/Add/Trim

Gemini combines those prompts with the Recommender tab message.

---

## Update locally

Research files and the tool ship with **this repo**. After changes:

```bash
cd ~/apira-rag && docker compose up -d --build
```

Then **restart the agent** so it reloads tools from MCP:

```bash
cd ~/apira-agent && docker compose restart
```

Frontend changes (Recommender tab) rebuild locally:

```bash
cd ~/apira-frontend && docker compose up -d --build
```

---

## How to test

**From the UI:** `http://localhost:3000` → Recommender → `alice` / `password` → Get Recommendations.

**From curl** (same path the UI uses):

```bash
curl -s -X POST http://localhost:8100/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Log in as alice with password password. Retrieve their portfolio holdings. Use searchLocalFolder to find stock research files for each ticker. Respond with one entry per holding: **TICKER (Company)** — Hold/Add/Trim, then Files: ..., then one or two short sentences. Keep it concise. No sector overview."}'
```

Expected: a multi-paragraph reply referencing files like `aapl-outlook.md` and `tech-sector-overview.md`.

---

---

## Phase II — Vector search (searchVectorDB)

### RAG pipeline

```
stock-research/
  ├── *.md, *.txt          analyst notes (Phase I samples)
  ├── pdfs/*.pdf           ticker earnings PDFs
  └── extracted/*.txt      text from PDFs + SEC HTML exhibits
        │
        ▼
scripts/ingest_research.py  |  pdf_inject.py  |  fetch_sec_exhibit.py
        │  chunk → embed (Gemini gemini-embedding-001, 768 dims)
        ▼
PostgreSQL — research_chunks table (pgvector)
        │
        ▼
searchVectorDB MCP tool  →  agent  →  Recommender UI (Vector DB mode)
```

| Component | Location |
|-----------|----------|
| Ingest scripts | `scripts/ingest_research.py`, `pdf_inject.py`, `fetch_sec_exhibit.py`, `ingest_ticker_research.sh` |
| PDF extraction | `rag/pdf_extract.py` (fluff-page skipping) |
| RAG code | `rag/` (chunk, embed, ingest, search) |
| Vector storage | Postgres table `research_chunks` — **same DB as users/portfolios** |
| MCP tool | `searchVectorDB(query, limit=5)` |

### Demo ticker earnings corpus

| Ticker | File | Type |
|--------|------|------|
| AAPL | `pdfs/aapl-fy2025-q4-earnings.pdf` | Official Apple newsroom PDF |
| TSLA | `pdfs/tsla-q1-2026-update.pdf` | Official Tesla IR PDF |
| MSFT | `extracted/msft-q3-fy2026-earnings.from-sec.txt` | SEC Exhibit 99.1 HTML |
| GOOGL | `extracted/googl-q3-2025-earnings.from-sec.txt` | SEC Exhibit 99.1 HTML |
| AMZN | `extracted/amzn-q1-2026-earnings.from-sec.txt` | SEC Exhibit 99.1 HTML |

These complement the analyst notes — they carry **current financial results** the agent can weigh against how much of each stock the user owns.

### PDF injector

```bash
# On the host
python scripts/pdf_inject.py stock-research/pdfs/aapl-fy2025-q4-earnings.pdf

# Or inside the container
docker compose run --rm rag-server \
  python scripts/pdf_inject.py /data/stock-research/pdfs/aapl-fy2025-q4-earnings.pdf
```

Then re-ingest all text files (or run `ingest_ticker_research.sh` for the full corpus).

### Frontend search mode

The Recommender tab radio buttons tell the agent which tool to use:

| UI selection | Tool used |
|--------------|-----------|
| Local folder | `searchLocalFolder` only |
| Vector DB | `searchVectorDB` only |

### Verify the vector index

List indexed files and chunk counts:

```bash
cd ~/apira-rag
docker compose run --rm rag-server \
  python scripts/purge_vector_index.py --list
```

Run semantic search directly and inspect matched filenames, chunks, and
similarity scores:

```bash
docker compose run --rm rag-server python -c "
import json
from rag.search import search_vector_db
print(json.dumps(
    search_vector_db('AAPL fiscal 2025 fourth quarter earnings', 5),
    indent=2
))
"
```

Chunk counts change when extraction or chunking rules improve.

### Local Postgres

Use the pgvector image from [apira run-locally.md](https://github.com/KMeltzer24/apira/blob/main/docs/run-locally.md). Set `DATABASE_URL` + `GOOGLE_API_KEY` in apira-rag `.env`, then run ingest. Schema is applied by `rag/schema.py`.

---

## What this feature is not

| Not included | Notes |
|--------------|-------|
| Searching arbitrary paths on the Mac | Files come from the `stock-research/` mount |
| Separate vector DB service | Vectors live in PostgreSQL (pgvector) |
| Separate `stockRecommender` MCP tool | Recommendations are agent behavior + search tools |
| Using both search tools at once | UI selects one mode per request |
| Shared login with Portfolio tab | Recommender asks for credentials again |
| Structured JSON output | Free-text reply from Gemini |

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| Agent ignores research files | Agent not restarted after RAG rebuild | `docker compose restart` in `~/apira-agent/` |
| `searchLocalFolder` returns empty | `stock-research/` not mounted | Check `docker-compose.yml` volume; rebuild RAG |
| Generic advice, no file citations | Gemini skipped tool calls | Retry; check agent logs |
| "Stock research folder not found" | Volume missing | Ensure `stock-research/` is in the image/volume |
| Timeout / slow | Many tickers → many tool calls + LLM | Normal for alice's 5 holdings; wait or use curl to debug |
| `searchVectorDB` returns empty | Research not ingested | Run `scripts/ingest_research.py` or `ingest_ticker_research.sh` |
| Vector search returns generic advice | Wrong corpus (e.g. SEC education PDFs) | Use ticker-specific earnings PDFs / SEC exhibits — see [pdfs/README.md](../stock-research/pdfs/README.md) |
| `429 RESOURCE_EXHAUSTED` during ingest | Gemini embedding rate limit | Wait 30s and re-run; scripts retry automatically |
| pgvector / embedding errors | Extension or env missing | Check `DATABASE_URL` / `GOOGLE_API_KEY`; see [run-locally.md](https://github.com/KMeltzer24/apira/blob/main/docs/run-locally.md) |

---

## Further reading

| Doc | Content |
|-----|---------|
| [apira-mcp: how-mcp-works.md](https://github.com/KMeltzer24/apira-mcp/blob/main/docs/how-mcp-works.md) | MCP protocol and tool discovery |
| [apira: run-locally.md](https://github.com/KMeltzer24/apira/blob/main/docs/run-locally.md) | Local Postgres + full stack |
| [vector-search-params.md](vector-search-params.md) | `similarity`, `limit`, prefer-newer ranking |
| [stock-research/pdfs/README.md](../stock-research/pdfs/README.md) | Ticker PDF sources, ingest commands, Google PDF search |
| [apira: architecture.md](https://github.com/KMeltzer24/apira/blob/main/docs/architecture.md) | Full system diagram |
| [apira-agent: how-the-agent-works.md](https://github.com/KMeltzer24/apira-agent/blob/main/docs/how-the-agent-works.md) | Supervisor + specialist graph |
| [apira-frontend: how-the-frontend-works.md](https://github.com/KMeltzer24/apira-frontend/blob/main/docs/how-the-frontend-works.md) | Three UI tabs |
