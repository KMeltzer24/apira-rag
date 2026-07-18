import os

STOCK_RESEARCH_DIR = os.environ.get("STOCK_RESEARCH_DIR", "/data/stock-research")
DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSION = int(os.environ.get("EMBEDDING_DIMENSION", "768"))

INGEST_EXTENSIONS = {".txt", ".md"}
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "100"))
DEFAULT_SEARCH_LIMIT = int(os.environ.get("RAG_SEARCH_LIMIT", "5"))
# Pause between embedding API calls to reduce 429 rate-limit errors on free tier.
EMBED_DELAY_SECONDS = float(os.environ.get("EMBED_DELAY_SECONDS", "0.7"))


def psycopg2_dsn(database_url: str) -> str:
    """Convert SQLAlchemy-style URL to a psycopg2 DSN."""
    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return database_url
