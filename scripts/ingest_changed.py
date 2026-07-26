#!/usr/bin/env python3
"""Ingest only new or changed research files into pgvector."""

from __future__ import annotations

import sys

from rag.ingest import ingest_changed


def main() -> int:
    try:
        result = ingest_changed()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Changed-file ingest complete.")
    print(f"  folder:          {result['folder']}")
    print(f"  files scanned:   {result['files_processed']}")
    print(f"  files ingested:  {result['files_ingested']}")
    print(f"  files skipped:   {result['files_skipped']}")
    print(f"  total chunks:    {result['total_chunks']}")
    if result.get("orphans_removed"):
        print(f"  orphans removed: {result['orphans_removed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
