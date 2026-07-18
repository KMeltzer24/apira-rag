#!/usr/bin/env bash
# Re-extract PDFs and atomically refresh each file in the vector index.
# Requires Gemini embedding quota (run after Pacific midnight or with billing enabled).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export STOCK_RESEARCH_DIR="${STOCK_RESEARCH_DIR:-$ROOT/stock-research}"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"

EXTRACTED="$STOCK_RESEARCH_DIR/extracted"
PDF_DIR="$STOCK_RESEARCH_DIR/pdfs"

echo "=== Remove legacy extract files (pre .from-pdf / .from-sec naming) ==="
for legacy in \
  "$EXTRACTED/aapl-fy2025-q4-earnings.txt" \
  "$EXTRACTED/tsla-q1-2026-update.txt" \
  "$EXTRACTED/msft-q3-fy2026-earnings.txt" \
  "$EXTRACTED/googl-q3-2025-earnings.txt" \
  "$EXTRACTED/amzn-q1-2026-earnings.txt" \
  "$EXTRACTED"/sec-*.txt
do
  [ -e "$legacy" ] || continue
  echo "  rm $legacy"
  rm -f "$legacy"
done
rm -f "$EXTRACTED"/._* 2>/dev/null || true

echo "=== Re-extract PDFs with current filtering rules ==="
for pdf in "$PDF_DIR"/*.pdf; do
  [ -e "$pdf" ] || continue
  python3 scripts/pdf_inject.py "$pdf" --skip-ingest
done

echo "=== Re-ingest committed corpus (slow; one line per file) ==="
# ingest_file replaces one file in a transaction, so a quota error leaves that
# file's previous chunks intact. ingest_all removes orphaned legacy paths after
# every current file succeeds.
python3 scripts/ingest_research.py

echo "Done."
