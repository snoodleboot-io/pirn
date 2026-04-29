"""Unit tests for Ok/Err/Skipped."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pirn import Err, Ok, Skipped
from pirn.managers.exceptions import ExceptionRecord


def _record():
    return ExceptionRecord(
        run_id="r", knot_id="k", exc_type="ValueError",
        message="boom", traceback_text="tb",
    )


def test_ok_properties():
    o = Ok(value=42)
    assert o.is_ok and not o.is_err and not o.is_skipped
    assert o.unwrap() == 42


def test_err_properties():
    e = Err(record=_record())
    assert not e.is_ok and e.is_err and not e.is_skipped
    with pytest.raises(RuntimeError):
        e.unwrap()


def test_skipped_properties():
    s = Skipped(reason="my_reason")
    assert not s.is_ok and not s.is_err and s.is_skipped
    assert s.reason == "my_reason"
    with pytest.raises(RuntimeError):
        s.unwrap()


def test_skipped_default_reason():
    """Skipped without an explicit reason has the default 'skipped' marker."""
    s = Skipped()
    assert s.reason == "skipped"


def test_ok_is_frozen():
    o = Ok(value=1)
    with pytest.raises(ValidationError):
        o.value = 2  # type: ignore[misc]


def test_err_is_frozen():
    e = Err(record=_record())
    with pytest.raises(ValidationError):
        e.record = _record()  # type: ignore[misc]


def test_skipped_is_frozen():
    s = Skipped(reason="x")
    with pytest.raises(ValidationError):
        s.reason = "y"  # type: ignore[misc]


def test_skipped_carries_detail():
    s = Skipped(reason="branch_not_selected", detail={"branch_name": "tool"})
    assert s.detail == {"branch_name": "tool"}


def test_skipped_default_detail_empty():
    s = Skipped(reason="x")
    assert s.detail == {}


def test_isinstance_discrimination():
    """Downstream code uses isinstance to discriminate; verify correctness."""
    o: object = Ok(value=1)
    e: object = Err(record=_record())
    s: object = Skipped()
    assert isinstance(o, Ok) and not isinstance(o, (Err, Skipped))
    assert isinstance(e, Err) and not isinstance(e, (Ok, Skipped))
    assert isinstance(s, Skipped) and not isinstance(s, (Ok, Err))


def test_ok_preserves_value_identity():
    """Pydantic doesn't deep-copy our value — the same object is held."""
    payload = {"a": 1}
    o = Ok(value=payload)
    assert o.value is payload
