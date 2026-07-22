"""FastMCP request correlation and safe tool lifecycle logging."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext

from apira_logging import (
    get_logger,
    get_request_id,
    log_event,
    normalize_request_id,
    reset_request_id,
    set_request_id,
)

logger = get_logger("apira-rag")


class RequestIdHeaderMiddleware:
    """Add a canonical request ID to the ASGI request and response."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = list(scope.get("headers", []))
        incoming = next(
            (
                value.decode("latin-1")
                for key, value in headers
                if key.lower() == b"x-request-id"
            ),
            None,
        )
        request_id = normalize_request_id(incoming)
        scope = dict(scope)
        scope["headers"] = [
            (key, value) for key, value in headers if key.lower() != b"x-request-id"
        ] + [(b"x-request-id", request_id.encode("ascii"))]

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                response_headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                message = dict(message)
                message["headers"] = response_headers + [
                    (b"x-request-id", request_id.encode("ascii"))
                ]
            await send(message)

        token = set_request_id(request_id)
        try:
            return await self.app(scope, receive, send_with_request_id)
        finally:
            reset_request_id(token)


class RequestLoggingMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        headers = get_http_headers() or {}
        incoming = headers.get("x-request-id") or headers.get("X-Request-ID")
        token = set_request_id(incoming)
        try:
            return await call_next(context)
        finally:
            reset_request_id(token)

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        own_token = None
        if get_request_id() is None:
            own_token = set_request_id(None)

        tool_name = context.message.name
        arguments = context.message.arguments or {}
        fields = {
            "tool_name": tool_name,
            "arg_keys": sorted(str(key) for key in arguments),
        }
        started = perf_counter()
        log_event(
            logger,
            logging.INFO,
            "mcp.tool.started",
            "Tool call started",
            **fields,
        )
        try:
            result = await call_next(context)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "mcp.tool.failed",
                "Tool call failed",
                **fields,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                error_type=type(exc).__name__,
            )
            raise
        else:
            log_event(
                logger,
                logging.INFO,
                "mcp.tool.completed",
                "Tool call completed",
                **fields,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            return result
        finally:
            if own_token is not None:
                reset_request_id(own_token)
