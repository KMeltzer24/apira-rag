#!/usr/bin/env python3
"""Extract text from a PDF into stock-research/ and ingest into pgvector."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from rag.config import STOCK_RESEARCH_DIR
from rag.pdf_extract import extract_pdf_text


def inject_pdf(
    pdf_path: Path,
    research_dir: Path,
    *,
    skip_fluff: bool = True,
    skip_ingest: bool = False,
) -> dict:
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file: {pdf_path}")

    research_dir = research_dir.resolve()
    research_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = research_dir / "pdfs"
    extracted_dir = research_dir / "extracted"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    extraction = extract_pdf_text(pdf_path, skip_fluff=skip_fluff)
    text = extraction["text"].replace("\x00", "")
    if not text.strip():
        raise ValueError(
            f"No useful text found in {pdf_path.name}. "
            "Try again with --include-all-pages."
        )

    copied_pdf = pdf_dir / pdf_path.name
    if pdf_path.resolve() != copied_pdf.resolve():
        shutil.copy2(pdf_path, copied_pdf)

    pdf_ref = f"pdfs/{copied_pdf.name}"
    txt_path = extracted_dir / f"{pdf_path.stem}.from-pdf.txt"
    body = f"# Source: PDF — {pdf_ref}\n\n{text}"
    txt_path.write_text(body, encoding="utf-8")

    if skip_ingest:
        ingest_result = {"chunks": 0, "skipped": True, "reason": "skip_ingest"}
    else:
        from rag.ingest import ingest_file

        ingest_result = ingest_file(txt_path)
    return {
        "source_pdf": str(pdf_path),
        "stored_pdf": str(copied_pdf.relative_to(research_dir)),
        "extracted_txt": str(txt_path.relative_to(research_dir)),
        "characters_extracted": len(text),
        "total_pages": extraction["total_pages"],
        "pages_kept": extraction["pages_kept"],
        "pages_skipped": extraction["pages_skipped"],
        "pages_skipped_details": extraction["pages_skipped_details"],
        "removed_boilerplate_lines": extraction["removed_boilerplate_lines"],
        "skip_fluff": skip_fluff,
        "ingest": ingest_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inject a PDF into stock-research and ingest into pgvector."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=Path(STOCK_RESEARCH_DIR),
        help="Target stock-research directory (default: STOCK_RESEARCH_DIR env)",
    )
    parser.add_argument(
        "--include-all-pages",
        action="store_true",
        help="Do not skip cover, copyright, or TOC-style pages",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Extract text only; do not embed into pgvector",
    )
    args = parser.parse_args()

    try:
        result = inject_pdf(
            args.pdf,
            args.research_dir,
            skip_fluff=not args.include_all_pages,
            skip_ingest=args.skip_ingest,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("PDF injected successfully.")
    print(f"  stored PDF:      {result['stored_pdf']}")
    print(f"  extracted text:  {result['extracted_txt']}")
    print(f"  pages kept:      {result['pages_kept']} / {result['total_pages']}")
    if result["pages_skipped"]:
        print(f"  pages skipped:   {result['pages_skipped']} (fluff / empty)")
        for detail in result["pages_skipped_details"]:
            print(f"    page {detail['page']}: {detail['reason']}")
    if result["removed_boilerplate_lines"]:
        print(
            "  repeated/noise lines removed: "
            f"{result['removed_boilerplate_lines']}"
        )
    print(f"  characters:      {result['characters_extracted']}")
    print(f"  chunks ingested: {result['ingest']['chunks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
