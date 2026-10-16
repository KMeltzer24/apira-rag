# Apira RAG (MCP tools)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-FastMCP-black)](https://github.com/modelcontextprotocol)
[![pgvector](https://img.shields.io/badge/pgvector-HNSW-4169E1)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

**MCP + RAG server** for **Apira** (AI Portfolio Intelligence Research Assistant). One **FastMCP** endpoint at **`http://localhost:8000/mcp`**: backend tools (login, holdings, last rec) plus research — keyword search on disk and **semantic search** (Gemini embeddings, pgvector HNSW).

Apira is four repos. **Clone + run order:** [apira README](https://github.com/KMeltzer24/apira). Start the backend before this repo.

## Tools

| Tool | Backs onto |
|------|------------|
| `login` | [apira](https://github.com/KMeltzer24/apira) `POST /login` |
| `get_portfolio` | `GET /portfolio` |
| `getPreviousRecommendation` / `saveRecommendation` | `GET` / `PUT /recommendation` |
| `searchLocalFolder` | `stock-research/` on disk |
| `searchVectorDB` | Postgres `research_chunks` (Gemini embeddings, HNSW) |

[apira-agent](https://github.com/KMeltzer24/apira-agent) specialists load **allowlists**, not the full catalog. The [frontend](https://github.com/KMeltzer24/apira-frontend) does not call this server.

Local-folder search does not need a Gemini key. Vector search and ingest do.

Research files live in `stock-research/` (analyst notes, PDFs, extracted text). They are committed; nothing is downloaded on start. Optional ingest embeds that corpus into Postgres.

## Run

Need [Docker Desktop](https://www.docker.com/products/docker-desktop/). Point `DATABASE_URL` at the same Postgres this stack starts in [apira](https://github.com/KMeltzer24/apira).

```bash
git clone https://github.com/KMeltzer24/apira-rag.git
cd apira-rag
cp .env.example .env
# DATABASE_URL, USER_SERVICE_URL, PORTFOLIO_SERVICE_URL
# GOOGLE_API_KEY only for searchVectorDB / ingest
docker compose up -d --build
```

Optional ingest (vector DB):

```bash
docker compose run --rm rag-server python scripts/ingest_research.py
```
