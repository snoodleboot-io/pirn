"""Unit tests for :class:`ToolResult`."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus


class TestRoundtrip(unittest.TestCase):
    def test_construct_success(self) -> None:
        result = ToolResult(call_id="c1", result={"answer": 42}, error=None)
        assert result.call_id == "c1"
        assert result.result == {"answer": 42}
        assert result.error is None

    def test_construct_failure(self) -> None:
        result = ToolResult(call_id="c1", result=None, error="boom")
        assert result.error == "boom"
        assert result.result is None

    def test_audit_dict_includes_repr_of_result(self) -> None:
        result = ToolResult(call_id="c1", result={"x": 1}, error=None)
        d = result._pirn_audit_dict()
        assert d["call_id"] == "c1"
        assert d["error"] is None


class TestStatusFields(unittest.TestCase):
    def test_default_status_ok(self) -> None:
        result = ToolResult(call_id="c1", result=42)
        assert result.status is ToolStatus.OK
        assert result.latency is None
        assert result.tokens is None

    def test_error_promotes_status_to_error(self) -> None:
        result = ToolResult(call_id="c1", result=None, error="boom")
        assert result.status is ToolStatus.ERROR

    def test_explicit_status_preserved_over_error(self) -> None:
        result = ToolResult(
            call_id="c1",
            result=None,
            error="timed out",
            status=ToolStatus.TIMEOUT,
        )
        assert result.status is ToolStatus.TIMEOUT

    def test_explicit_nonok_status_without_error_is_untouched(self) -> None:
        result = ToolResult(call_id="c1", result=None, status=ToolStatus.TIMEOUT)
        assert result.status is ToolStatus.TIMEOUT

    def test_latency_and_tokens_round_trip(self) -> None:
        result = ToolResult(call_id="c1", result=1, latency=0.25, tokens=17)
        assert result.latency == 0.25
        assert result.tokens == 17

    def test_audit_dict_includes_new_fields(self) -> None:
        result = ToolResult(call_id="c1", result="x", error="e", latency=1.5, tokens=3)
        d = result._pirn_audit_dict()
        assert d == {
            "call_id": "c1",
            "result": repr("x"),
            "error": "e",
            # Emitted alongside ``error`` even when absent, mirroring
            # BatchItemResult.to_payload, so a reader sees one shape (PIR-794).
            "exception": None,
            "status": "error",
            "latency": 1.5,
            "tokens": 3,
        }

    def test_frozen(self) -> None:
        result = ToolResult(call_id="c1", result=1)
        with self.assertRaises(FrozenInstanceError):
            result.result = 2  # type: ignore[misc]

    def test_cache_stability_identical_fields_equal_audit(self) -> None:
        a = ToolResult(call_id="c1", result=1, latency=0.1, tokens=5)
        b = ToolResult(call_id="c1", result=1, latency=0.1, tokens=5)
        assert a._pirn_audit_dict() == b._pirn_audit_dict()
        assert a == b


class ExceptionRecordFieldTests(unittest.TestCase):
    """PIR-794 — the tool path keeps the exception, not just its message."""

    @staticmethod
    def _record() -> ExceptionRecord:
        try:
            raise ValueError("boom")
        except ValueError as exc:
            return ExceptionRecord.for_knot("search", exc)

    def test_error_is_derived_from_the_record_when_not_supplied(self) -> None:
        result = ToolResult(call_id="c1", result=None, exception=self._record())
        assert result.error == "ValueError: boom"
        assert result.status is ToolStatus.ERROR

    def test_explicit_error_is_preserved_alongside_the_record(self) -> None:
        # The timeout path reports a domain message while capturing the
        # underlying exception, so the two are allowed to differ deliberately.
        result = ToolResult(
            call_id="c1",
            result=None,
            error="tool 'search' timed out after 1.0s",
            status=ToolStatus.TIMEOUT,
            exception=self._record(),
        )
        assert result.error == "tool 'search' timed out after 1.0s"
        assert result.exception is not None
        assert result.exception.message == "boom"
        assert result.status is ToolStatus.TIMEOUT

    def test_record_carries_type_and_traceback(self) -> None:
        # The whole point: a caller can now see WHAT failed, not just a string.
        result = ToolResult(call_id="c1", result=None, exception=self._record())
        assert result.exception is not None
        assert result.exception.exc_type == "ValueError"
        assert "ValueError: boom" in result.exception.traceback_text

    def test_success_keeps_both_absent(self) -> None:
        result = ToolResult(call_id="c1", result="ok")
        assert result.exception is None
        assert result.error is None
        assert result.status is ToolStatus.OK

    def test_a_non_record_exception_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ToolResult(call_id="c1", result=None, exception="boom")  # type: ignore[arg-type]

    def test_audit_dict_carries_the_full_record(self) -> None:
        result = ToolResult(call_id="c1", result=None, exception=self._record())
        payload = result._pirn_audit_dict()["exception"]
        assert isinstance(payload, dict)
        assert payload["exc_type"] == "ValueError"
        assert payload["message"] == "boom"


class ToResultTests(unittest.TestCase):
    """PIR-856: the smallest behaviour-preserving bridge to Ok | Err | Skipped."""

    def test_ok_status_wraps_the_whole_result_in_ok(self) -> None:
        result = ToolResult(call_id="c1", result={"a": 1})
        wrapped = result.to_result()
        assert isinstance(wrapped, Ok)
        assert wrapped.value is result

    def test_error_with_a_captured_exception_uses_its_record(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError as exc:
            record = ExceptionRecord.for_knot("search", exc)
        result = ToolResult(call_id="c1", result=None, exception=record)
        wrapped = result.to_result()
        assert isinstance(wrapped, Err)
        assert wrapped.record is record

    def test_error_without_an_exception_synthesises_a_record_from_the_message(self) -> None:
        result = ToolResult(call_id="c1", result=None, error="tool 'x' not found")
        wrapped = result.to_result()
        assert isinstance(wrapped, Err)
        assert wrapped.record.message == "tool 'x' not found"

    def test_a_bare_status_with_no_message_still_synthesises_a_record(self) -> None:
        result = ToolResult(call_id="c1", result=None, status=ToolStatus.TIMEOUT)
        wrapped = result.to_result()
        assert isinstance(wrapped, Err)
        assert "timeout" in wrapped.record.message


class FromResultTests(unittest.TestCase):
    def test_ok_of_a_tool_result_round_trips_unchanged(self) -> None:
        original = ToolResult(call_id="c1", result=42, latency=0.1)
        rebuilt = ToolResult.from_result("c1", Ok(value=original))
        assert rebuilt is original

    def test_ok_of_a_plain_value_is_wrapped(self) -> None:
        rebuilt = ToolResult.from_result("c1", Ok(value=42))
        assert rebuilt.call_id == "c1"
        assert rebuilt.result == 42
        assert rebuilt.status is ToolStatus.OK

    def test_err_carries_its_record_through(self) -> None:
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            record = ExceptionRecord.for_knot("k", exc)
        rebuilt = ToolResult.from_result("c1", Err(record=record))
        assert rebuilt.status is ToolStatus.ERROR
        assert rebuilt.exception is record
        assert rebuilt.error == "RuntimeError: boom"

    def test_skipped_becomes_an_error_result_naming_the_reason(self) -> None:
        """ToolStatus has no "not run" member; a skip is reported as its own error."""
        rebuilt = ToolResult.from_result("c1", Skipped(reason="upstream not selected"))
        assert rebuilt.status is ToolStatus.ERROR
        assert rebuilt.error is not None
        assert "upstream not selected" in rebuilt.error

    def test_rejects_a_non_result(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be Ok, Err, or Skipped"):
            ToolResult.from_result("c1", "not a result")  # type: ignore[arg-type]

    def test_round_trip_through_to_result_and_back(self) -> None:
        original = ToolResult(call_id="c1", result="value", latency=0.2)
        assert ToolResult.from_result("c1", original.to_result()) is original
