"""Tests for :class:`ToolCallBatch` and :class:`ToolCallBatchFrame` (PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_batch import ToolCallBatch
from pirn_agents.tools.tool_call_batch_frame import ToolCallBatchFrame


def _calls() -> tuple[ToolCall, ...]:
    return (
        ToolCall(tool_name="search", arguments={"input": "q"}, call_id="c0"),
        ToolCall(tool_name="calc", arguments={"input": "2+2"}, call_id="c1"),
    )


def test_is_a_payload_with_derived_frame() -> None:
    batch = ToolCallBatch(_calls())

    assert isinstance(batch, Payload)
    assert isinstance(batch.metadata, ToolCallBatchFrame)
    assert batch.metadata.count == 2
    assert batch.metadata.tool_names == ("search", "calc")


def test_data_is_the_ordered_tuple_of_calls() -> None:
    calls = _calls()

    assert ToolCallBatch(list(calls)).data == calls


def test_empty_batch() -> None:
    batch = ToolCallBatch(())

    assert batch.data == ()
    assert batch.metadata == ToolCallBatchFrame(count=0, tool_names=())


def test_audit_dict_carries_frame_and_calls() -> None:
    calls = _calls()

    audit = ToolCallBatch(calls)._pirn_audit_dict()

    assert audit["count"] == 2
    assert audit["tool_names"] == ["search", "calc"]
    assert audit["calls"] == [call._pirn_audit_dict() for call in calls]


def test_equality_is_structural() -> None:
    assert ToolCallBatch(_calls()) == ToolCallBatch(_calls())
    assert ToolCallBatch(_calls()) != ToolCallBatch(_calls()[:1])
    assert ToolCallBatch(_calls()) != _calls()
