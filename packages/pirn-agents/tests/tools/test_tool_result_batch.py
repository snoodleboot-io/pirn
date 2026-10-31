"""Tests for :class:`ToolResultBatch` and :class:`ToolResultBatchFrame` (PIR-874)."""

from __future__ import annotations

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.payload import Payload
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_result_batch import ToolResultBatch
from pirn_agents.tools.tool_result_batch_frame import ToolResultBatchFrame


def _results() -> tuple[ToolResult, ...]:
    return (
        ToolResult(call_id="c0", outcome=Ok(value="hit")),
        ToolResult(call_id="c1", outcome=Skipped(reason="approval_denied")),
        ToolResult(call_id="c2", outcome=Ok(value=4)),
    )


def _batch(results: tuple[ToolResult, ...] | None = None) -> ToolResultBatch:
    return ToolResultBatch(
        _results() if results is None else results, max_concurrency=4, timeout=1.5
    )


def test_is_a_payload_with_derived_frame() -> None:
    batch = _batch()

    assert isinstance(batch, Payload)
    assert batch.metadata == ToolResultBatchFrame(
        attempted=3, succeeded=2, failed=1, max_concurrency=4, timeout=1.5
    )


def test_failed_counts_every_non_ok_outcome() -> None:
    err = Err(record=ExceptionRecord.for_knot("k", RuntimeError("boom")))
    batch = ToolResultBatch(
        (ToolResult(call_id="c0", outcome=err), *_results()),
        max_concurrency=1,
        timeout=None,
    )

    assert batch.metadata.attempted == 4
    assert batch.metadata.succeeded == 2
    assert batch.metadata.failed == 2
    assert batch.metadata.timeout is None


def test_data_is_the_ordered_tuple_of_results() -> None:
    results = _results()

    assert _batch(results).data == results


def test_audit_dict_carries_frame_and_results() -> None:
    results = _results()

    audit = _batch(results)._pirn_audit_dict()

    assert audit["attempted"] == 3
    assert audit["succeeded"] == 2
    assert audit["failed"] == 1
    assert audit["max_concurrency"] == 4
    assert audit["timeout"] == 1.5
    assert audit["results"] == [result._pirn_audit_dict() for result in results]


def test_equality_is_structural() -> None:
    assert _batch() == _batch()
    assert _batch() != _batch(_results()[:1])
    assert _batch() != _results()
