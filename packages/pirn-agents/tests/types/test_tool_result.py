"""Unit tests for :class:`ToolResult`."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

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
        assert result.error == "boom"
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
