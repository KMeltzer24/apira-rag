"""MCP server for Apira tools: login, holdings, and stock research."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastmcp import FastMCP

from apira_logging import get_logger, log_event
from backend_tools import register_backend_tools
from rag.search import search_vector_db
from request_logging import RequestIdHeaderMiddleware, RequestLoggingMiddleware

STOCK_RESEARCH_DIR = os.environ.get("STOCK_RESEARCH_DIR", "/data/stock-research")
ALLOWED_EXTENSIONS = {".txt", ".md"}
MAX_FILE_BYTES = 32_000
MAX_TOTAL_BYTES = 96_000

logger = get_logger("apira-rag")
mcp = FastMCP("apira")
mcp.add_middleware(RequestLoggingMiddleware())
register_backend_tools(mcp)


def _resolve_research_dir() -> Path:
    root = Path(STOCK_RESEARCH_DIR).resolve()
    if not root.is_dir():
        raise FileNotFoundError(
            f"Stock research folder not found: {root}. "
            "Mount stock-research/ or set STOCK_RESEARCH_DIR."
        )
    return root


def _read_text_file(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="replace")
    content = content.replace("\x00", "")
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        content = content[:MAX_FILE_BYTES] + "\n\n[truncated]"
    return content


def _file_matches_query(path: Path, content: str, query: str) -> bool:
    if not query or query.strip() in {"*", "all"}:
        return True
    needle = query.casefold()
    return needle in path.name.casefold() or needle in content.casefold()


@mcp.tool()
async def searchLocalFolder(query: str = "") -> dict:
    """Search text and Markdown stock research in the stock-research folder."""
    root = _resolve_research_dir()
    matches = []
    total_bytes = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if path.name.startswith("._") or path.name.lower() == "readme.md":
            continue
        if not path.resolve().is_relative_to(root):
            continue

        content = _read_text_file(path)
        if not _file_matches_query(path, content, query):
            continue

        size = len(content.encode("utf-8"))
        if total_bytes + size > MAX_TOTAL_BYTES:
            break
        matches.append(
            {
                "filename": path.name,
                "relative_path": str(path.relative_to(root)),
                "content": content,
            }
        )
        total_bytes += size

    result = {
        "query": query or "all",
        "folder": str(root),
        "file_count": len(matches),
        "files": matches,
    }
    log_event(
        logger,
        logging.INFO,
        "rag.local_search.completed",
        f"Local folder search completed ({len(matches)} files)",
        match_count=len(matches),
        result_bytes=total_bytes,
    )
    return result


@mcp.tool()
async def searchVectorDB(query: str, limit: int = 5) -> dict:
    """Semantically search ingested stock research in PostgreSQL/pgvector."""
    return await asyncio.to_thread(search_vector_db, query, limit)


if __name__ == "__main__":
    from starlette.middleware import Middleware as ASGIMiddleware

    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("MCP_PORT", "8000")),
        path="/mcp",
        middleware=[ASGIMiddleware(RequestIdHeaderMiddleware)],
    )
