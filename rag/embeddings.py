import os
import time

from google import genai
from google.genai import types

from rag.config import EMBEDDING_MODEL, GOOGLE_API_KEY


def _client() -> genai.Client:
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Required for embeddings and searchVectorDB."
        )
    return genai.Client(api_key=GOOGLE_API_KEY)


def _model_name() -> str:
    return EMBEDDING_MODEL.removeprefix("models/")


def embed_text(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Return an embedding vector for document chunks or queries."""
    client = _client()
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = client.models.embed_content(
                model=_model_name(),
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=768,
                ),
            )
            values = response.embeddings[0].values
            if not values:
                raise RuntimeError("Embedding API returned no values.")
            return list(values)
        except Exception as exc:
            last_error = exc
            message = str(exc)
            if "429" not in message and "RESOURCE_EXHAUSTED" not in message:
                raise
            time.sleep(min(30, 5 * (attempt + 1)))
    raise last_error  # type: ignore[misc]
