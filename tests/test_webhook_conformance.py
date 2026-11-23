from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from openhandle import WebhookVerificationError, verify_webhook

FIXTURE = json.loads((Path(__file__).parent.parent / "testdata" / "webhook-conformance.json").read_text())


def verify_case(case: dict[str, Any], body: bytes | str) -> object:
    return verify_webhook(
        body,
        case["headers"],
        FIXTURE["secret"],
        tolerance_seconds=case.get("toleranceSeconds", FIXTURE["defaultToleranceSeconds"]),
        now=datetime.fromtimestamp(case["now"], tz=timezone.utc),
    )


def test_fixture_version_is_pinned() -> None:
    assert FIXTURE["version"] == 1


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: str(case["name"]))
def test_shared_webhook_conformance(case: dict[str, Any]) -> None:
    body = case["body"].encode("utf-8")
    expected_error = case.get("error")
    if expected_error is None:
        assert verify_case(case, body) == case["event"]
        return
    with pytest.raises(WebhookVerificationError) as raised:
        verify_case(case, body)
    assert raised.value.code == expected_error


def test_string_body_is_signed_as_utf8_bytes() -> None:
    case = next(case for case in FIXTURE["cases"] if case["name"] == "non-ASCII body is verified as UTF-8 bytes")
    assert verify_case(case, case["body"]) == case["event"]


def test_tolerance_compares_whole_seconds() -> None:
    case = next(case for case in FIXTURE["cases"] if case["name"] == "timestamp exactly at the default tolerance")
    late = datetime.fromtimestamp(case["now"] + 0.4, tz=timezone.utc)
    event = verify_webhook(case["body"], case["headers"], FIXTURE["secret"], now=late)
    assert event["id"] == case["event"]["id"]
