#!/usr/bin/env bash
# One-time / rare refresh: re-download PDFs, re-fetch SEC HTML, re-extract, then ingest.
# Normal deploys should NOT run this — use ingest_ticker_research.sh instead.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export STOCK_RESEARCH_DIR="${STOCK_RESEARCH_DIR:-$ROOT/stock-research}"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"

python3 scripts/download_ticker_pdfs.py
bash scripts/fetch_ticker_earnings.sh

echo "=== Extracting PDFs (no embed yet) ==="
for pdf in "$STOCK_RESEARCH_DIR"/pdfs/*.pdf; do
  [ -f "$pdf" ] || continue
  echo "--- $pdf ---"
  python3 scripts/pdf_inject.py "$pdf" --skip-ingest
done

echo "=== Full ingest ==="
python3 scripts/ingest_research.py

echo "Done. Commit updated files under stock-research/pdfs/ and stock-research/extracted/."
