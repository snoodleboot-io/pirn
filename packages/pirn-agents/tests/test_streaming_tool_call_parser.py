"""Chunked, early-emission, parallel, and malformed-tail tests for
:class:`StreamingToolCallParser`.

Written in the project's ``asyncio_mode = "auto"`` style: module-level
``async def test_...`` functions with plain ``assert`` statements. Each test
builds a tiny async generator yielding neutral delta mappings and drives the
parser directly, so the eager-emission and never-raise guarantees can be
asserted deterministically.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.streaming_tool_call_parser import StreamingToolCallParser


async def _stream(deltas: Sequence[Mapping[str, Any]]) -> AsyncIterator[Mapping[str, Any]]:
    """Yield ``deltas`` one at a time, cooperatively yielding control."""
    for delta in deltas:
        await asyncio.sleep(0)
        yield delta


async def test_single_call_split_across_fragments() -> None:
    deltas = [
        {"index": 0, "id": "call_1", "name": "search", "arguments": '{"que'},
        {"index": 0, "arguments": 'ry": "cats"'},
        {"index": 0, "arguments": ', "limit": 3}'},
        {"index": 0, "done": True, "arguments": ""},
    ]
    parser = StreamingToolCallParser()

    calls = await parser.parse_to_list(_stream(deltas))

    assert len(calls) == 1
    assert calls[0].tool_name == "search"
    assert calls[0].call_id == "call_1"
    assert calls[0].arguments == {"query": "cats", "limit": 3}
    assert calls[0].raw == {"index": 0}
    assert parser.dropped_partial == 0


async def test_call_emitted_before_stream_completes() -> None:
    # Index 0 finishes (done) early; index 1 fragments follow but the second
    # generator half blocks on an event, proving the index-0 ToolCall is
    # retrievable BEFORE the stream is exhausted.
    gate = asyncio.Event()

    async def gated_stream() -> AsyncIterator[Mapping[str, Any]]:
        yield {"index": 0, "id": "c0", "name": "a", "arguments": "{}", "done": True}
        yield {"index": 1, "id": "c1", "name": "b", "arguments": '{"x"'}
        await gate.wait()  # stream cannot complete until the test releases it
        yield {"index": 1, "arguments": ": 1}", "done": True}

    parser = StreamingToolCallParser()
    iterator = parser.parse(gated_stream())

    first = await anext(iterator)
    assert first.call_id == "c0"
    assert first.tool_name == "a"
    assert first.arguments == {}
    # The generator is still suspended at ``gate.wait`` — the stream is NOT
    # done, yet we already hold index 0's ToolCall.
    assert not gate.is_set()

    gate.set()
    second = await anext(iterator)
    assert second.call_id == "c1"
    assert second.arguments == {"x": 1}


async def test_parallel_interleaved_calls() -> None:
    deltas = [
        {"index": 0, "id": "c0", "name": "alpha", "arguments": '{"a"'},
        {"index": 1, "id": "c1", "name": "beta", "arguments": '{"b"'},
        {"index": 0, "arguments": ": 1}"},
        {"index": 1, "arguments": ": 2}"},
        {"index": 0, "done": True, "arguments": ""},
        {"index": 1, "done": True, "arguments": ""},
    ]
    parser = StreamingToolCallParser()

    calls = await parser.parse_to_list(_stream(deltas))

    assert len(calls) == 2
    by_id = {call.call_id: call for call in calls}
    assert by_id["c0"].tool_name == "alpha"
    assert by_id["c0"].arguments == {"a": 1}
    assert by_id["c1"].tool_name == "beta"
    assert by_id["c1"].arguments == {"b": 2}


async def test_malformed_tail_is_dropped_without_raising() -> None:
    deltas = [
        {"index": 0, "id": "c0", "name": "ok", "arguments": "{}", "done": True},
        {"index": 1, "id": "c1", "name": "broken", "arguments": '{"partial'},
    ]
    parser = StreamingToolCallParser()

    calls = await parser.parse_to_list(_stream(deltas))

    assert len(calls) == 1
    assert calls[0].call_id == "c0"
    assert parser.dropped_partial == 1


async def test_empty_arguments_with_done_yields_empty_dict() -> None:
    deltas = [
        {"index": 0, "id": "c0", "name": "noargs", "arguments": "", "done": True},
    ]
    parser = StreamingToolCallParser()

    calls = await parser.parse_to_list(_stream(deltas))

    assert len(calls) == 1
    assert calls[0].arguments == {}
    assert parser.dropped_partial == 0


async def test_sequential_fallback_flush_without_done() -> None:
    # No ``done`` ever arrives, but a new index beginning flushes the prior
    # index once its accumulated arguments are valid JSON.
    deltas = [
        {"index": 0, "id": "c0", "name": "first", "arguments": '{"n": 1}'},
        {"index": 1, "id": "c1", "name": "second", "arguments": '{"n": 2}'},
    ]
    parser = StreamingToolCallParser()

    calls = await parser.parse_to_list(_stream(deltas))

    assert [call.call_id for call in calls] == ["c0", "c1"]
    assert calls[0].arguments == {"n": 1}
    assert calls[1].arguments == {"n": 2}
    assert parser.dropped_partial == 0
