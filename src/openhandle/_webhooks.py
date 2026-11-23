from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import cast

from openhandle._errors import WebhookVerificationError
from openhandle.models import WebhookEvent

SIGNATURE_HEADER = "x-openhandle-signature"
TIMESTAMP_HEADER = "x-openhandle-timestamp"
UNIX_SECONDS = re.compile(r"[0-9]+")


def verify_webhook(
    raw_body: bytes | str,
    headers: Mapping[str, str],
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: datetime | None = None,
) -> WebhookEvent:
    """Verify a pushed webhook and return the typed event.

    Pass the raw request body exactly as received. Never parse and re-serialize
    it first, because the signature covers the original bytes.
    """
    body = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
    lowered = {name.lower(): value for name, value in headers.items()}

    signature = lowered.get(SIGNATURE_HEADER)
    if not signature:
        raise WebhookVerificationError("missing_signature", "The X-Openhandle-Signature header is missing.")

    timestamp = lowered.get(TIMESTAMP_HEADER)
    if not timestamp:
        raise WebhookVerificationError("missing_timestamp", "The X-Openhandle-Timestamp header is missing.")

    if not UNIX_SECONDS.fullmatch(timestamp):
        raise WebhookVerificationError("invalid_timestamp", "The X-Openhandle-Timestamp header is not Unix seconds.")

    current = int((now or datetime.now(timezone.utc)).timestamp())
    if abs(current - int(timestamp)) > tolerance_seconds:
        raise WebhookVerificationError(
            "timestamp_out_of_tolerance",
            f"The webhook timestamp is more than {tolerance_seconds} seconds from the current time.",
        )

    digest = hmac.new(secret.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={digest}".encode(), signature.encode("utf-8")):
        raise WebhookVerificationError("invalid_signature", "The webhook signature does not match.")

    try:
        event = json.loads(body)
    except ValueError as error:
        raise WebhookVerificationError("invalid_payload", "The webhook body is not valid JSON.") from error
    if not isinstance(event, dict):
        raise WebhookVerificationError("invalid_payload", "The webhook body is not a JSON object.")
    fields = ("id", "type", "environment", "createdAt")
    if not all(isinstance(event.get(field), str) for field in fields) or not isinstance(event.get("data"), dict):
        raise WebhookVerificationError("invalid_payload", "The webhook body is not a webhook event.")
    return cast(WebhookEvent, event)
