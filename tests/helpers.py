from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

RESPONSE_HEADERS = {
    "Content-Type": "application/json",
    "OpenHandle-Billing-Disposition": "test",
    "OpenHandle-Cost": "0.000",
    "OpenHandle-Environment": "test",
    "X-Request-ID": "req_test",
}


def profile_response() -> httpx.Response:
    return envelope_response(
        {
            "platform": "instagram",
            "resource": "profile",
            "captured_at": "2026-08-26T12:00:00Z",
            "source": "live",
            "data": {"id": "25025320", "handle": "openai"},
        }
    )


def page_response(cursor: str | None, items: list[dict[str, Any]] | None = None) -> httpx.Response:
    return envelope_response(
        {
            "platform": "instagram",
            "resource": "comment",
            "captured_at": "2026-08-26T12:00:00Z",
            "source": "live",
            "data": items or [],
            "meta": {"cursors": {"next": cursor}},
        }
    )


def envelope_response(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, content=json.dumps(body), headers=RESPONSE_HEADERS)


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def mock_async_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
