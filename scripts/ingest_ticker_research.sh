#!/usr/bin/env bash
# Embed the stock-research corpus into pgvector.
# PDFs and extracted/*.txt ship with the repo (like analyst notes) — nothing is re-downloaded.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export STOCK_RESEARCH_DIR="${STOCK_RESEARCH_DIR:-$ROOT/stock-research}"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"

python3 scripts/ingest_research.py

echo "Done."
