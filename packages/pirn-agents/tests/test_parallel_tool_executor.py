"""Isolation, concurrency, timeout, retry, and cancellation tests for
:class:`ParallelToolExecutor` — a fan-out of tool knots the engine runs (ADR WS1).

Written in the project's ``asyncio_mode = "auto"`` style: module-level
``async def test_...`` functions with plain ``assert`` statements. A local
:class:`Probe` tool knot provides configurable latency, transient-failure and
in-flight tracking so the engine's concurrency semantics can be asserted
deterministically.  Every test runs the executor in a real tapestry: the
executor is a ``NestedRunKnot`` whose ``process()`` runs the fan-out as an
inner run under the resolved concurrency cap.
"""

from __future__ import annotations

import asyncio
import time
import warnings
from typing import Any, ClassVar

import pytest
from pirn.core.concurrency.unused_concurrency_group_warning import (
    UnusedConcurrencyGroupWarning,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.toolset import Toolset


class InFlightCounter:
    """Track live and peak concurrency across cooperating calls."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    def enter(self) -> None:
        self.current += 1
        self.peak = max(self.peak, self.current)

    def leave(self) -> None:
        self.current -= 1


class Probe(Tool):
    """Configurable tool knot: latency, transient failures, in-flight tracking."""

    #: name -> number of calls / cancellations observed, shared per test.
    calls: ClassVar[dict[str, int]] = {}
    cancelled: ClassVar[dict[str, int]] = {}
    failures_left: ClassVar[dict[str, int]] = {}
    counters: ClassVar[dict[str, InFlightCounter]] = {}

    def __init__(
        self,
        *,
        name: Knot | str,
        latency: Knot | float = 0.0,
        result: Knot | Any = "ok",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, latency=latency, result=result, _config=_config, **kwargs)

    async def process(self, name: str, latency: float = 0.0, result: Any = "ok", **_: Any) -> Any:
        Probe.calls[name] = Probe.calls.get(name, 0) + 1
        if Probe.failures_left.get(name, 0) > 0:
            Probe.failures_left[name] -= 1
            raise RuntimeError(f"{name} transient failure")
        counter = Probe.counters.get(name)
        if counter is not None:
            counter.enter()
        try:
            if latency:
                await asyncio.sleep(latency)
            return result
        except asyncio.CancelledError:
            Probe.cancelled[name] = Probe.cancelled.get(name, 0) + 1
            raise
        finally:
            if counter is not None:
                counter.leave()


@pytest.fixture(autouse=True)
def _reset_probe() -> None:
    Probe.calls.clear()
    Probe.cancelled.clear()
    Probe.failures_left.clear()
    Probe.counters.clear()


def _named(names: list[str], **bound: Any) -> Toolset:
    """One probe capability per name: ``name`` bound (hidden) and declared as the tool name."""
    return Toolset([Probe.bind(name=name, **bound).named(name) for name in names])


async def _run(
    calls: list[ToolCall], toolset: Toolset, **ctor: Any
) -> tuple[tuple[ToolResult, ...], RunResult, Tapestry]:
    with Tapestry() as t:
        ParallelToolExecutor(
            tool_calls=calls, toolset=toolset, _config=KnotConfig(id="pte"), **ctor
        )
    run = await t.run(RunRequest())
    assert run.succeeded, run.exceptions
    return run.outputs["pte"], run, t


async def _inner_rows(t: Tapestry, run: RunResult) -> dict[str, Any]:
    children = await t.history.children_of(run.run_id)
    return {row.knot_id: row for child in children for row in child.lineage}


async def test_concurrency_cap_respected() -> None:
    counter = InFlightCounter()
    names = [f"t{i}" for i in range(4)]
    for name in names:
        Probe.counters[name] = counter
    toolset = _named(names, latency=0.05)
    calls = [ToolCall(tool_name=n, arguments={}, call_id=f"c{i}") for i, n in enumerate(names)]

    results, _, _ = await _run(calls, toolset, max_concurrency=2)

    assert counter.peak == 2
    assert all(r.status == "ok" for r in results)


async def test_concurrency_cap_wired_from_an_upstream_knot_is_applied() -> None:
    # ``max_concurrency`` produced by a parent knot is only known at run time;
    # it still caps the batch (it used to be read from literal config only, so
    # a wired cap silently ran the batch unbounded).
    counter = InFlightCounter()
    names = [f"t{i}" for i in range(4)]
    for name in names:
        Probe.counters[name] = counter
    toolset = _named(names, latency=0.05)
    calls = [ToolCall(tool_name=n, arguments={}, call_id=f"c{i}") for i, n in enumerate(names)]

    with Tapestry() as t:
        cap = Parameter("cap", int, default=1, _config=KnotConfig(id="cap"))
        ParallelToolExecutor(
            tool_calls=calls, toolset=toolset, max_concurrency=cap, _config=KnotConfig(id="pte")
        )
    run = await t.run(RunRequest())

    assert run.succeeded, run.exceptions
    assert counter.peak == 1
    assert all(r.status == "ok" for r in run.outputs["pte"])


async def test_failure_isolation() -> None:
    toolset = Toolset(
        [Probe.bind(name="good", result="value").named("good"), Probe.bind(name="bad").named("bad")]
    )
    Probe.failures_left["bad"] = 1
    calls = [
        ToolCall(tool_name="good", arguments={}, call_id="c1"),
        ToolCall(tool_name="bad", arguments={}, call_id="c2"),
    ]

    results, _, _ = await _run(calls, toolset)

    by_id = {r.call_id: r for r in results}
    assert by_id["c1"].status == "ok"
    assert by_id["c1"].result == "value"
    assert by_id["c2"].status == "error"
    assert by_id["c2"].error is not None and "transient failure" in by_id["c2"].error


async def test_timeout_isolated_from_siblings() -> None:
    toolset = _named(["slow", "fast"])
    calls = [
        ToolCall(tool_name="slow", arguments={"latency": 0.5}, call_id="c1"),
        ToolCall(tool_name="fast", arguments={"result": "quick"}, call_id="c2"),
    ]

    results, _, _ = await _run(calls, toolset, timeout=0.05)

    by_id = {r.call_id: r for r in results}
    assert by_id["c1"].status == "timeout"
    assert by_id["c1"].error is not None and "did not finish within" in by_id["c1"].error
    assert by_id["c2"].status == "ok"
    assert by_id["c2"].result == "quick"


async def test_retry_then_success() -> None:
    # Fails twice, succeeds on the third attempt; three attempts grant exactly that.
    toolset = _named(["flaky"], result="recovered")
    Probe.failures_left["flaky"] = 2
    calls = [ToolCall(tool_name="flaky", arguments={}, call_id="c1")]

    results, run, t = await _run(
        calls, toolset, retry=KnotRetryPolicy(max_attempts=3, base_delay=0.0, jitter=False)
    )

    assert Probe.calls["flaky"] == 3
    assert results[0].status == "ok"
    assert results[0].result == "recovered"
    rows = await _inner_rows(t, run)
    assert rows["c1"].extra.get("attempts") == 3


async def test_retry_backoff_sleeps_between_attempts_on_the_engine() -> None:
    # Core GovernedDispatch owns the inter-attempt backoff: 0.04 s then 0.08 s
    # before the third attempt, with no sleep inside the executor itself.
    toolset = _named(["flaky"], result="recovered")
    Probe.failures_left["flaky"] = 2
    calls = [ToolCall(tool_name="flaky", arguments={}, call_id="c1")]

    started = time.perf_counter()
    results, _, _ = await _run(
        calls, toolset, retry=KnotRetryPolicy(max_attempts=3, base_delay=0.04, jitter=False)
    )

    assert results[0].status == "ok"
    assert time.perf_counter() - started >= 0.12


async def test_retry_exhausted_returns_error() -> None:
    toolset = _named(["flaky"])
    Probe.failures_left["flaky"] = 5
    calls = [ToolCall(tool_name="flaky", arguments={}, call_id="c1")]

    results, _, _ = await _run(
        calls, toolset, retry=KnotRetryPolicy(max_attempts=2, base_delay=0.0, jitter=False)
    )

    assert Probe.calls["flaky"] == 2  # initial attempt + 1 retry
    assert results[0].status == "error"


async def test_unknown_tool_yields_error_and_batch_completes() -> None:
    toolset = _named(["good"], result="value")
    calls = [
        ToolCall(tool_name="missing", arguments={}, call_id="c1"),
        ToolCall(tool_name="good", arguments={}, call_id="c2"),
    ]

    results, _, _ = await _run(calls, toolset)

    by_id = {r.call_id: r for r in results}
    assert by_id["c1"].status == "error"
    assert by_id["c1"].error is not None and "missing" in by_id["c1"].error
    assert by_id["c1"].exception is not None
    assert by_id["c1"].exception.exc_type == "ToolNotFoundError"
    assert by_id["c2"].status == "ok"


async def test_results_returned_in_input_order() -> None:
    # Later calls finish first (descending latency) yet order must follow input.
    names = [f"t{i}" for i in range(4)]
    toolset = _named(names)
    calls = [
        ToolCall(tool_name=n, arguments={"latency": (4 - i) * 0.02, "result": i}, call_id=f"c{i}")
        for i, n in enumerate(names)
    ]

    results, _, _ = await _run(calls, toolset)

    assert tuple(r.call_id for r in results) == ("c0", "c1", "c2", "c3")
    assert tuple(r.result for r in results) == (0, 1, 2, 3)


async def test_every_call_gets_its_own_lineage_row_under_its_call_id() -> None:
    toolset = _named(["a", "b"])
    calls = [
        ToolCall(tool_name="a", arguments={}, call_id="c1"),
        ToolCall(tool_name="b", arguments={}, call_id="c2"),
    ]

    _, run, t = await _run(calls, toolset)

    rows = await _inner_rows(t, run)
    assert rows["c1"].outcome == "ok"
    assert rows["c2"].outcome == "ok"
    assert rows["results"].outcome == "ok"


async def test_empty_batch_produces_an_empty_tuple() -> None:
    results, _, _ = await _run([], Toolset())
    assert results == ()


async def test_empty_batch_declares_no_unused_concurrency_group() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        results, _, _ = await _run([], Toolset())
    assert results == ()
    assert not [w for w in caught if issubclass(w.category, UnusedConcurrencyGroupWarning)]


async def test_rejects_non_tool_call() -> None:
    with Tapestry():
        executor = ParallelToolExecutor(
            tool_calls=[], toolset=Toolset(), _config=KnotConfig(id="pte", validate_io=False)
        )
    with pytest.raises(TypeError):
        await executor.process(
            tool_calls=["not-a-call"],
            toolset=Toolset(),
            max_concurrency=8,
        )


async def test_rejects_non_toolset() -> None:
    # This knot is constructed with validate_io=False in production
    # (ReWooPipeline), so process() carries its own isinstance guard.
    with Tapestry():
        executor = ParallelToolExecutor(
            tool_calls=[], toolset=Toolset(), _config=KnotConfig(id="pte", validate_io=False)
        )
    with pytest.raises(TypeError):
        await executor.process(
            tool_calls=[],
            toolset=["not-a-toolset"],
            max_concurrency=8,
        )


async def test_cancellation_propagates_and_cancels_inflight() -> None:
    toolset = _named(["slow"])
    calls = [ToolCall(tool_name="slow", arguments={"latency": 5.0}, call_id="c1")]
    with Tapestry() as t:
        ParallelToolExecutor(tool_calls=calls, toolset=toolset, _config=KnotConfig(id="pte"))

    task = asyncio.ensure_future(t.run(RunRequest()))
    await asyncio.sleep(0.1)  # let the call start and block on its sleep
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert Probe.cancelled.get("slow", 0) == 1


async def test_error_path_carries_the_exception_record() -> None:
    """The tool path keeps type and traceback, not just a string."""
    toolset = _named(["t"])
    Probe.failures_left["t"] = 1

    results, _, _ = await _run([ToolCall(tool_name="t", arguments={}, call_id="c1")], toolset)

    assert results[0].status == "error"
    record = results[0].exception
    assert record is not None
    assert record.exc_type == "RuntimeError"
    assert record.message == "t transient failure"
    assert "RuntimeError: t transient failure" in record.traceback_text
    # The string stays available and agrees with the record.
    assert results[0].error == "RuntimeError: t transient failure"
