# Ticker research PDFs

These PDFs are **committed to the repo** and deploy to EC2 with the rest of `stock-research/` — same as the analyst `.md` / `.txt` files. They are **not** re-downloaded on each deploy or ingest.

| File | Ticker | Source |
|------|--------|--------|
| `aapl-fy2025-q4-earnings.pdf` | AAPL | [Apple newsroom](https://www.apple.com/newsroom/pdfs/fy2025-q4/) |
| `tsla-q1-2026-update.pdf` | TSLA | [Tesla IR / SEC](https://ir.tesla.com/) |

Extracted text lives in `../extracted/`:

| File | Origin |
|------|--------|
| `*.from-pdf.txt` | Text extracted from a PDF in this folder (header cites source PDF) |
| `*.from-sec.txt` | Text from SEC Exhibit 99.1 HTML (MSFT, GOOGL, AMZN) |

## Normal use (EC2)

Deploy includes PDFs + extracted text. Embed into pgvector:

```bash
sudo docker compose run --rm mcp-server bash scripts/ingest_ticker_research.sh
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
