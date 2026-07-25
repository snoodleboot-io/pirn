"""Isolation, concurrency, timeout, retry, and cancellation tests for
:class:`ParallelToolExecutor`.

Written in the project's ``asyncio_mode = "auto"`` style: module-level
``async def test_...`` functions with plain ``assert`` statements. A local
:class:`StubTool` provides configurable latency, transient-failure, and
cancellation-tracking behaviour so the concurrency semantics can be asserted
deterministically.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus


class InFlightCounter:
    """Track live and peak concurrency across cooperating tasks."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    def enter(self) -> None:
        self.current += 1
        self.peak = max(self.peak, self.current)

    def leave(self) -> None:
        self.current -= 1


class StubTool(Tool):
    """Configurable tool double recording invocations and cancellations."""

    def __init__(
        self,
        *,
        name: str,
        latency: float = 0.0,
        result: Any = "ok",
        fail_times: int = 0,
        counter: InFlightCounter | None = None,
    ) -> None:
        self._name = name
        self._latency = latency
        self._result = result
        self._fail_times = fail_times
        self._counter = counter
        self.calls = 0
        self.cancelled = 0

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
        self.calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError(f"{self._name} transient failure")
        counter = self._counter
        if counter is not None:
            counter.enter()
        try:
            if self._latency:
                await asyncio.sleep(self._latency)
            return self._result
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        finally:
            if counter is not None:
                counter.leave()


def _make_executor(**ctor: Any) -> ParallelToolExecutor:
    """Build an executor inside a throwaway tapestry context."""
    with Tapestry():
        return ParallelToolExecutor(
            tool_calls=[],
            toolset=Toolset(),
            _config=KnotConfig(id="pte", validate_io=False),
            **ctor,
        )


async def test_concurrency_cap_respected() -> None:
    counter = InFlightCounter()
    tools = [StubTool(name=f"t{i}", latency=0.05, counter=counter) for i in range(4)]
    toolset = Toolset(tools)
    calls = [ToolCall(tool_name=f"t{i}", arguments={}, call_id=f"c{i}") for i in range(4)]
    executor = _make_executor()

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=2, timeout=None, retries=0
    )

    assert counter.peak == 2
    assert all(r.status is ToolStatus.OK for r in results)


async def test_failure_isolation() -> None:
    good = StubTool(name="good", result="value")
    bad = StubTool(name="bad", fail_times=1)  # no retries -> permanent failure
    toolset = Toolset([good, bad])
    calls = [
        ToolCall(tool_name="good", arguments={}, call_id="c1"),
        ToolCall(tool_name="bad", arguments={}, call_id="c2"),
    ]
    executor = _make_executor()

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    by_id = {r.call_id: r for r in results}
    assert by_id["c1"].status is ToolStatus.OK
    assert by_id["c1"].result == "value"
    assert by_id["c2"].status is ToolStatus.ERROR
    assert by_id["c2"].error is not None and "transient failure" in by_id["c2"].error


async def test_timeout_isolated_from_siblings() -> None:
    slow = StubTool(name="slow", latency=0.5)
    fast = StubTool(name="fast", result="quick")
    toolset = Toolset([slow, fast])
    calls = [
        ToolCall(tool_name="slow", arguments={}, call_id="c1"),
        ToolCall(tool_name="fast", arguments={}, call_id="c2"),
    ]
    executor = _make_executor()

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=0.05, retries=0
    )

    by_id = {r.call_id: r for r in results}
    assert by_id["c1"].status is ToolStatus.TIMEOUT
    assert by_id["c1"].error is not None and "timed out" in by_id["c1"].error
    assert by_id["c1"].latency is not None
    assert by_id["c2"].status is ToolStatus.OK
    assert by_id["c2"].result == "quick"


async def test_retry_then_success() -> None:
    # Fails twice, succeeds on the third attempt; retries=2 grants exactly that.
    flaky = StubTool(name="flaky", fail_times=2, result="recovered")
    toolset = Toolset([flaky])
    calls = [ToolCall(tool_name="flaky", arguments={}, call_id="c1")]
    executor = _make_executor(retry_policy=RetryPolicy(base_delay=0.0))

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=2
    )

    assert flaky.calls == 3
    assert results[0].status is ToolStatus.OK
    assert results[0].result == "recovered"


async def test_retry_exhausted_returns_error() -> None:
    flaky = StubTool(name="flaky", fail_times=5)
    toolset = Toolset([flaky])
    calls = [ToolCall(tool_name="flaky", arguments={}, call_id="c1")]
    executor = _make_executor(retry_policy=RetryPolicy(base_delay=0.0))

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=1
    )

    assert flaky.calls == 2  # initial attempt + 1 retry
    assert results[0].status is ToolStatus.ERROR


async def test_retry_delay_comes_from_the_composed_retry_policy() -> None:
    # The inter-attempt delay is RetryPolicy.backoff_delay, not a hand-rolled
    # formula. Capture the delays with an injected sleep + deterministic rng and
    # match them against the policy computed independently.
    slept: list[float] = []

    async def _record(delay: float) -> None:
        slept.append(delay)

    policy = RetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=1.0, jitter=True)
    flaky = StubTool(name="flaky", fail_times=2, result="ok")
    toolset = Toolset([flaky])
    calls = [ToolCall(tool_name="flaky", arguments={}, call_id="c1")]
    executor = _make_executor(retry_policy=policy, rng=lambda: 0.5, sleep=_record)

    await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=2
    )

    assert slept == [
        policy.backoff_delay(0, rng=lambda: 0.5),
        policy.backoff_delay(1, rng=lambda: 0.5),
    ]


async def test_unknown_tool_yields_error_and_batch_completes() -> None:
    good = StubTool(name="good", result="value")
    toolset = Toolset([good])
    calls = [
        ToolCall(tool_name="missing", arguments={}, call_id="c1"),
        ToolCall(tool_name="good", arguments={}, call_id="c2"),
    ]
    executor = _make_executor()

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    by_id = {r.call_id: r for r in results}
    assert by_id["c1"].status is ToolStatus.ERROR
    assert by_id["c1"].error is not None and "missing" in by_id["c1"].error
    assert by_id["c2"].status is ToolStatus.OK


async def test_results_returned_in_input_order() -> None:
    # Later calls finish first (descending latency) yet order must follow input.
    tools = [StubTool(name=f"t{i}", latency=(4 - i) * 0.02, result=i) for i in range(4)]
    toolset = Toolset(tools)
    calls = [ToolCall(tool_name=f"t{i}", arguments={}, call_id=f"c{i}") for i in range(4)]
    executor = _make_executor()

    results = await executor.process(
        tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
    )

    assert tuple(r.call_id for r in results) == ("c0", "c1", "c2", "c3")
    assert tuple(r.result for r in results) == (0, 1, 2, 3)


async def test_rejects_non_tool_call() -> None:
    executor = _make_executor()
    with pytest.raises(TypeError):
        await executor.process(
            tool_calls=["not-a-call"],  # type: ignore[list-item]
            toolset=Toolset(),
            max_concurrency=8,
            timeout=None,
            retries=0,
        )


async def test_rejects_non_toolset() -> None:
    executor = _make_executor()
    with pytest.raises(TypeError):
        await executor.process(
            tool_calls=[],
            toolset=["not-a-toolset"],  # type: ignore[arg-type]
            max_concurrency=8,
            timeout=None,
            retries=0,
        )


async def test_cancellation_propagates_and_cancels_inflight() -> None:
    slow = StubTool(name="slow", latency=5.0)
    toolset = Toolset([slow])
    calls = [ToolCall(tool_name="slow", arguments={}, call_id="c1")]
    executor = _make_executor()

    task = asyncio.ensure_future(
        executor.process(
            tool_calls=calls, toolset=toolset, max_concurrency=8, timeout=None, retries=0
        )
    )
    await asyncio.sleep(0.05)  # let the invocation start and block on its sleep
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert slow.cancelled == 1


async def test_runs_through_tapestry_end_to_end() -> None:
    from pirn.core.run_request import RunRequest

    good = StubTool(name="good", result="value")
    toolset = Toolset([good])
    calls = [ToolCall(tool_name="good", arguments={}, call_id="c1")]

    with Tapestry() as tapestry:
        ParallelToolExecutor(
            tool_calls=calls,
            toolset=toolset,
            max_concurrency=4,
            _config=KnotConfig(id="pte"),
        )
    run = await tapestry.run(RunRequest())

    assert run.succeeded
    results = run.outputs["pte"]
    assert results[0].status is ToolStatus.OK
    assert results[0].result == "value"
