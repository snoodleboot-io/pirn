"""Unit tests for Ok/Err/Skipped."""

from __future__ import annotations
import unittest

from pydantic import ValidationError

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord


def _record():
    return ExceptionRecord(
        run_id="r",
        knot_id="k",
        exc_type="ValueError",
        message="boom",
        traceback_text="tb",
    )



class _StandaloneTests(unittest.TestCase):
    def test_ok_properties(self):
        o = Ok(value=42)
        assert o.is_ok and not o.is_err and not o.is_skipped
        assert o.unwrap() == 42
    
    
    def test_err_properties(self):
        e = Err(record=_record())
        assert not e.is_ok and e.is_err and not e.is_skipped
        with self.assertRaises(RuntimeError):
            e.unwrap()
    
    
    def test_skipped_properties(self):
        s = Skipped(reason="my_reason")
        assert not s.is_ok and not s.is_err and s.is_skipped
        assert s.reason == "my_reason"
        with self.assertRaises(RuntimeError):
            s.unwrap()
    
    
    def test_skipped_default_reason(self):
        """Skipped without an explicit reason has the default 'skipped' marker."""
        s = Skipped()
        assert s.reason == "skipped"
    
    
    def test_ok_is_frozen(self):
        o = Ok(value=1)
        with self.assertRaises(ValidationError):
            o.value = 2  # type: ignore[misc]
    
    
    def test_err_is_frozen(self):
        e = Err(record=_record())
        with self.assertRaises(ValidationError):
            e.record = _record()  # type: ignore[misc]
    
    
    def test_skipped_is_frozen(self):
        s = Skipped(reason="x")
        with self.assertRaises(ValidationError):
            s.reason = "y"  # type: ignore[misc]
    
    
    def test_skipped_carries_detail(self):
        s = Skipped(reason="branch_not_selected", detail={"branch_name": "tool"})
        assert s.detail == {"branch_name": "tool"}
    
    
    def test_skipped_default_detail_empty(self):
        s = Skipped(reason="x")
        assert s.detail == {}
    
    
    def test_isinstance_discrimination(self):
        """Downstream code uses isinstance to discriminate; verify correctness."""
        o: object = Ok(value=1)
        e: object = Err(record=_record())
        s: object = Skipped()
        assert isinstance(o, Ok) and not isinstance(o, (Err, Skipped))
        assert isinstance(e, Err) and not isinstance(e, (Ok, Skipped))
        assert isinstance(s, Skipped) and not isinstance(s, (Ok, Err))
    
    
    def test_ok_preserves_value_identity(self):
        """Pydantic doesn't deep-copy our value — the same object is held."""
        payload = {"a": 1}
        o = Ok(value=payload)
        assert o.value is payload
