"""Deprecated-hook tests for :class:`ParallelToolExecutor` (ADR WS1, one cycle).

``ToolInvocationHook`` is deprecated: a tool call is a knot, so its outcome is
its lineage row and the run's emitters.  For the cycle the executor still
fires a hook it is handed — ``on_start`` once per call before the graph runs,
``on_finish`` once per terminal outcome from the combine — so an existing
subscriber keeps its events.  These tests pin that contract, and that
subclassing the hook warns.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import pytest
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation_hook import ToolInvocationHook
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus
from pirn_agents.tools.toolset import Toolset


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


with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)

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


class Stub(Tool):
    """Configurable tool knot: return a value, raise, or sleep past a timeout."""

    def __init__(
        self,
        *,
        result: Knot | Any = "ok",
        raises: Knot | bool = False,
        latency: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(result=result, raises=raises, latency=latency, _config=_config, **kwargs)

    async def process(
        self, result: Any = "ok", raises: bool = False, latency: float = 0.0, **_: Any
    ) -> Any:
        import asyncio

        if latency:
            await asyncio.sleep(latency)
        if raises:
            raise RuntimeError("boom")
        return result


def _stub(name: str, **bound: Any):
    return Stub.bind(**bound).named(name)


async def _run(calls: list[ToolCall], toolset: Toolset, **ctor: Any) -> tuple[ToolResult, ...]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with Tapestry() as t:
            ParallelToolExecutor(
                tool_calls=calls, toolset=toolset, _config=KnotConfig(id="pte"), **ctor
            )
        run = await t.run(RunRequest())
    assert run.succeeded, run.exceptions
    return run.outputs["pte"]


def test_subclassing_the_hook_warns() -> None:
    with pytest.warns(DeprecationWarning, match="ToolInvocationHook"):

        class _Later(ToolInvocationHook):
            pass


async def test_passing_a_hook_warns() -> None:
    with Tapestry() as t:
        ParallelToolExecutor(
            tool_calls=[ToolCall(tool_name="t", arguments={}, call_id="c1")],
            toolset=Toolset([_stub("t")]),
            hook=RecordingHook(),
            _config=KnotConfig(id="pte"),
        )
    # The executor's ``process()`` is where the deprecated input is read, so
    # the warning is raised when the engine runs it, not at construction.
    with pytest.warns(DeprecationWarning, match="hook"):
        run = await t.run(RunRequest())
    assert run.succeeded, run.exceptions


async def test_on_start_fires_before_on_finish_with_ids() -> None:
    hook = RecordingHook()
    calls = [ToolCall(tool_name="t", arguments={"a": 1}, call_id="c1")]

    await _run(calls, Toolset([_stub("t", result="v")]), hook=hook)

    assert len(hook.events) == 2
    assert isinstance(hook.events[0], StartEvent)
    assert isinstance(hook.events[1], FinishEvent)
    assert hook.events[0].tool_name == "t"
    assert hook.events[0].call_id == "c1"
    assert hook.events[1].tool_name == "t"
    assert hook.events[1].call_id == "c1"


async def test_args_digest_non_empty_and_stable_for_identical_args() -> None:
    hook = RecordingHook()
    args = {"query": "hello", "limit": 5}
    calls = [
        ToolCall(tool_name="t", arguments=dict(args), call_id="c1"),
        ToolCall(tool_name="t", arguments=dict(args), call_id="c2"),
    ]

    await _run(calls, Toolset([_stub("t")]), hook=hook)

    digests = {s.call_id: s.args_digest for s in hook.starts()}
    assert all(d for d in digests.values())  # non-empty
    assert digests["c1"] == digests["c2"]  # stable for identical args


async def test_args_digest_differs_for_different_args() -> None:
    hook = RecordingHook()
    calls = [
        ToolCall(tool_name="t", arguments={"q": "a"}, call_id="c1"),
        ToolCall(tool_name="t", arguments={"q": "b"}, call_id="c2"),
    ]

    await _run(calls, Toolset([_stub("t")]), hook=hook)

    digests = {s.call_id: s.args_digest for s in hook.starts()}
    assert digests["c1"] != digests["c2"]


async def test_on_finish_status_ok_for_success() -> None:
    hook = RecordingHook()
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]

    await _run(calls, Toolset([_stub("t", result="v")]), hook=hook)

    finish = hook.finishes()[0]
    assert finish.status is ToolStatus.OK
    assert isinstance(finish.latency, float)


async def test_on_finish_status_error_for_raising_tool() -> None:
    hook = RecordingHook()
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]

    await _run(calls, Toolset([_stub("t", raises=True)]), hook=hook)

    finish = hook.finishes()[0]
    assert finish.status is ToolStatus.ERROR
    assert isinstance(finish.latency, float)


async def test_on_finish_status_timeout_for_timing_out_tool() -> None:
    hook = RecordingHook()
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]

    await _run(calls, Toolset([_stub("t", latency=0.5)]), hook=hook, timeout=0.05)

    finish = hook.finishes()[0]
    assert finish.status is ToolStatus.TIMEOUT
    assert isinstance(finish.latency, float)


async def test_on_finish_fires_for_unknown_tool() -> None:
    hook = RecordingHook()
    calls = [ToolCall(tool_name="missing", arguments={}, call_id="c1")]

    await _run(calls, Toolset([_stub("present")]), hook=hook)

    assert len(hook.starts()) == 1
    finish = hook.finishes()[0]
    assert finish.call_id == "c1"
    assert finish.status is ToolStatus.ERROR


async def test_noop_default_hook_is_inert_and_matches_no_hook() -> None:
    toolset = Toolset([_stub("t", result="v")])
    calls = [ToolCall(tool_name="t", arguments={"latency": 0.0}, call_id="c1")]

    without_hook = await _run(calls, toolset)
    with_base_hook = await _run(calls, toolset, hook=ToolInvocationHook())

    assert [(r.call_id, r.status, r.result) for r in without_hook] == [
        (r.call_id, r.status, r.result) for r in with_base_hook
    ]
    assert without_hook[0].status is ToolStatus.OK


async def test_raising_hook_does_not_break_execution() -> None:
    calls = [ToolCall(tool_name="t", arguments={}, call_id="c1")]

    results = await _run(calls, Toolset([_stub("t", result="v")]), hook=RaisingHook())

    assert len(results) == 1
    assert results[0].status is ToolStatus.OK
    assert results[0].result == "v"


async def test_opaque_arguments_do_not_break_tool_execution() -> None:
    """An argument with no content rendering still gets a digest sentinel, never an error."""
    hook = RecordingHook()
    calls = [ToolCall(tool_name="t", arguments={"blob": object()}, call_id="c1")]

    results = await _run(calls, Toolset([_stub("t", result="v")]), hook=hook)

    assert hook.starts()[0].args_digest
    assert results[0].call_id == "c1"
