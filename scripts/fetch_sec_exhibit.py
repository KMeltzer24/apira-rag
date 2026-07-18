#!/usr/bin/env python3
"""Fetch an SEC Exhibit 99.1 (HTML) earnings release into stock-research/extracted/."""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
from pathlib import Path

from rag.config import STOCK_RESEARCH_DIR

SEC_USER_AGENT = "ApiraDemoBot/1.0 (mentorship learning project; contact: local-dev)"


def _strip_html(raw: str) -> str:
    """Convert SEC/iXBRL HTML to plain text."""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = re.sub(r"(?i)</tr\s*>", "\n", text)
    text = re.sub(r"(?i)</td\s*>", "\t", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def fetch_exhibit(
    url: str,
    output_name: str,
    *,
    research_dir: Path | None = None,
    skip_ingest: bool = False,
) -> dict:
    research_dir = (research_dir or Path(STOCK_RESEARCH_DIR)).resolve()
    extracted_dir = research_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")

    text = _strip_html(raw).replace("\x00", "")
    if len(text) < 200:
        raise ValueError(f"Extracted text from {url} looks too short ({len(text)} chars).")

    if output_name.endswith(".txt"):
        output_name = output_name[: -len(".txt")]
    txt_path = extracted_dir / f"{output_name}.from-sec.txt"
    body = f"# Source: SEC Exhibit 99.1 — {url}\n\n{text}"
    txt_path.write_text(body, encoding="utf-8")

    if skip_ingest:
        ingest_result = {"chunks": 0, "skipped": True, "reason": "skip_ingest"}
    else:
        from rag.ingest import ingest_file

        ingest_result = ingest_file(txt_path)
    return {
        "source_url": url,
        "extracted_txt": str(txt_path.relative_to(research_dir)),
        "characters_extracted": len(text),
        "ingest": ingest_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch SEC Exhibit 99.1 HTML and ingest into pgvector."
    )
    parser.add_argument("url", help="SEC exhibit URL (HTML)")
    parser.add_argument(
        "output_name",
        help="Output filename under stock-research/extracted/ (e.g. msft-q3-2026-earnings)",
    )
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=Path(STOCK_RESEARCH_DIR),
        help="Target stock-research directory",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Extract text only; do not embed into pgvector",
    )
    args = parser.parse_args()

    try:
        result = fetch_exhibit(
            args.url,
            args.output_name,
            research_dir=args.research_dir,
            skip_ingest=args.skip_ingest,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("SEC exhibit ingested successfully.")
    print(f"  source URL:      {result['source_url']}")
    print(f"  extracted text:  {result['extracted_txt']}")
    print(f"  characters:      {result['characters_extracted']}")
    print(f"  chunks ingested: {result['ingest']['chunks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
