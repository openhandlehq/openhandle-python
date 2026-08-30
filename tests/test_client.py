from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
import pytest

from openhandle import OpenHandle, OpenHandleError, OpenHandleReferenceError, ReferenceMismatchError
from openhandle._operations import OPERATIONS
from tests.helpers import mock_client, page_response, profile_response


def client(handler: Callable[[httpx.Request], httpx.Response], max_retries: int = 0) -> OpenHandle:
    return OpenHandle(
        "oh_test_sdk",
        base_url="https://api.openhandle.test",
        http_client=mock_client(handler),
        max_retries=max_retries,
    )


def test_generates_every_openapi_operation_exactly_once() -> None:
    assert len(OPERATIONS) == 126
    assert len({operation["path"] for operation in OPERATIONS}) == len(OPERATIONS)


def test_treats_profile_strings_as_usernames_and_ids_as_explicit_strings() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return profile_response()

    openhandle = client(handler)
    openhandle.instagram.profile("12356").get(freshness="24h")
    openhandle.instagram.profile(id="12356").get()

    assert requests[0].url.raw_path.split(b"?")[0] == b"/v1/instagram/profiles/%4012356"
    assert requests[0].url.params["freshness"] == "24h"
    assert requests[1].url.path == "/v1/instagram/profiles/12356"


def test_parses_explicit_social_urls_locally_and_rejects_resource_mismatches() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return profile_response()

    openhandle = client(handler)
    openhandle.instagram.profile(url="https://www.instagram.com/openai/?hl=en").get()
    assert requests[0].url.raw_path.split(b"?")[0] == b"/v1/instagram/profiles/%40openai"

    with pytest.raises(ReferenceMismatchError):
        openhandle.instagram.profile(url="https://www.instagram.com/p/Db04otPRpRH/")


def test_rejects_numeric_and_ambiguous_references_before_making_a_request() -> None:
    openhandle = client(lambda request: profile_response())

    with pytest.raises(OpenHandleReferenceError):
        openhandle.instagram.profile(12356)  # type: ignore[arg-type]
    with pytest.raises(OpenHandleReferenceError):
        openhandle.instagram.profile(username="openai", id="25025320")


def test_binds_nested_resources_and_follows_opaque_pagination_cursors() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return page_response(None if "cursor" in request.url.params else "next-page")

    openhandle = client(handler)
    first = openhandle.instagram.post("Db04otPRpRH").comment("18120112390529134").replies.list()
    assert first.has_next_page is True
    assert first.next_cursor == "next-page"
    assert first.captured_at == datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    assert first.request_id == "req_test"
    assert first.billing.cost == "0.000"
    assert first.billing.environment == "test"

    second = first.next()
    assert second is not None
    assert second.has_next_page is False
    assert second.next() is None
    assert requests[0].url.path == "/v1/instagram/posts/Db04otPRpRH/comments/18120112390529134/replies"
    assert requests[1].url.params["cursor"] == "next-page"


def test_items_iterates_lazily_across_pages() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "cursor" in request.url.params:
            return page_response(None, [{"id": "3"}])
        return page_response("next-page", [{"id": "1"}, {"id": "2"}])

    openhandle = client(handler)
    items = openhandle.instagram.profile("openai").posts.items()
    assert requests == []
    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert len(requests) == 2


def test_raises_typed_api_errors_without_retrying_non_retryable_failures() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            403,
            content=json.dumps(
                {
                    "error": {
                        "code": "PROFILE_PRIVATE",
                        "message": "This profile is private.",
                        "request_id": "req_private",
                        "retryable": False,
                    }
                }
            ),
            headers={"Content-Type": "application/json"},
        )

    openhandle = client(handler, max_retries=2)
    with pytest.raises(OpenHandleError) as raised:
        openhandle.instagram.profile("private").get()
    assert raised.value.code == "PROFILE_PRIVATE"
    assert raised.value.request_id == "req_private"
    assert raised.value.retryable is False
    assert raised.value.status == 403
    assert len(requests) == 1


def test_sends_url_fetches_as_typed_json_requests() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return profile_response()

    openhandle = client(handler)
    openhandle.fetch("https://www.instagram.com/openai/", freshness="7d")
    assert bodies == [{"url": "https://www.instagram.com/openai/", "freshness": "7d"}]


def test_retries_explicitly_retryable_failures_and_honors_retry_after() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                503,
                content=json.dumps(
                    {
                        "error": {
                            "code": "UPSTREAM_DEGRADED",
                            "message": "Try again.",
                            "request_id": "req_retry",
                            "retryable": True,
                        }
                    }
                ),
                headers={"Content-Type": "application/json", "Retry-After": "0"},
            )
        return profile_response()

    openhandle = client(handler, max_retries=1)
    response = openhandle.instagram.profile("openai").get()
    assert response.data["handle"] == "openai"
    assert len(requests) == 2


def test_requires_a_non_empty_api_key() -> None:
    with pytest.raises(ValueError):
        OpenHandle("   ")


def test_sends_authorization_and_client_headers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return profile_response()

    openhandle = client(handler)
    openhandle.instagram.profile("openai").get()
    assert requests[0].headers["Authorization"] == "Bearer oh_test_sdk"
    assert requests[0].headers["X-OpenHandle-Client"].startswith("openhandle-python/")
