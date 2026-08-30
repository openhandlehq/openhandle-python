from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar, cast

DataT = TypeVar("DataT")
ItemT = TypeVar("ItemT")


@dataclass(frozen=True)
class Billing:
    """Authoritative accounting metadata returned in response headers.

    Monetary values remain decimal strings to avoid precision loss.
    """

    cost: str | None
    dataset_version: str | None
    disposition: str | None
    environment: str | None
    list_price: str | None


class ResponseMetadata:
    """Envelope metadata shared by singular responses and pages."""

    def __init__(self, body: dict[str, Any], request_id: str, billing: Billing) -> None:
        self._body = body
        self.request_id = request_id
        self.billing = billing

    @property
    def raw(self) -> dict[str, Any]:
        """The complete decoded response body, exactly as returned by the API."""
        return self._body

    @property
    def platform(self) -> str:
        return str(self._body.get("platform", ""))

    @property
    def resource(self) -> str:
        return str(self._body.get("resource", ""))

    @property
    def source(self) -> str:
        return str(self._body.get("source", ""))

    @property
    def captured_at(self) -> datetime | None:
        value = self._body.get("captured_at")
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


class Response(ResponseMetadata, Generic[DataT]):
    """A typed singular response preserving the public envelope."""

    @property
    def data(self) -> DataT:
        return cast(DataT, self._body.get("data"))


class Page(ResponseMetadata, Generic[ItemT]):
    """One typed page returned by a list or search operation."""

    def __init__(
        self,
        body: dict[str, Any],
        request_id: str,
        billing: Billing,
        fetch_next: Callable[[str], Page[ItemT]],
    ) -> None:
        super().__init__(body, request_id, billing)
        self._fetch_next = fetch_next

    @property
    def data(self) -> list[ItemT]:
        value = self._body.get("data")
        return value if isinstance(value, list) else []

    @property
    def next_cursor(self) -> str | None:
        """The opaque cursor for the next page, or None after the final page."""
        return page_cursor(self._body)

    @property
    def has_next_page(self) -> bool:
        return self.next_cursor is not None

    def next(self) -> Page[ItemT] | None:
        """Fetch the next page, or return None without a request at the end."""
        cursor = self.next_cursor
        if cursor is None:
            return None
        return self._fetch_next(cursor)


class AsyncPage(ResponseMetadata, Generic[ItemT]):
    """One typed page returned by an asynchronous list or search operation."""

    def __init__(
        self,
        body: dict[str, Any],
        request_id: str,
        billing: Billing,
        fetch_next: Callable[[str], Awaitable[AsyncPage[ItemT]]],
    ) -> None:
        super().__init__(body, request_id, billing)
        self._fetch_next = fetch_next

    @property
    def data(self) -> list[ItemT]:
        value = self._body.get("data")
        return value if isinstance(value, list) else []

    @property
    def next_cursor(self) -> str | None:
        """The opaque cursor for the next page, or None after the final page."""
        return page_cursor(self._body)

    @property
    def has_next_page(self) -> bool:
        return self.next_cursor is not None

    async def next(self) -> AsyncPage[ItemT] | None:
        """Fetch the next page, or return None without a request at the end."""
        cursor = self.next_cursor
        if cursor is None:
            return None
        return await self._fetch_next(cursor)


def page_cursor(body: dict[str, Any]) -> str | None:
    meta = body.get("meta")
    if not isinstance(meta, dict):
        return None
    cursors = meta.get("cursors")
    if not isinstance(cursors, dict):
        return None
    cursor = cursors.get("next")
    return cursor if isinstance(cursor, str) and cursor else None
