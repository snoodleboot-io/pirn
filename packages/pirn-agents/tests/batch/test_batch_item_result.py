"""Mirrored tests for the batch item result value — its outcome is a core ``Result``."""

from __future__ import annotations

import pytest
from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.batch.batch_item_result import BatchItemResult


def _record(message: str = "boom", exc_type: str = "RuntimeError") -> ExceptionRecord:
    return ExceptionRecord(
        run_id="<unbound>",
        knot_id="k9",
        exc_type=exc_type,
        message=message,
        traceback_text="Traceback (most recent call last):\n  RuntimeError: boom\n",
    )


def _ok() -> BatchItemResult:
    return BatchItemResult(index=2, key="k2", outcome=Ok(value={"n": 1}), attempts=1, latency=0.5)


def _failed(record: ExceptionRecord | None = None) -> BatchItemResult:
    return BatchItemResult(
        index=9,
        key="k9",
        outcome=Err(record=record if record is not None else _record()),
        attempts=3,
        latency=1.25,
    )


def _timeout() -> BatchItemResult:
    return BatchItemResult(
        index=7,
        key="k7",
        outcome=Err(record=_record("deadline exceeded", "KnotTimeoutError")),
    )


def _skipped() -> BatchItemResult:
    return BatchItemResult(index=3, key="k3", outcome=Skipped(reason="resumed"), attempts=0)


class TestBatchItemResultOutcome:
    def test_ok_outcome_succeeds_and_carries_output(self) -> None:
        result = _ok()
        assert result.succeeded
        assert result.output == {"n": 1}
        assert result.exception is None
        assert result.error is None
        assert not result.timed_out

    def test_err_outcome_carries_the_record(self) -> None:
        record = _record()
        result = _failed(record)
        assert not result.succeeded
        assert result.output is None
        assert result.exception == record
        assert result.error == "boom"
        assert not result.timed_out

    def test_timeout_is_an_err_whose_error_type_is_a_timeout(self) -> None:
        result = _timeout()
        assert isinstance(result.outcome, Err)
        assert result.timed_out
        assert result.error == "deadline exceeded"

    @pytest.mark.parametrize("exc_type", ["TimeoutError", "KnotTimeoutError"])
    def test_every_timeout_error_type_is_recognised(self, exc_type: str) -> None:
        result = BatchItemResult(index=0, key="k", outcome=Err(record=_record(exc_type=exc_type)))
        assert result.timed_out

    def test_skipped_outcome_is_neither_success_nor_failure(self) -> None:
        result = _skipped()
        assert isinstance(result.outcome, Skipped)
        assert not result.succeeded
        assert result.exception is None
        assert result.output is None

    def test_error_is_read_only(self) -> None:
        with pytest.raises(AttributeError):
            _failed().error = "clobbered"  # type: ignore[misc]


class TestBatchItemResultPayload:
    def test_payload_covers_all_fields(self) -> None:
        assert set(_ok().to_payload()) == {
            "index",
            "key",
            "outcome",
            "output",
            "error",
            "exception",
            "skip_reason",
            "attempts",
            "latency",
        }

    @pytest.mark.parametrize(
        ("result", "token"),
        [(_ok(), "ok"), (_failed(), "err"), (_skipped(), "skipped")],
    )
    def test_outcome_serialises_to_the_result_variant_token(
        self, result: BatchItemResult, token: str
    ) -> None:
        assert result.to_payload()["outcome"] == token

    def test_payload_carries_the_whole_record(self) -> None:
        payload = _failed().to_payload()
        assert payload["exception"]["exc_type"] == "RuntimeError"
        assert payload["exception"]["traceback_text"].startswith("Traceback")
        assert payload["error"] == "boom"

    def test_payload_carries_the_skip_reason(self) -> None:
        assert _skipped().to_payload()["skip_reason"] == "resumed"
        assert _ok().to_payload()["skip_reason"] is None

    def test_non_json_output_is_stringified(self) -> None:
        result = BatchItemResult(index=0, key="k", outcome=Ok(value=object()))
        assert isinstance(result.to_payload()["output"], str)

    def test_nested_json_output_is_preserved(self) -> None:
        result = BatchItemResult(index=0, key="k", outcome=Ok(value={"a": [1, {"b": 2}]}))
        assert result.to_payload()["output"] == {"a": [1, {"b": 2}]}

    def test_is_opaque_audit_dict(self) -> None:
        assert _ok()._pirn_audit_dict() == _ok().to_payload()


class TestBatchItemResultValidation:
    def test_rejects_negative_index(self) -> None:
        with pytest.raises(ValueError):
            BatchItemResult(index=-1, key="k", outcome=Ok(value=None))

    def test_rejects_empty_key(self) -> None:
        with pytest.raises(TypeError):
            BatchItemResult(index=0, key="", outcome=Ok(value=None))

    def test_rejects_an_outcome_that_is_not_a_result(self) -> None:
        with pytest.raises(TypeError):
            BatchItemResult(index=0, key="k", outcome="ok")  # type: ignore[arg-type]
