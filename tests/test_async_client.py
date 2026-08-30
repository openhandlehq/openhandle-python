from __future__ import annotations

from collections.abc import Callable

import httpx

from openhandle import AsyncOpenHandle
from tests.helpers import mock_async_client, page_response, profile_response


def client(handler: Callable[[httpx.Request], httpx.Response]) -> AsyncOpenHandle:
    return AsyncOpenHandle(
        "oh_test_sdk",
        base_url="https://api.openhandle.test",
        http_client=mock_async_client(handler),
        max_retries=0,
    )


async def test_performs_async_requests_through_the_same_resource_graph() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return profile_response()

    async with client(handler) as openhandle:
        response = await openhandle.instagram.profile("openai").get(freshness="24h")

    assert response.data["handle"] == "openai"
    assert requests[0].url.raw_path.split(b"?")[0] == b"/v1/instagram/profiles/%40openai"
    assert requests[0].url.params["freshness"] == "24h"


async def test_follows_pagination_cursors_asynchronously() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return page_response(None if "cursor" in request.url.params else "next-page")

    async with client(handler) as openhandle:
        first = await openhandle.instagram.post("Db04otPRpRH").comments.list()
        assert first.has_next_page is True
        second = await first.next()

    assert second is not None
    assert second.has_next_page is False
    assert await second.next() is None
    assert requests[1].url.params["cursor"] == "next-page"


async def test_items_iterates_lazily_across_pages_asynchronously() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "cursor" in request.url.params:
            return page_response(None, [{"id": "3"}])
        return page_response("next-page", [{"id": "1"}, {"id": "2"}])

    async with client(handler) as openhandle:
        items = openhandle.instagram.profile("openai").posts.items()
        assert requests == []
        collected = [item["id"] async for item in items]

    assert collected == ["1", "2", "3"]
    assert len(requests) == 2
