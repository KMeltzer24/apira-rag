#!/usr/bin/env bash
# Download public, ticker-specific PDFs for the stock-research demo corpus.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/download_ticker_pdfs.py"
