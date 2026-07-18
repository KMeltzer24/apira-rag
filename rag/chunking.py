def _preferred_break(text: str, start: int, target: int, minimum: int) -> int:
    """Choose a readable boundary near the target instead of cutting words."""
    for separator in ("\n\n", "\n", ". ", "; ", ", ", " "):
        index = text.rfind(separator, minimum, target)
        if index != -1:
            return index + len(separator)
    return target


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks at paragraph/sentence boundaries."""
    cleaned = text.strip()
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        target = min(start + chunk_size, len(cleaned))
        minimum = start + int(chunk_size * 0.60)
        end = (
            _preferred_break(cleaned, start, target, minimum)
            if target < len(cleaned)
            else target
        )
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break

        next_start = max(end - overlap, start + 1)
        # Avoid beginning the overlap in the middle of a word.
        if next_start > 0 and not cleaned[next_start - 1].isspace():
            whitespace = cleaned.find(" ", next_start, min(end, next_start + 60))
            if whitespace != -1:
                next_start = whitespace + 1
        start = next_start

    return [chunk for chunk in chunks if chunk]
