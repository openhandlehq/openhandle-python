from __future__ import annotations

from typing import Any


class OpenHandleError(Exception):
    """An error returned by the OpenHandle API or transport runtime.

    Branch on ``code``, never on ``message``.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        request_id: str | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id
        self.retryable = retryable
        self.retry_after = retry_after
        self.status = status
        self.details = details

    def __str__(self) -> str:
        if self.request_id:
            return f"{self.code}: {self.message} (request {self.request_id})"
        return f"{self.code}: {self.message}"


class OpenHandleReferenceError(ValueError):
    """A locally invalid resource reference, raised before any request."""


class ReferenceMismatchError(OpenHandleReferenceError):
    """A social URL for a different platform or resource than the selector."""

    def __init__(
        self,
        expected_platform: str,
        expected_resource: str,
        actual_platform: str,
        actual_resource: str,
    ) -> None:
        super().__init__(
            f"Expected a {expected_platform} {expected_resource} URL, "
            f"received a {actual_platform} {actual_resource} URL."
        )
        self.expected_platform = expected_platform
        self.expected_resource = expected_resource
        self.actual_platform = actual_platform
        self.actual_resource = actual_resource
