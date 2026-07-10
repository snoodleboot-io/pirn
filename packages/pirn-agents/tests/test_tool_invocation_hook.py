"""Observability-hook tests for :class:`ParallelToolExecutor`.

Written in the project's ``asyncio_mode = "auto"`` style: module-level
``async def test_...`` functions with plain ``assert`` statements. A local
:class:`RecordingHook` captures every ``on_start``/``on_finish`` event so the
firing order, correlation ids, argument digest, terminal status, and latency
can be asserted deterministically; a configurable :class:`StubTool` drives the
success, error, and timeout paths.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tool import Tool
from pirn_agents.tool_invocation_hook import ToolInvocationHook
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


@dataclass(frozen=True)
class StartEvent:
    """Captured ``on_start`` invocation."""

    tool_name: str
    args_digest: str
    call_id: str


@dataclass(frozen=True)
class FinishEvent:
    """Captured ``on_finish`` invocation."""

    tool_name: str
    call_id: str
    status: ToolStatus
    latency: float


class RecordingHook(ToolInvocationHook):
    """Hook double appending every event to a single ordered log."""

    def __init__(self) -> None:
        self.events: list[StartEvent | FinishEvent] = []

    def on_start(self, *, tool_name: str, args_digest: str, call_id: str) -> None:
        self.events.append(
            StartEvent(tool_name=tool_name, args_digest=args_digest, call_id=call_id)
        )

    def on_finish(
        self, *, tool_name: str, call_id: str, status: ToolStatus, latency: float
    ) -> None:
        self.events.append(
            FinishEvent(tool_name=tool_name, call_id=call_id, status=status, latency=latency)
        )

    def starts(self) -> list[StartEvent]:
        return [e for e in self.events if isinstance(e, StartEvent)]

    def finishes(self) -> list[FinishEvent]:
        return [e for e in self.events if isinstance(e, FinishEvent)]


class RaisingHook(ToolInvocationHook):
    """Hook whose callbacks always raise, to prove exceptions are swallowed."""

    def on_start(self, *, tool_name: str, args_digest: str, call_id: str) -> None:
        raise RuntimeError("on_start boom")

    def on_finish(
        self, *, tool_name: str, call_id: str, status: ToolStatus, latency: float
    ) -> None:
        raise RuntimeError("on_finish boom")


class StubTool(Tool):
    """Configurable tool double: return a value, raise, or hang forever."""

    def __init__(
        self,
        *,
        name: str,
        result: Any = "ok",
        raises: bool = False,
        latency: float = 0.0,
    ) -> None:
        self._name = name
        self._result = result
        self._raises = raises
        self._latency = latency

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"stub {self._name}"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        if self._latency:
            await asyncio.sleep(self._latency)
        if self._raises:
            raise RuntimeError(f"{self._name} boom")
        return self._result


def _make_executor(**ctor: Any) -> ParallelToolExecutor:
    """Build an executor inside a throwaway tapestry context."""
    with Tapestry():
        return ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="pte", validate_io=False),
            **ctor,
        )


async def test_on_start_fires_before_on_finish_with_ids() -> None:
    hook = RecordingHook()
    toolset = Toolset([StubTool(name="t", result="v")])
    calls = [ToolCall(tool_name="t", arguments={"a": 1}, call_id="c1")]
    executor = _make_executor(hook=hook)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    assert len(hook.events) == 2
    assert isinstance(hook.events[0], StartEvent)
    assert isinstance(hook.events[1], FinishEvent)
    assert hook.events[0].tool_name == "t"
    assert hook.events[0].call_id == "c1"
    assert hook.events[1].tool_name == "t"
    assert hook.events[1].call_id == "c1"


async def test_args_digest_non_empty_and_stable_for_identical_args() -> None:
    hook = RecordingHook()
    toolset = Toolset([StubTool(name="t")])
    args = {"query": "hello", "limit": 5}
    calls = [
        ToolCall(tool_name="t", arguments=dict(args), call_id="c1"),
        ToolCall(tool_name="t", arguments=dict(args), call_id="c2"),
    ]
    executor = _make_executor(hook=hook)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    digests = {s.call_id: s.args_digest for s in hook.starts()}
    assert all(d for d in digests.values())  # non-empty
    assert digests["c1"] == digests["c2"]  # stable for identical args


async def test_args_digest_differs_for_different_args() -> None:
    hook = RecordingHook()
    toolset = Toolset([StubTool(name="t")])
    calls = [
        ToolCall(tool_name="t", arguments={"q": "a"}, call_id="c1"),
        ToolCall(tool_name="t", arguments={"q": "b"}, call_id="c2"),
    ]
    executor = _make_executor(hook=hook)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    digests = {s.call_id: s.args_digest for s in hook.starts()}
    assert digests["c1"] != digests["c2"]


async def test_on_finish_status_ok_for_success() -> None:
    hook = RecordingHook()
    toolset = Toolset([StubTool(name="t", result="v")])
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]
    executor = _make_executor(hook=hook)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    finish = hook.finishes()[0]
    assert finish.status is ToolStatus.OK
    assert isinstance(finish.latency, float)


async def test_on_finish_status_error_for_raising_tool() -> None:
    hook = RecordingHook()
    toolset = Toolset([StubTool(name="t", raises=True)])
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]
    executor = _make_executor(hook=hook)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    finish = hook.finishes()[0]
    assert finish.status is ToolStatus.ERROR
    assert isinstance(finish.latency, float)


async def test_on_finish_status_timeout_for_timing_out_tool() -> None:
    hook = RecordingHook()
    toolset = Toolset([StubTool(name="t", latency=0.5)])
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]
    executor = _make_executor(hook=hook)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=0.05, retries=0
    )

    finish = hook.finishes()[0]
    assert finish.status is ToolStatus.TIMEOUT
    assert isinstance(finish.latency, float)


async def test_on_finish_fires_for_unknown_tool() -> None:
    hook = RecordingHook()
    toolset = Toolset([StubTool(name="present")])
    calls = [ToolCall(tool_name="missing", arguments={}, call_id="c1")]
    executor = _make_executor(hook=hook)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    assert len(hook.starts()) == 1
    finish = hook.finishes()[0]
    assert finish.call_id == "c1"
    assert finish.status is ToolStatus.ERROR


async def test_noop_default_hook_is_inert_and_matches_no_hook() -> None:
    toolset = Toolset([StubTool(name="t", result="v")])
    calls = [ToolCall(tool_name="t", arguments={"a": 1}, call_id="c1")]

    without_hook = await _make_executor().process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )
    with_base_hook = await _make_executor(hook=ToolInvocationHook()).process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    assert _comparable(without_hook) == _comparable(with_base_hook)
    assert without_hook[0].status is ToolStatus.OK
    assert with_base_hook[0].status is ToolStatus.OK


async def test_raising_hook_does_not_break_execution() -> None:
    toolset = Toolset([StubTool(name="t", result="v")])
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]
    executor = _make_executor(hook=RaisingHook())

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    assert len(results) == 1
    assert results[0].status is ToolStatus.OK
    assert results[0].result == "v"


def _comparable(results: tuple[ToolResult, ...]) -> list[tuple[str, Any, ToolStatus, str | None]]:
    """Reduce results to their latency-independent identity for comparison."""
    return [(r.call_id, r.result, r.status, r.error) for r in results]
