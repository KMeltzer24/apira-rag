import asyncio
import unittest
from unittest.mock import patch

import httpx

from apira_logging import reset_request_id, set_request_id
from backend_tools import getPreviousRecommendation, login, saveRecommendation


class _FakeAsyncClient:
    request_headers = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def request(self, method, url, *, headers, **kwargs):
        type(self).request_headers = headers
        type(self).last_method = method
        type(self).last_url = url
        type(self).last_kwargs = kwargs
        if "recommendation" in str(url) and method == "GET":
            payload = {"user_id": 7, "body": "Hold AAPL"}
        elif "recommendation" in str(url) and method == "PUT":
            payload = {"user_id": 7, "body": (kwargs.get("json") or {}).get("body")}
        else:
            payload = {"user_id": 7}
        return httpx.Response(
            200,
            json=payload,
            request=httpx.Request(method, url),
        )


class UpstreamCorrelationTests(unittest.TestCase):
    def test_active_request_id_is_propagated(self):
        request_id = "123e4567-e89b-12d3-a456-426614174000"
        token = set_request_id(request_id)
        try:
            with patch("backend_tools.httpx.AsyncClient", _FakeAsyncClient):
                result = asyncio.run(login("private-user", "private-password"))
        finally:
            reset_request_id(token)

        self.assertEqual(result, {"user_id": 7})
        self.assertEqual(
            _FakeAsyncClient.request_headers["X-Request-ID"], request_id
        )

    def test_get_previous_recommendation_hits_portfolio_service(self) -> None:
        with patch("backend_tools.httpx.AsyncClient", _FakeAsyncClient):
            result = asyncio.run(getPreviousRecommendation(7))
        self.assertEqual(result["body"], "Hold AAPL")
        self.assertEqual(_FakeAsyncClient.last_method, "GET")
        self.assertIn("/recommendation", str(_FakeAsyncClient.last_url))

    def test_save_recommendation_puts_body(self) -> None:
        with patch("backend_tools.httpx.AsyncClient", _FakeAsyncClient):
            result = asyncio.run(saveRecommendation(7, "Trim TSLA"))
        self.assertEqual(result["body"], "Trim TSLA")
        self.assertEqual(_FakeAsyncClient.last_method, "PUT")
        self.assertEqual(
            _FakeAsyncClient.last_kwargs.get("json"),
            {"user_id": 7, "body": "Trim TSLA"},
        )


if __name__ == "__main__":
    unittest.main()
