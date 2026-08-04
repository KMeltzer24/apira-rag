"""Small, dependency-free structured logging and correlation helpers."""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime, timezone
import json
import logging
import os
import re
import sys
from typing import Any
from uuid import UUID, uuid4

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_SENSITIVE_KEYS = {
    "api_key",
    "arguments",
    "authorization",
    "content",
    "cookie",
    "database_url",
    "db_url",
    "embedding",
    "file_contents",
    "password",
    "prompt",
    "query",
    "request_body",
    "response_body",
    "secret",
    "token",
    "username",
    "vector",
}
_CREDENTIAL_URL = re.compile(r"^[a-z][a-z0-9+.-]*://[^/@\s]+:[^/@\s]+@", re.I)
_STANDARD_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)


def normalize_request_id(value: str | None) -> str:
    """Accept a UUID request ID or create a new one."""
    if value:
        try:
            return str(UUID(value.strip()))
        except (ValueError, AttributeError):
            pass
    return str(uuid4())


def set_request_id(value: str | None) -> Token:
    return _request_id.set(normalize_request_id(value))


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


def _sanitize(value: Any, key: str | None = None) -> Any:
    if key and key.casefold() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        if _CREDENTIAL_URL.search(value):
            return "[REDACTED]"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    """Render one safe JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": getattr(record, "service", "apira-rag"),
            "environment": getattr(
                record, "environment", os.getenv("ENVIRONMENT", "development")
            ),
            "event": getattr(record, "event", "application.log"),
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_KEYS and key not in payload:
                payload[key] = value
        return json.dumps(_sanitize(payload), separators=(",", ":"), sort_keys=True)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = get_request_id() or "-"
        event = getattr(record, "event", "application.log")
        return f"{record.levelname} {event} request_id={request_id} {record.getMessage()}"


_NOISY_THIRD_PARTY = (
    "httpx",
    "httpcore",
    "google_genai",
    "google.genai",
    "urllib3",
    "mcp",
    "mcp.client.streamable_http",
)


def _quiet_third_party_loggers() -> None:
    for name in _NOISY_THIRD_PARTY:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(service: str) -> logging.Logger:
    logger = logging.getLogger(service)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if os.getenv("LOG_FORMAT", "json").casefold() == "json"
        else TextFormatter()
    )
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    _quiet_third_party_loggers()
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    **fields: Any,
) -> None:
    # logging.LogRecord already owns keys like filename/module/name — remap
    # application fields so structured extras never collide.
    remapped: dict[str, Any] = {}
    for key, value in fields.items():
        safe_key = key
        if key in _STANDARD_RECORD_KEYS or key in {"message", "msg", "args"}:
            safe_key = f"field_{key}"
        remapped[safe_key] = value
    logger.log(level, message, extra={"event": event, **remapped})
