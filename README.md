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

Ingest the committed corpus:

```bash
docker compose run --rm rag-server python scripts/ingest_research.py
```

Re-extract PDFs and refresh the vector index:

```bash
docker compose run --rm rag-server bash scripts/rebuild_vector_corpus.sh
```

## Deploy to EC2

From the repository root on your Mac:

```bash
tar czf /tmp/apira-rag-deploy.tgz \
  server.py requirements.txt Dockerfile .dockerignore docker-compose.yml \
  .env.example rag scripts stock-research docs tests

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

## Documentation

- [How the stock recommender works](docs/how-stock-recommender-works.md)
- [pgvector/RDS setup](docs/setup-pgvector-rds.md)
