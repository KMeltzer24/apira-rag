#!/usr/bin/env bash
# Fetch recent earnings Exhibit 99.1 HTML from SEC for tickers without stable public PDFs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export STOCK_RESEARCH_DIR="${STOCK_RESEARCH_DIR:-$ROOT/stock-research}"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"

run_fetch() {
  local url="$1"
  local name="$2"
  echo "=== $name ==="
  python3 scripts/fetch_sec_exhibit.py "$url" "$name" --skip-ingest
  echo ""
}

run_fetch \
  "https://www.sec.gov/Archives/edgar/data/789019/000119312526191457/msft-ex99_1.htm" \
  "msft-q3-fy2026-earnings"

run_fetch \
  "https://www.sec.gov/Archives/edgar/data/1652044/000165204425000087/googexhibit991q32025.htm" \
  "googl-q3-2025-earnings"

run_fetch \
  "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000012/amzn-20260331xex991.htm" \
  "amzn-q1-2026-earnings"

echo "Done. Earnings text saved under stock-research/extracted/ and embedded in pgvector."
