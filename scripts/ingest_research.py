#!/usr/bin/env python3
"""Ingest all .txt / .md files from stock-research/ into pgvector."""

from __future__ import annotations

import sys

from rag.ingest import ingest_all


def main() -> int:
    try:
        result = ingest_all()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Ingest complete.")
    print(f"  folder:          {result['folder']}")
    print(f"  files processed: {result['files_processed']}")
    print(f"  total chunks:    {result['total_chunks']}")
    if result.get("orphans_removed"):
        print(f"  orphans removed: {result['orphans_removed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
