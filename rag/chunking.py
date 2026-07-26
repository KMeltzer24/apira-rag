"""Section-aware text chunking for research documents."""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"(?m)^(#{1,6}\s+\S.*)$")
_SOURCE_RE = re.compile(r"(?m)^(Source:\s+\S.*)$", re.I)


def _preferred_break(text: str, start: int, target: int, minimum: int) -> int:
    """Choose a readable boundary near the target instead of cutting words."""
    for separator in ("\n\n", "\n", ". ", "; ", ", ", " "):
        index = text.rfind(separator, minimum, target)
        if index != -1:
            return index + len(separator)
    return target


def _split_sections(text: str) -> list[str]:
    """Split on markdown headings / Source lines while keeping the heading."""
    markers: list[int] = []
    for pattern in (_HEADING_RE, _SOURCE_RE):
        markers.extend(match.start() for match in pattern.finditer(text))
    if not markers:
        return [text]

    starts = sorted({0, *markers})
    sections: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        piece = text[start:end].strip()
        if piece:
            sections.append(piece)
    return sections or [text]


def _window_chunk(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        target = min(start + chunk_size, len(text))
        minimum = start + int(chunk_size * 0.60)
        end = (
            _preferred_break(text, start, target, minimum)
            if target < len(text)
            else target
        )
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break

        next_start = max(end - overlap, start + 1)
        if next_start > 0 and not text[next_start - 1].isspace():
            whitespace = text.find(" ", next_start, min(end, next_start + 60))
            if whitespace != -1:
                next_start = whitespace + 1
        start = next_start

    return [chunk for chunk in chunks if chunk]


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks, preferring section then sentence breaks."""
    cleaned = text.strip()
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    chunks: list[str] = []
    for section in _split_sections(cleaned):
        chunks.extend(_window_chunk(section, chunk_size, overlap))
    return chunks
