from __future__ import annotations

from types import TracebackType

import httpx

from openhandle._async_resources import AsyncGeneratedClient
from openhandle._sync_resources import GeneratedClient
from openhandle._transport import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    AsyncTransport,
    SyncTransport,
    TransportConfig,
)


class OpenHandle(GeneratedClient):
    """A reusable synchronous OpenHandle client.

    The API key selects the Test or Live environment; there is no separate
    environment option. Never expose an API key in client-side code.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        config = TransportConfig(api_key, base_url, timeout, max_retries)
        super().__init__(SyncTransport(config, http_client))

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> OpenHandle:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AsyncOpenHandle(AsyncGeneratedClient):
    """A reusable asynchronous OpenHandle client.

    The API key selects the Test or Live environment; there is no separate
    environment option. Never expose an API key in client-side code.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        config = TransportConfig(api_key, base_url, timeout, max_retries)
        super().__init__(AsyncTransport(config, http_client))

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> AsyncOpenHandle:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
