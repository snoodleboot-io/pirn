"""Unit tests for :class:`ToolResult` — the model-facing view of a call's ``Result``."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.tools.tool_result import ToolResult


def _record(exc: BaseException) -> ExceptionRecord:
    try:
        raise exc
    except BaseException as caught:
        return ExceptionRecord.for_knot("k", caught)


class TestOutcomeViews(unittest.TestCase):
    def test_ok_outcome(self) -> None:
        result = ToolResult(call_id="c1", outcome=Ok(value={"answer": 42}))
        assert result.call_id == "c1"
        assert result.succeeded
        assert result.result == {"answer": 42}
        assert result.error is None
        assert result.exception is None
        assert result.status == "ok"

    def test_err_outcome_renders_type_and_message(self) -> None:
        record = _record(RuntimeError("boom"))
        result = ToolResult(call_id="c1", outcome=Err(record=record))
        assert not result.succeeded
        assert result.result is None
        assert result.exception is record
        assert result.error == "RuntimeError: boom"
        assert result.status == "error"

    def test_timeout_status_is_derived_from_the_error_type(self) -> None:
        for exc_type in ("KnotTimeoutError", "TimeoutError"):
            record = ExceptionRecord(
                run_id="<unbound>",
                knot_id="k",
                exc_type=exc_type,
                message="late",
                traceback_text="",
            )
            result = ToolResult(call_id="c1", outcome=Err(record=record))
            assert result.status == "timeout", exc_type

    def test_skipped_outcome_renders_the_reason(self) -> None:
        result = ToolResult(call_id="c1", outcome=Skipped(reason="approval denied"))
        assert not result.succeeded
        assert result.status == "skipped"
        assert result.error == "call skipped: approval denied"
        assert result.exception is None

    def test_latency_and_tokens_are_annotations(self) -> None:
        result = ToolResult(call_id="c1", outcome=Ok(value=1), latency=0.25, tokens=17)
        assert result.latency == 0.25
        assert result.tokens == 17

    def test_with_latency_keeps_the_outcome(self) -> None:
        outcome = Ok(value=1)
        result = ToolResult(call_id="c1", outcome=outcome, tokens=3).with_latency(1.5)
        assert result.outcome is outcome
        assert result.latency == 1.5
        assert result.tokens == 3

    def test_is_frozen(self) -> None:
        result = ToolResult(call_id="c1", outcome=Ok(value=1))
        with self.assertRaises(FrozenInstanceError):
            result.call_id = "c2"  # type: ignore[misc]

    def test_equality_is_structural(self) -> None:
        a = ToolResult(call_id="c1", outcome=Ok(value=1), latency=0.1, tokens=5)
        b = ToolResult(call_id="c1", outcome=Ok(value=1), latency=0.1, tokens=5)
        assert a == b

    def test_rejects_an_outcome_that_is_not_a_result(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be Ok, Err, or Skipped"):
            ToolResult(call_id="c1", outcome="boom")  # type: ignore[arg-type]

    def test_audit_dict_carries_the_record_and_status(self) -> None:
        audit = ToolResult(
            call_id="c1", outcome=Err(record=_record(ValueError("bad")))
        )._pirn_audit_dict()
        assert audit["status"] == "error"
        assert audit["exception"]["exc_type"] == "ValueError"
        assert audit["error"] == "ValueError: bad"


class FromResultTests(unittest.TestCase):
    def test_ok_of_a_tool_result_round_trips_unchanged(self) -> None:
        original = ToolResult(call_id="c1", outcome=Ok(value=42), latency=0.1)
        rebuilt = ToolResult.from_result("c1", Ok(value=original))
        assert rebuilt is original

    def test_ok_of_a_plain_value_is_wrapped(self) -> None:
        rebuilt = ToolResult.from_result("c1", Ok(value=42))
        assert rebuilt.call_id == "c1"
        assert rebuilt.result == 42
        assert rebuilt.status == "ok"

    def test_err_carries_its_record_through(self) -> None:
        record = _record(RuntimeError("boom"))
        rebuilt = ToolResult.from_result("c1", Err(record=record))
        assert rebuilt.status == "error"
        assert rebuilt.exception is record
        assert rebuilt.error == "RuntimeError: boom"

    def test_skipped_stays_skipped_naming_the_reason(self) -> None:
        """PIR-865: a skip is reported as skipped, not fabricated into an error."""
        rebuilt = ToolResult.from_result("c1", Skipped(reason="upstream not selected"))
        assert isinstance(rebuilt.outcome, Skipped)
        assert rebuilt.status == "skipped"
        assert rebuilt.error == "call skipped: upstream not selected"

    def test_gated_skipped_names_approval_denied_over_the_raw_reason(self) -> None:
        """A gated call's Skipped can only be its approval gate closing (PIR-865)."""
        rebuilt = ToolResult.from_result(
            "c1", Skipped(reason="parent_failed_or_skipped"), gated=True
        )
        assert rebuilt.status == "skipped"
        assert rebuilt.error == "call skipped: approval denied"

    def test_ungated_skipped_keeps_the_engines_own_reason(self) -> None:
        rebuilt = ToolResult.from_result(
            "c1", Skipped(reason="parent_failed_or_skipped"), gated=False
        )
        assert rebuilt.error == "call skipped: parent_failed_or_skipped"

    def test_rejects_a_non_result(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be Ok, Err, or Skipped"):
            ToolResult.from_result("c1", "not a result")  # type: ignore[arg-type]

    def test_outcome_round_trips_through_from_result(self) -> None:
        original = ToolResult(call_id="c1", outcome=Ok(value="value"), latency=0.2)
        rebuilt = ToolResult.from_result("c1", original.outcome)
        assert rebuilt.outcome == original.outcome
        assert rebuilt.result == "value"
