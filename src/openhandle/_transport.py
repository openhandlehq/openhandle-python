from __future__ import annotations

import asyncio
import email.utils
import random
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any, TypeVar
from urllib.parse import quote

import httpx

from openhandle._errors import OpenHandleError
from openhandle._response import AsyncPage, Billing, Page, Response

ItemT = TypeVar("ItemT")

DEFAULT_BASE_URL = "https://api.openhandle.dev"
DEFAULT_MAX_RETRIES = 2
DEFAULT_TIMEOUT = 30.0
MAX_RESPONSE_BYTES = 32 << 20


def sdk_version() -> str:
    try:
        return version("openhandle")
    except PackageNotFoundError:
        return "0.0.0"


class TransportConfig:
    def __init__(self, api_key: str, base_url: str | None, timeout: float, max_retries: int) -> None:
        api_key = api_key.strip() if isinstance(api_key, str) else ""
        if not api_key:
            raise ValueError("OpenHandle requires a non-empty api_key.")
        if timeout <= 0:
            raise ValueError("timeout must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative.")
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be an absolute HTTP or HTTPS URL.")
        self.timeout = timeout
        self.max_retries = max_retries

    def headers(self, has_body: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-OpenHandle-Client": f"openhandle-python/{sdk_version()}",
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers


def bind_path(api_path: str, bindings: dict[str, str]) -> str:
    def replace(segment: str) -> str:
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            value = bindings.get(name)
            if not value:
                raise TypeError(f"Missing bound SDK reference {name} for {api_path}.")
            return quote(value, safe="")
        return segment

    return "/".join(replace(segment) for segment in api_path.split("/"))


def encode_params(params: dict[str, Any]) -> dict[str, str]:
    encoded: dict[str, str] = {}
    for name, value in params.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            encoded[name] = "true" if value else "false"
            continue
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            encoded[name] = value.isoformat()
            continue
        encoded[name] = str(value)
    return encoded


def billing_from_headers(headers: httpx.Headers) -> Billing:
    return Billing(
        cost=headers.get("OpenHandle-Cost"),
        dataset_version=headers.get("OpenHandle-Dataset-Version"),
        disposition=headers.get("OpenHandle-Billing-Disposition"),
        environment=headers.get("OpenHandle-Environment"),
        list_price=headers.get("OpenHandle-List-Price"),
    )


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        target = email.utils.parsedate_to_datetime(value)
    except ValueError:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())


def retry_delay(error: OpenHandleError, attempt: int) -> float:
    if error.retry_after is not None and error.retry_after > 0:
        return error.retry_after
    base = min(4.0, 0.25 * (2.0 ** min(attempt, 4)))
    return base * (0.75 + random.random() * 0.5)


def transport_error() -> OpenHandleError:
    return OpenHandleError(code="TRANSPORT_ERROR", message="OpenHandle request failed.", retryable=True)


def decode_body(response: httpx.Response) -> dict[str, Any]:
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise OpenHandleError(
            code="INVALID_RESPONSE",
            message="OpenHandle response exceeded the maximum supported size.",
            request_id=response.headers.get("X-Request-ID"),
            status=response.status_code,
        )
    if not response.content:
        return {}
    try:
        body = response.json()
    except ValueError as cause:
        raise OpenHandleError(
            code="INVALID_RESPONSE",
            message="OpenHandle returned invalid JSON.",
            request_id=response.headers.get("X-Request-ID"),
            status=response.status_code,
        ) from cause
    return body if isinstance(body, dict) else {}


def api_error(response: httpx.Response, body: dict[str, Any]) -> OpenHandleError:
    error_value = body.get("error")
    error: dict[str, Any] = error_value if isinstance(error_value, dict) else {}
    code = error.get("code")
    message = error.get("message")
    request_id = error.get("request_id")
    retryable = error.get("retryable")
    details = error.get("details")
    return OpenHandleError(
        code=code if isinstance(code, str) and code else f"HTTP_{response.status_code}",
        message=message
        if isinstance(message, str) and message
        else f"OpenHandle request failed with status {response.status_code}.",
        request_id=request_id if isinstance(request_id, str) and request_id else response.headers.get("X-Request-ID"),
        retryable=retryable
        if isinstance(retryable, bool)
        else response.status_code == 429 or response.status_code >= 500,
        retry_after=parse_retry_after(response.headers.get("Retry-After")),
        status=response.status_code,
        details=details if isinstance(details, dict) else None,
    )


def interpret(response: httpx.Response) -> tuple[dict[str, Any], str, Billing]:
    body = decode_body(response)
    if response.status_code < 200 or response.status_code >= 300:
        raise api_error(response, body)
    request_id = response.headers.get("X-Request-ID", "")
    return body, request_id, billing_from_headers(response.headers)


class SyncTransport:
    def __init__(self, config: TransportConfig, http_client: httpx.Client | None) -> None:
        self._config = config
        self._client = http_client or httpx.Client()
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def request(
        self,
        method: str,
        api_path: str,
        bindings: dict[str, str],
        params: dict[str, Any],
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> tuple[dict[str, Any], str, Billing]:
        path = bind_path(api_path, bindings)
        query = encode_params(params)
        retries = self._config.max_retries if max_retries is None else max_retries
        if retries < 0:
            raise ValueError("max_retries must not be negative.")
        attempt = 0
        while True:
            try:
                return self._attempt(method, path, query, json_body, timeout)
            except OpenHandleError as error:
                if not error.retryable or attempt >= retries:
                    raise
                time.sleep(retry_delay(error, attempt))
                attempt += 1

    def _attempt(
        self,
        method: str,
        path: str,
        query: dict[str, str],
        json_body: dict[str, Any] | None,
        timeout: float | None,
    ) -> tuple[dict[str, Any], str, Billing]:
        try:
            response = self._client.request(
                method.upper(),
                f"{self._config.base_url}{path}",
                params=query,
                json=json_body,
                headers=self._config.headers(json_body is not None),
                timeout=timeout if timeout is not None else self._config.timeout,
            )
        except httpx.HTTPError as cause:
            raise transport_error() from cause
        return interpret(response)

    def response(self, result: tuple[dict[str, Any], str, Billing]) -> Response[Any]:
        body, request_id, billing = result
        return Response(body, request_id, billing)

    def page(
        self,
        result: tuple[dict[str, Any], str, Billing],
        method: str,
        api_path: str,
        bindings: dict[str, str],
        params: dict[str, Any],
        timeout: float | None,
        max_retries: int | None,
    ) -> Page[Any]:
        body, request_id, billing = result

        def fetch_next(cursor: str) -> Page[Any]:
            next_params = {**params, "cursor": cursor}
            next_result = self.request(
                method, api_path, bindings, next_params, timeout=timeout, max_retries=max_retries
            )
            return self.page(next_result, method, api_path, bindings, next_params, timeout, max_retries)

        return Page(body, request_id, billing, fetch_next)


class AsyncTransport:
    def __init__(self, config: TransportConfig, http_client: httpx.AsyncClient | None) -> None:
        self._config = config
        self._client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        api_path: str,
        bindings: dict[str, str],
        params: dict[str, Any],
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> tuple[dict[str, Any], str, Billing]:
        path = bind_path(api_path, bindings)
        query = encode_params(params)
        retries = self._config.max_retries if max_retries is None else max_retries
        if retries < 0:
            raise ValueError("max_retries must not be negative.")
        attempt = 0
        while True:
            try:
                return await self._attempt(method, path, query, json_body, timeout)
            except OpenHandleError as error:
                if not error.retryable or attempt >= retries:
                    raise
                await asyncio.sleep(retry_delay(error, attempt))
                attempt += 1

    async def _attempt(
        self,
        method: str,
        path: str,
        query: dict[str, str],
        json_body: dict[str, Any] | None,
        timeout: float | None,
    ) -> tuple[dict[str, Any], str, Billing]:
        try:
            response = await self._client.request(
                method.upper(),
                f"{self._config.base_url}{path}",
                params=query,
                json=json_body,
                headers=self._config.headers(json_body is not None),
                timeout=timeout if timeout is not None else self._config.timeout,
            )
        except httpx.HTTPError as cause:
            raise transport_error() from cause
        return interpret(response)

    def response(self, result: tuple[dict[str, Any], str, Billing]) -> Response[Any]:
        body, request_id, billing = result
        return Response(body, request_id, billing)

    def page(
        self,
        result: tuple[dict[str, Any], str, Billing],
        method: str,
        api_path: str,
        bindings: dict[str, str],
        params: dict[str, Any],
        timeout: float | None,
        max_retries: int | None,
    ) -> AsyncPage[Any]:
        body, request_id, billing = result

        async def fetch_next(cursor: str) -> AsyncPage[Any]:
            next_params = {**params, "cursor": cursor}
            next_result = await self.request(
                method, api_path, bindings, next_params, timeout=timeout, max_retries=max_retries
            )
            return self.page(next_result, method, api_path, bindings, next_params, timeout, max_retries)

        return AsyncPage(body, request_id, billing, fetch_next)
