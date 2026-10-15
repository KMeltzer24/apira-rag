"""MCP tools that wrap Apira REST login, holdings, and last recommendation."""

from __future__ import annotations

import logging
import os
from time import perf_counter
from urllib.parse import urlparse

import httpx
from fastmcp import FastMCP

from apira_logging import get_logger, get_request_id, log_event

USER_SERVICE_URL = os.environ.get(
    "USER_SERVICE_URL", "http://host.docker.internal:8001"
)
PORTFOLIO_SERVICE_URL = os.environ.get(
    "PORTFOLIO_SERVICE_URL", "http://host.docker.internal:8002"
)
UPSTREAM_TIMEOUT = httpx.Timeout(10.0)

logger = get_logger("apira-rag")


async def _upstream_request(
    upstream: str, method: str, url: str, **kwargs
) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    request_id = get_request_id()
    if request_id:
        headers["X-Request-ID"] = request_id

    path = urlparse(url).path or "/"
    started = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "upstream.request.failed",
            f"Upstream {upstream} {method} {path} failed ({type(exc).__name__})",
            upstream=upstream,
            method=method,
            path=path,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            error_type=type(exc).__name__,
        )
        raise

    duration_ms = round((perf_counter() - started) * 1000, 2)
    if response.is_error:
        log_event(
            logger,
            logging.WARNING,
            "upstream.request.failed",
            f"Upstream {upstream} {method} {path} returned {response.status_code}",
            upstream=upstream,
            method=method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            error_type="HTTPStatusError",
        )
    else:
        log_event(
            logger,
            logging.INFO,
            "upstream.request.completed",
            f"Upstream {upstream} {method} {path} completed ({response.status_code})",
            upstream=upstream,
            method=method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
    response.raise_for_status()
    return response


async def login(username: str, password: str) -> dict:
    """Authenticate a user and return user_id."""
    response = await _upstream_request(
        "user-service",
        "POST",
        f"{USER_SERVICE_URL}/login",
        json={"username": username, "password": password},
    )
    payload = response.json()
    log_event(
        logger,
        logging.INFO,
        "mcp.login.completed",
        "login completed",
        user_id=payload.get("user_id"),
    )
    return payload


async def get_portfolio(user_id: int) -> dict:
    """Return portfolio holdings for a user_id."""
    response = await _upstream_request(
        "portfolio-service",
        "GET",
        f"{PORTFOLIO_SERVICE_URL}/portfolio",
        params={"user_id": user_id},
    )
    payload = response.json()
    holdings = payload.get("holdings") or []
    tickers = [
        item.get("ticker")
        for item in holdings
        if isinstance(item, dict) and item.get("ticker")
    ]
    log_event(
        logger,
        logging.INFO,
        "mcp.portfolio.completed",
        f"get_portfolio completed ({len(holdings)} holdings)",
        user_id=user_id,
        holdings_count=len(holdings),
        tickers=tickers,
        holdings_summary=[
            {"ticker": item.get("ticker"), "shares": item.get("shares")}
            for item in holdings
            if isinstance(item, dict)
        ],
    )
    return payload


async def getPreviousRecommendation(user_id: int) -> dict:
    """Return the last saved recommendation for a user_id, or body null if none."""
    response = await _upstream_request(
        "portfolio-service",
        "GET",
        f"{PORTFOLIO_SERVICE_URL}/recommendation",
        params={"user_id": user_id},
    )
    payload = response.json()
    log_event(
        logger,
        logging.INFO,
        "mcp.recommendation.fetched",
        "getPreviousRecommendation completed",
        user_id=user_id,
        found=payload.get("body") is not None,
    )
    return payload


async def saveRecommendation(user_id: int, body: str) -> dict:
    """Replace the last recommendation for a user_id."""
    response = await _upstream_request(
        "portfolio-service",
        "PUT",
        f"{PORTFOLIO_SERVICE_URL}/recommendation",
        json={"user_id": user_id, "body": body},
    )
    payload = response.json()
    log_event(
        logger,
        logging.INFO,
        "mcp.recommendation.saved",
        "saveRecommendation completed",
        user_id=user_id,
        body_length=len(body),
    )
    return payload


def register_backend_tools(mcp: FastMCP) -> None:
    mcp.tool()(login)
    mcp.tool()(get_portfolio)
    mcp.tool()(getPreviousRecommendation)
    mcp.tool()(saveRecommendation)
