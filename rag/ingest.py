from pathlib import Path
import time

from rag.chunking import chunk_text
from rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBED_DELAY_SECONDS,
    INGEST_EXTENSIONS,
    STOCK_RESEARCH_DIR,
)
from rag.db import get_connection
from rag.embeddings import embed_text


def _research_root() -> Path:
    root = Path(STOCK_RESEARCH_DIR).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Stock research folder not found: {root}")
    return root


def _iter_ingest_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("._"):
            continue
        if path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() not in INGEST_EXTENSIONS:
            continue
        if not path.resolve().is_relative_to(root):
            continue
        files.append(path)
    return files


def _delete_chunks(conn, relative_path: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM research_chunks WHERE relative_path = %s",
            (relative_path,),
        )


def _delete_orphan_chunks(conn, valid_paths: set[str]) -> int:
    """Remove embeddings for files no longer in stock-research/."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT relative_path FROM research_chunks")
        existing = {row[0] for row in cur.fetchall()}
        orphans = sorted(existing - valid_paths)
        for relative_path in orphans:
            _delete_chunks(conn, relative_path)
    return len(orphans)


def _insert_chunk(
    conn,
    *,
    filename: str,
    relative_path: str,
    chunk_index: int,
    content: str,
    embedding: list[float],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO research_chunks
                (filename, relative_path, chunk_index, content, embedding)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (relative_path, chunk_index)
            DO UPDATE SET
                filename = EXCLUDED.filename,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                created_at = NOW()
            """,
            (filename, relative_path, chunk_index, content, embedding),
        )


def ingest_file(path: Path) -> dict:
    """Chunk, embed, and upsert one research file into pgvector."""
    root = _research_root()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"File must be under {root}: {path}")

    text = resolved.read_text(encoding="utf-8", errors="replace").strip()
    text = text.replace("\x00", "")
    if not text:
        return {
            "relative_path": str(resolved.relative_to(root)),
            "chunks": 0,
            "skipped": True,
            "reason": "empty file",
        }

    relative_path = str(resolved.relative_to(root))
    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

    with get_connection() as conn:
        _delete_chunks(conn, relative_path)
        for index, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            _insert_chunk(
                conn,
                filename=resolved.name,
                relative_path=relative_path,
                chunk_index=index,
                content=chunk,
                embedding=vector,
            )
            if EMBED_DELAY_SECONDS > 0 and index + 1 < len(chunks):
                time.sleep(EMBED_DELAY_SECONDS)

    return {
        "relative_path": relative_path,
        "chunks": len(chunks),
        "skipped": False,
    }


def ingest_all() -> dict:
    """Ingest every .txt / .md file under stock-research/."""
    root = _research_root()
    files = _iter_ingest_files(root)
    results = []
    total_chunks = 0

    for path in files:
        print(f"Ingesting {path.relative_to(root)} ...", flush=True)
        result = ingest_file(path)
        results.append(result)
        total_chunks += result.get("chunks", 0)
        print(f"  -> {result.get('chunks', 0)} chunks", flush=True)

    valid_paths = {result["relative_path"] for result in results}
    orphans_removed = 0
    with get_connection() as conn:
        orphans_removed = _delete_orphan_chunks(conn, valid_paths)

    return {
        "folder": str(root),
        "files_processed": len(results),
        "total_chunks": total_chunks,
        "orphans_removed": orphans_removed,
        "files": results,
    }
