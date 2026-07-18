"""Extract useful text from research PDFs while removing low-value content."""

from __future__ import annotations

from collections import Counter
import math
import re
from pathlib import Path

from pypdf import PdfReader

# Patterns common on covers, legal pages, and navigation pages.
FLUFF_PATTERNS = (
    r"all rights reserved",
    r"©\s*\d{4}",
    r"copyright",
    r"table of contents",
    r"this page intentionally left blank",
    r"printed in the united states",
    r"isbn",
    r"terms of use",
    r"privacy policy",
    r"cookie policy",
    r"subscribe to our newsletter",
    r"follow us on",
    r"for more information visit",
    r"forward-looking statements disclaimer",
    r"safe harbor statement",
)

FLUFF_RE = re.compile("|".join(f"({p})" for p in FLUFF_PATTERNS), re.IGNORECASE | re.MULTILINE)

# Standalone lines that add no useful retrieval context.
NOISE_LINE_RE = re.compile(
    r"^(?:"
    r"page\s+\d+(?:\s+of\s+\d+)?"
    r"|\d+\s*/\s*\d+"
    r"|https?://\S+"
    r"|www\.\S+"
    r"|confidential"
    r"|proprietary(?:\s+and\s+confidential)?"
    r"|this page intentionally left blank"
    r")$",
    re.IGNORECASE,
)

# Words that suggest substantive investment or company content.
SIGNAL_WORDS = (
    "stock",
    "portfolio",
    "invest",
    "risk",
    "revenue",
    "earnings",
    "outlook",
    "asset allocation",
    "diversif",
    "10-k",
    "md&a",
    "dividend",
    "market",
    "equity",
    "etf",
    "bond",
    "financial",
    "company",
    "management",
    "rebalance",
    "holdings",
    "volatility",
    "sector",
    "sales",
    "income",
    "margin",
    "cash flow",
    "guidance",
    "quarter",
    "fiscal",
    "assets",
    "liabilities",
    "expenses",
    "capital expenditures",
    "eps",
    "earnings per share",
    "year over year",
)

FINANCIAL_TABLE_TERMS = (
    "net sales",
    "total revenue",
    "gross margin",
    "operating income",
    "net income",
    "earnings per share",
    "cash and cash equivalents",
    "total assets",
    "total liabilities",
    "statements of operations",
    "balance sheets",
    "cash flows",
)


def _normalize_text(text: str) -> str:
    """Normalize PDF extraction artifacts without flattening useful structure."""
    text = text.replace("\x00", "").replace("\xa0", " ")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _line_key(line: str) -> str:
    """Create a stable key for repeated headers whose page numbers vary."""
    key = line.casefold().strip()
    key = re.sub(r"\b\d+\b", "#", key)
    key = re.sub(r"\s+", " ", key)
    return key


def _edge_lines(text: str, count: int = 4) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:count] + lines[-count:]


def _repeated_edge_keys(pages: list[str]) -> set[str]:
    """Find headers/footers repeated across a meaningful share of pages."""
    if len(pages) < 3:
        return set()

    occurrences: Counter[str] = Counter()
    for text in pages:
        keys = {
            _line_key(line)
            for line in _edge_lines(text)
            if 3 <= len(line) <= 160 and not NOISE_LINE_RE.match(line)
        }
        occurrences.update(keys)

    threshold = max(3, math.ceil(len(pages) * 0.30))
    return {key for key, count in occurrences.items() if count >= threshold}


def _clean_page(text: str, repeated_edge_keys: set[str]) -> tuple[str, int]:
    """Remove repeated headers, footers, page numbers, and navigation lines."""
    normalized = _normalize_text(text)
    lines = normalized.splitlines()
    nonempty_indexes = [i for i, line in enumerate(lines) if line.strip()]
    edge_indexes = set(nonempty_indexes[:4] + nonempty_indexes[-4:])
    cleaned: list[str] = []
    removed = 0

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        if NOISE_LINE_RE.match(stripped):
            removed += 1
            continue
        if index in edge_indexes and _line_key(stripped) in repeated_edge_keys:
            removed += 1
            continue
        cleaned.append(stripped)

    return _normalize_text("\n".join(cleaned)), removed


def _page_metrics(text: str) -> tuple[int, int, int, int, int]:
    lower = text.lower()
    words = lower.split()
    word_count = len(words)
    signals = sum(1 for term in SIGNAL_WORDS if term in lower)
    fluff_hits = len(FLUFF_RE.findall(lower))
    financial_terms = sum(1 for term in FINANCIAL_TABLE_TERMS if term in lower)
    numeric_values = len(
        re.findall(r"(?:[$€£]\s*)?\(?\d[\d,.]*(?:\.\d+)?%?\)?", text)
    )
    return word_count, signals, fluff_hits, financial_terms, numeric_values


def fluff_reason(text: str) -> str | None:
    """Return why a page is low-value, or None when it should be retained."""
    stripped = text.strip()
    if not stripped:
        return "empty or image-only"

    word_count, signals, fluff_hits, financial_terms, numeric_values = _page_metrics(
        stripped
    )

    # Preserve compact earnings tables and summary slides even when text is short.
    if financial_terms >= 1 and numeric_values >= 4:
        return None
    if signals >= 3 and numeric_values >= 2:
        return None

    # Very short pages without financial substance are covers or divider slides.
    if word_count < 45:
        return "short page without financial substance"

    # Strong substance wins even if a footer contains legal language.
    if word_count >= 100 and signals >= 3:
        return None
    if word_count >= 180 and signals >= 2:
        return None

    # Mostly boilerplate with little investment vocabulary.
    if fluff_hits >= 2 and signals < 2:
        return "legal or publication boilerplate"
    if "table of contents" in stripped.casefold() and financial_terms == 0:
        return "table of contents"
    if signals == 0 and financial_terms == 0 and word_count < 140:
        return "low relevance"
    if fluff_hits >= 1 and signals <= 1 and word_count < 110:
        return "boilerplate with little financial content"

    return None


def is_fluff_page(text: str) -> bool:
    """Return True for pages with no useful company or investment content."""
    return fluff_reason(text) is not None


def extract_pdf_text(pdf_path: Path, *, skip_fluff: bool = True) -> dict:
    """Extract useful text and report exactly what was removed."""
    reader = PdfReader(str(pdf_path))
    raw_pages = [_normalize_text(page.extract_text() or "") for page in reader.pages]
    repeated_keys = _repeated_edge_keys(raw_pages) if skip_fluff else set()
    kept_parts: list[str] = []
    kept_pages: list[int] = []
    skipped_pages: list[int] = []
    skipped_page_details: list[dict] = []
    removed_boilerplate_lines = 0

    for index, raw_text in enumerate(raw_pages, start=1):
        if skip_fluff:
            text, removed = _clean_page(raw_text, repeated_keys)
            removed_boilerplate_lines += removed
        else:
            text = raw_text
        if not text:
            skipped_pages.append(index)
            skipped_page_details.append(
                {"page": index, "reason": "empty or image-only"}
            )
            continue
        reason = fluff_reason(text) if skip_fluff else None
        if reason:
            skipped_pages.append(index)
            skipped_page_details.append({"page": index, "reason": reason})
            continue
        kept_parts.append(f"[Page {index}]\n{text}")
        kept_pages.append(index)

    return {
        "text": "\n\n".join(kept_parts),
        "total_pages": len(reader.pages),
        "pages_kept": kept_pages,
        "pages_skipped": skipped_pages,
        "pages_skipped_details": skipped_page_details,
        "removed_boilerplate_lines": removed_boilerplate_lines,
    }
