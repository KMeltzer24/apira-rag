"""Extract ticker and document date metadata from research files."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
_FILENAME_TICKER_RE = re.compile(r"^([a-z]{1,5})[-_]", re.I)
_FY_Q_RE = re.compile(r"fy\s*(\d{4})\s*[-_]?q([1-4])", re.I)
_Q_FY_RE = re.compile(r"q([1-4])\s*[-_]?fy\s*(\d{4})", re.I)
_Q_YEAR_RE = re.compile(r"q([1-4])\s*[-_]?(\d{4})", re.I)
_ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Approximate quarter-end dates used when only FY/Q is known.
_QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


def extract_ticker(path: Path, text: str = "") -> str | None:
    """Best-effort ticker from filename stem or research-note header."""
    match = _FILENAME_TICKER_RE.match(path.name)
    if match:
        return match.group(1).upper()

    header = "\n".join(text.splitlines()[:8])
    note = re.search(r"\(([A-Z]{1,5})\)\s*—", header)
    if note:
        return note.group(1)

    tickers = _TICKER_RE.findall(header)
    for candidate in tickers:
        if candidate not in {"PDF", "SEC", "EX", "HTML", "HTTP", "HTTPS"}:
            return candidate
    return None


def _quarter_date(year: int, quarter: int) -> date:
    month, day = _QUARTER_END[quarter]
    return date(year, month, day)


def extract_document_date(path: Path, text: str = "") -> date | None:
    """Parse a document date from filename patterns or an ISO date in the header."""
    stem = path.stem.lower().replace(".from-pdf", "").replace(".from-sec", "")
    for pattern, groups in (
        (_FY_Q_RE, ("year", "quarter")),
        (_Q_FY_RE, ("quarter", "year")),
        (_Q_YEAR_RE, ("quarter", "year")),
    ):
        match = pattern.search(stem)
        if not match:
            continue
        if groups == ("year", "quarter"):
            year, quarter = int(match.group(1)), int(match.group(2))
        else:
            quarter, year = int(match.group(1)), int(match.group(2))
        return _quarter_date(year, quarter)

    header = "\n".join(text.splitlines()[:12])
    iso = _ISO_DATE_RE.search(header) or _ISO_DATE_RE.search(stem)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    year_match = _YEAR_RE.search(stem)
    if year_match:
        return date(int(year_match.group(1)), 12, 31)
    return None


def extract_section_title(chunk: str) -> str | None:
    """Return a markdown/section heading from the start of a chunk, if present."""
    for line in chunk.splitlines()[:5]:
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            return title[:200] if title else None
        if stripped.lower().startswith("source:"):
            return stripped[:200]
    return None
