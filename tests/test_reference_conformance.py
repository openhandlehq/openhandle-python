from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openhandle import OpenHandleReferenceError, ReferenceMismatchError
from openhandle._references import resolve_reference

FIXTURE = json.loads((Path(__file__).parent.parent / "testdata" / "reference-conformance.json").read_text())


def test_fixture_version_is_pinned() -> None:
    assert FIXTURE["version"] == 1


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: str(case["name"]))
def test_shared_reference_conformance(case: dict[str, Any]) -> None:
    kind = case["input"]["kind"]
    value = case["input"]["value"]
    expected_error = case.get("error")
    if expected_error is None:
        assert resolve_reference(kind, value, case["platform"], case["resource"]) == case["identifier"]
        return
    with pytest.raises(OpenHandleReferenceError) as raised:
        resolve_reference(kind, value, case["platform"], case["resource"])
    actual_error = "reference_mismatch" if isinstance(raised.value, ReferenceMismatchError) else "invalid_reference"
    assert actual_error == expected_error
