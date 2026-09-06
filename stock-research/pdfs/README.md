# Ticker research PDFs

These PDFs are **committed to the repo** with the rest of `stock-research/` — same as the analyst `.md` / `.txt` files. They are **not** re-downloaded on each start or ingest.

| File | Ticker | Source |
|------|--------|--------|
| `aapl-fy2025-q4-earnings.pdf` | AAPL | [Apple newsroom FY25 Q4](https://www.apple.com/newsroom/pdfs/fy2025-q4/) |
| `aapl-fy2026-q2-earnings.pdf` | AAPL | [Apple newsroom FY26 Q2](https://www.apple.com/newsroom/pdfs/fy2026q2/) (newer — prefer-newer test) |
| `tsla-q1-2026-update.pdf` | TSLA | [Tesla IR / SEC](https://ir.tesla.com/) |
| `tsla-q2-2026-update.pdf` | TSLA | [Tesla Q2 2026 Update](https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf) (newer — prefer-newer test) |

Extracted text lives in `../extracted/`:

| File | Origin |
|------|--------|
| `*.from-pdf.txt` | Text extracted from a PDF in this folder (header cites source PDF) |
| `*.from-sec.txt` | Text from SEC Exhibit 99.1 HTML (MSFT, GOOGL, AMZN) |

Newer same-ticker pairs for **prefer-newer** ranking tests:

| Older | Newer | Parsed `document_date` |
|-------|-------|-------------------------|
| `aapl-fy2025-q4-…` | `aapl-fy2026-q2-…` | 2025-12-31 → **2026-06-30** |
| `tsla-q1-2026-…` | `tsla-q2-2026-…` | 2026-03-31 → **2026-06-30** |
| `msft-q3-fy2026-…` | `msft-q4-fy2026-…` | 2026-09-30 → **2026-12-31** |

After adding files, run `scripts/ingest_changed.py` (or full ingest) so pgvector picks them up.

## Normal use

Embed into local Postgres pgvector:

```bash
docker compose run --rm rag-server bash scripts/ingest_ticker_research.sh
```

That **only embeds** — it does not download anything new.

## Adding or updating research (rare)

Only when you intentionally want new filings:

```bash
bash scripts/refresh_ticker_corpus.sh   # re-download, re-extract, ingest
git add stock-research/pdfs/ stock-research/extracted/
git commit && git push
```

## Inject one new PDF manually

```bash
python scripts/pdf_inject.py stock-research/pdfs/your-file.pdf
```

Creates `extracted/your-file.from-pdf.txt` with header `# Source: PDF — pdfs/your-file.pdf`.
