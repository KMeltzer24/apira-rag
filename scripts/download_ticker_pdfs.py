#!/usr/bin/env python3
"""Download public, ticker-specific PDFs into stock-research/pdfs/."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from rag.config import STOCK_RESEARCH_DIR

UA = "ApiraDemoBot/1.0 (mentorship learning project)"
DEST = Path(STOCK_RESEARCH_DIR).resolve() / "pdfs"

PDFS = (
    (
        "https://www.apple.com/newsroom/pdfs/fy2025-q4/FY25_Q4_Consolidated_Financial_Statements.pdf",
        "aapl-fy2025-q4-earnings.pdf",
    ),
    (
        "https://ir.tesla.com/_flysystem/s3/sec/000162828026026551/tsla-20260422-gen.pdf",
        "tsla-q1-2026-update.pdf",
    ),
)


def download(url: str, name: str) -> None:
    dest = DEST / name
    print(f"Downloading {name} ...")
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=120) as response:
        dest.write_bytes(response.read())


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for url, name in PDFS:
        download(url, name)
    print(f"Done. PDFs saved to {DEST}")
    print()
    print("MSFT, GOOGL, and AMZN earnings are fetched from SEC Exhibit 99.1 HTML:")
    print("  bash scripts/fetch_ticker_earnings.sh")


if __name__ == "__main__":
    main()
