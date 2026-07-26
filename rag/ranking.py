"""Post-filters for vector search ranking."""

from __future__ import annotations


def prefer_newer(rows: list[tuple], limit: int) -> list[tuple]:
    """Keep highest-similarity chunks, dropping older docs when a newer one exists.

    Rows: filename, relative_path, chunk_index, content, similarity,
          ticker, document_date, section_title
    """
    newest_by_ticker: dict[str, object] = {}
    for row in rows:
        ticker = row[5]
        doc_date = row[6]
        if not ticker or doc_date is None:
            continue
        current = newest_by_ticker.get(ticker)
        if current is None or doc_date > current:
            newest_by_ticker[ticker] = doc_date

    selected: list[tuple] = []
    for row in rows:
        ticker = row[5]
        doc_date = row[6]
        newest = newest_by_ticker.get(ticker) if ticker else None
        if newest is not None and doc_date is not None and doc_date < newest:
            continue
        selected.append(row)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        selected_ids = {id(row) for row in selected}
        for row in rows:
            if id(row) in selected_ids:
                continue
            selected.append(row)
            if len(selected) >= limit:
                break
    return selected[:limit]
