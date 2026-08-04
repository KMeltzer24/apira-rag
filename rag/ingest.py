import hashlib
import logging
from pathlib import Path
import time

from apira_logging import get_logger, log_event
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
from rag.metadata import extract_document_date, extract_section_title, extract_ticker
from rag.schema import ensure_research_chunk_schema

logger = get_logger("apira-rag")


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


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _stored_content_hash(conn, relative_path: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content_hash
            FROM research_chunks
            WHERE relative_path = %s
            LIMIT 1
            """,
            (relative_path,),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _insert_chunk(
    conn,
    *,
    filename: str,
    relative_path: str,
    chunk_index: int,
    content: str,
    embedding: list[float],
    content_hash: str,
    ticker: str | None,
    document_date,
    section_title: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO research_chunks
                (
                    filename,
                    relative_path,
                    chunk_index,
                    content,
                    embedding,
                    content_hash,
                    ticker,
                    document_date,
                    section_title
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (relative_path, chunk_index)
            DO UPDATE SET
                filename = EXCLUDED.filename,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                content_hash = EXCLUDED.content_hash,
                ticker = EXCLUDED.ticker,
                document_date = EXCLUDED.document_date,
                section_title = EXCLUDED.section_title,
                created_at = NOW()
            """,
            (
                filename,
                relative_path,
                chunk_index,
                content,
                embedding,
                content_hash,
                ticker,
                document_date,
                section_title,
            ),
        )


def ingest_file(path: Path, *, force: bool = True) -> dict:
    """Chunk, embed, and upsert one research file into pgvector.

    When *force* is False, unchanged files (same content hash) are skipped.
    """
    started = time.perf_counter()
    ensure_research_chunk_schema()
    root = _research_root()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"File must be under {root}: {path}")

    text = resolved.read_text(encoding="utf-8", errors="replace").strip()
    text = text.replace("\x00", "")
    relative_path = str(resolved.relative_to(root))
    if not text:
        log_event(
            logger,
            logging.INFO,
            "rag.ingestion.file_skipped",
            f"Empty research file skipped: {resolved.name}",
            filename=resolved.name,
            chunk_count=0,
            reason="empty_file",
        )
        return {
            "relative_path": relative_path,
            "chunks": 0,
            "skipped": True,
            "reason": "empty file",
        }

    digest = _content_hash(text)
    ticker = extract_ticker(resolved, text)
    document_date = extract_document_date(resolved, text)

    with get_connection() as conn:
        if not force:
            existing = _stored_content_hash(conn, relative_path)
            if existing == digest:
                log_event(
                    logger,
                    logging.INFO,
                    "rag.ingestion.file_skipped",
                    f"Unchanged research file skipped: {resolved.name}",
                    filename=resolved.name,
                    chunk_count=0,
                    reason="unchanged_hash",
                    ticker=ticker,
                )
                return {
                    "relative_path": relative_path,
                    "chunks": 0,
                    "skipped": True,
                    "reason": "unchanged",
                    "ticker": ticker,
                    "document_date": document_date.isoformat() if document_date else None,
                }

        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
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
                content_hash=digest,
                ticker=ticker,
                document_date=document_date,
                section_title=extract_section_title(chunk),
            )
            if EMBED_DELAY_SECONDS > 0 and index + 1 < len(chunks):
                time.sleep(EMBED_DELAY_SECONDS)

    result = {
        "relative_path": relative_path,
        "chunks": len(chunks),
        "skipped": False,
        "ticker": ticker,
        "document_date": document_date.isoformat() if document_date else None,
    }
    log_event(
        logger,
        logging.INFO,
        "rag.ingestion.file_completed",
        f"Ingested {resolved.name} ({len(chunks)} chunks)",
        filename=resolved.name,
        chunk_count=len(chunks),
        ticker=ticker,
        document_date=result["document_date"],
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return result


def _ingest_many(files: list[Path], *, force: bool, event_prefix: str) -> dict:
    started = time.perf_counter()
    ensure_research_chunk_schema()
    root = _research_root()
    results = []
    total_chunks = 0
    skipped = 0

    ingest_kind = (
        "Full" if event_prefix == "rag.ingestion" else "Changed-only"
    )
    log_event(
        logger,
        logging.INFO,
        f"{event_prefix}.started",
        f"{ingest_kind} research corpus ingestion started ({len(files)} files)",
        file_count=len(files),
        force=force,
    )
    for path in files:
        log_event(
            logger,
            logging.DEBUG,
            "rag.ingestion.file_started",
            f"Research file ingestion started: {path.name}",
            filename=path.name,
        )
        result = ingest_file(path, force=force)
        results.append(result)
        total_chunks += result.get("chunks", 0)
        if result.get("skipped"):
            skipped += 1

    valid_paths = {str(path.relative_to(root)) for path in files}
    orphans_removed = 0
    with get_connection() as conn:
        orphans_removed = _delete_orphan_chunks(conn, valid_paths)

    result = {
        "folder": str(root),
        "files_processed": len(results),
        "files_ingested": len(results) - skipped,
        "files_skipped": skipped,
        "total_chunks": total_chunks,
        "orphans_removed": orphans_removed,
        "files": results,
    }
    log_event(
        logger,
        logging.INFO,
        f"{event_prefix}.completed",
        (
            f"{ingest_kind} research corpus ingestion completed "
            f"({result['files_ingested']} ingested, {skipped} skipped, "
            f"{total_chunks} chunks)"
        ),
        files_processed=len(results),
        files_ingested=result["files_ingested"],
        files_skipped=skipped,
        chunk_count=total_chunks,
        orphans_removed=orphans_removed,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return result


def ingest_all() -> dict:
    """Ingest every .txt / .md file under stock-research/ (full rebuild)."""
    root = _research_root()
    return _ingest_many(_iter_ingest_files(root), force=True, event_prefix="rag.ingestion")


def ingest_changed() -> dict:
    """Ingest only new or changed research files (skip unchanged content hashes)."""
    root = _research_root()
    return _ingest_many(
        _iter_ingest_files(root),
        force=False,
        event_prefix="rag.ingestion_changed",
    )
