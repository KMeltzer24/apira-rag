import logging
import time

from google import genai
from google.genai import types

from apira_logging import get_logger, log_event
from rag.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL, GOOGLE_API_KEY

logger = get_logger("apira-rag")


def _client() -> genai.Client:
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Required for embeddings and searchVectorDB."
        )
    return genai.Client(api_key=GOOGLE_API_KEY)


def _model_name() -> str:
    return EMBEDDING_MODEL.removeprefix("models/")


def _is_rate_limited(exc: Exception) -> bool:
    message = str(exc)
    return "429" in message or "RESOURCE_EXHAUSTED" in message


def embed_text(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Return an embedding vector for document chunks or queries."""
    client = _client()
    last_error: Exception | None = None
    for attempt in range(4):
        started = time.perf_counter()
        log_event(
            logger,
            logging.DEBUG,
            "rag.embedding.started",
            f"Embedding started ({task_type}, attempt {attempt + 1})",
            model=_model_name(),
            task_type=task_type,
            attempt=attempt + 1,
            input_length=len(text),
        )
        try:
            response = client.models.embed_content(
                model=_model_name(),
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBEDDING_DIMENSION,
                ),
            )
            values = response.embeddings[0].values
            if not values:
                raise RuntimeError("Embedding API returned no values.")
            log_event(
                logger,
                logging.DEBUG,
                "rag.embedding.completed",
                f"Embedding completed ({len(values)} dims)",
                model=_model_name(),
                task_type=task_type,
                attempt=attempt + 1,
                vector_dimension=len(values),
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return list(values)
        except Exception as exc:
            last_error = exc
            if not _is_rate_limited(exc):
                log_event(
                    logger,
                    logging.ERROR,
                    "rag.embedding.failed",
                    "Embedding request failed",
                    model=_model_name(),
                    task_type=task_type,
                    attempt=attempt + 1,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    error_type=type(exc).__name__,
                )
                raise
            if attempt == 3:
                break
            delay_seconds = min(30, 5 * (attempt + 1))
            log_event(
                logger,
                logging.WARNING,
                "rag.embedding.rate_limited",
                "Embedding request rate limited; retrying",
                model=_model_name(),
                task_type=task_type,
                attempt=attempt + 1,
                retry_in_seconds=delay_seconds,
                error_code=429,
            )
            time.sleep(delay_seconds)
    log_event(
        logger,
        logging.ERROR,
        "rag.embedding.failed",
        "Embedding request failed after retries",
        model=_model_name(),
        task_type=task_type,
        attempts=4,
        error_type=type(last_error).__name__,
        error_code=429,
    )
    raise last_error  # type: ignore[misc]
