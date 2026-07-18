#!/usr/bin/env python3
"""List or purge rows in research_chunks (pgvector index)."""

from __future__ import annotations

import argparse
import sys

from rag.ingest import _delete_orphan_chunks, _iter_ingest_files, _research_root
from rag.db import get_connection


def list_sources() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT relative_path, COUNT(*) AS chunks
                FROM research_chunks
                GROUP BY relative_path
                ORDER BY relative_path
                """
            )
            rows = cur.fetchall()
    total = sum(r[1] for r in rows)
    print(f"Total chunks: {total}")
    print(f"Distinct files: {len(rows)}")
    print()
    for path, count in rows:
        print(f"  {count:4d}  {path}")


def purge_stale() -> int:
    """Delete embeddings for files no longer on disk under stock-research/."""
    root = _research_root()
    files = _iter_ingest_files(root)
    valid_paths = {str(p.resolve().relative_to(root)) for p in files}
    with get_connection() as conn:
        return _delete_orphan_chunks(conn, valid_paths)


def purge_all() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM research_chunks")
            before = cur.fetchone()[0]
            cur.execute("DELETE FROM research_chunks")
    return before


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage research_chunks in RDS.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List embedded paths")
    group.add_argument(
        "--purge-stale",
        action="store_true",
        help="Remove chunks whose path is not a current .md/.txt on disk",
    )
    group.add_argument(
        "--purge-all",
        action="store_true",
        help="Delete every row in research_chunks (clean slate before re-ingest)",
    )
    args = parser.parse_args()

    try:
        if args.list:
            list_sources()
            return 0
        if args.purge_stale:
            removed = purge_stale()
            print(f"Removed {removed} stale file path(s) from research_chunks.")
            return 0
        if args.purge_all:
            removed = purge_all()
            print(f"Deleted {removed} chunk row(s) from research_chunks.")
            return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
