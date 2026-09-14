"""Isolation, concurrency, timeout, retry, and cancellation tests for
:class:`MapAgent` (ADR agents-speaks-core, WS4b).

WS4b replaced ``MapAgent``'s private ``asyncio.wait`` scheduler with the core
engine's own: per-item admission (``Admission``/``ConcurrencyLimits``),
timeout/retry (``KnotConfig``/``GovernedDispatch``), and joining
(``Aggregator`` under ``ErrorPolicy.RECEIVE_ERRORS``). Two behaviours this
changes, disclosed here rather than pinned silently:

* **Dispatch order** among same-depth sibling items is now the engine's own
  (topological order, tie-broken by knot id) rather than strict input order,
  so "which item ran first" is no longer asserted for concurrency > 1 —
  only "which items ran" and "how many were in flight at once".
* ``BatchItemResult.attempts`` is not populated by the engine-joined path
  (see :meth:`MapAgent._make_combine`'s docstring): a ``Result`` carries no
  attempt count, only ``KnotLineage.extra`` does. Tests below assert the
  *outcome* of a retried item, not its attempt count.

Written in the project's ``asyncio_mode = "auto"`` style: module-level
``async def test_...`` functions with plain ``assert`` statements. Stub
doubles make every behaviour deterministic without real elapsed time.
"""

from __future__ import annotations

import asyncio

import pytest
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig

from pirn_agents.batch.map_agent import MapAgent
from tests.batch.batch_doubles import InFlightCounter, StubAgent, TrackingIterable, gated_agent


async def _drain(runner: MapAgent, inputs: object) -> list:
    return [result async for result in runner.run(inputs)]  # type: ignore[arg-type]


async def test_maps_agent_over_all_inputs() -> None:
    agent = StubAgent()
    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="t1", concurrency=4
    )

    results = await _drain(runner, ["a", "b", "c"])

    by_key = {r.key: r for r in results}
    assert set(by_key) == {"0", "1", "2"}
    assert all(r.succeeded for r in results)
    assert by_key["0"].output == "done:a"


async def test_single_item_failure_does_not_abort_batch() -> None:
    agent = StubAgent(fail_items={"bad"})
    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="t2", concurrency=4
    )

    results = await _drain(runner, ["ok1", "bad", "ok2"])

    by_key = {r.key: r for r in results}
    assert by_key["0"].succeeded
    assert isinstance(by_key["1"].outcome, Err)
    assert by_key["1"].error is not None and "permanent failure" in by_key["1"].error
    assert by_key["2"].succeeded


async def test_failure_carries_an_exception_record() -> None:
    agent = StubAgent(fail_items={"bad"})
    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="t3", concurrency=1
    )

    results = await _drain(runner, ["bad"])

    record = results[0].exception
    assert record is not None
    assert record.exc_type == "RuntimeError"
    assert "permanent failure" in record.message
    assert record.knot_id == "item:t3:0"


async def test_concurrency_cap_respected() -> None:
    counter = InFlightCounter()
    gate = asyncio.Event()
    runner = MapAgent(
        run_item=gated_agent(gate, counter),
        _config=KnotConfig(id="map-agent"),
        batch_id="t4",
        concurrency=2,
    )

    task = asyncio.ensure_future(_drain(runner, list(range(6))))
    # Let the runner saturate its two slots before releasing the gate.
    for _ in range(20):
        await asyncio.sleep(0)
    assert counter.peak == 2
    gate.set()
    results = await task

    assert len(results) == 6
    assert counter.peak == 2


async def test_every_item_runs_even_though_the_source_is_lazily_iterated() -> None:
    """The dataset is still consumed fully; only the pre-migration lazy-pull
    guarantee (see the module docstring) no longer applies -- ``run`` reads
    the whole iterable up front to build the item graph."""
    source = TrackingIterable(list(range(10)))
    runner = MapAgent(
        run_item=StubAgent(), _config=KnotConfig(id="map-agent"), batch_id="t5", concurrency=3
    )

    results = await _drain(runner, source)

    assert len(results) == 10
    assert source.pulled == 10


async def test_timeout_isolated_from_siblings() -> None:
    async def agent(item: object) -> object:
        if item == "slow":
            await asyncio.sleep(0.5)
        return f"done:{item}"

    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="t6",
        concurrency=4,
        timeout=0.05,
    )

    results = await _drain(runner, ["slow", "fast"])

    by_key = {r.key: r for r in results}
    assert by_key["0"].timed_out
    assert by_key["0"].error is not None
    assert by_key["1"].succeeded


async def test_timeout_carries_an_exception_record() -> None:
    async def agent(item: object) -> object:
        await asyncio.sleep(0.5)
        return f"done:{item}"

    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="t7",
        concurrency=1,
        timeout=0.05,
    )

    results = await _drain(runner, ["slow"])

    record = results[0].exception
    assert record is not None
    assert record.exc_type == "KnotTimeoutError"
    assert record.knot_id == "item:t7:0"


async def test_retry_then_success() -> None:
    agent = StubAgent(fail_times={"flaky": 2})
    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="t8", concurrency=2, retries=2
    )

    results = await _drain(runner, ["flaky"])

    assert results[0].succeeded


async def test_retry_exhausted_returns_error() -> None:
    agent = StubAgent(fail_times={"flaky": 5})
    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="t9", concurrency=2, retries=1
    )

    results = await _drain(runner, ["flaky"])

    assert isinstance(results[0].outcome, Err)


async def test_custom_key_fn_used_for_result_key() -> None:
    agent = StubAgent()
    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="t10",
        concurrency=2,
        key_fn=lambda item: f"id-{item}",
    )

    results = await _drain(runner, ["x", "y"])

    assert {r.key for r in results} == {"id-x", "id-y"}


async def test_empty_input_yields_nothing() -> None:
    runner = MapAgent(
        run_item=StubAgent(), _config=KnotConfig(id="map-agent"), batch_id="t11", concurrency=2
    )
    assert await _drain(runner, []) == []


async def test_cancellation_cancels_inflight_items() -> None:
    counter = InFlightCounter()
    gate = asyncio.Event()
    agent = StubAgent(latency=5.0, counter=counter)

    async def _slow(item: object) -> object:
        counter.enter()
        try:
            await gate.wait()
            return item
        except asyncio.CancelledError:
            agent.cancelled += 1
            raise
        finally:
            counter.leave()

    runner = MapAgent(
        run_item=_slow, _config=KnotConfig(id="map-agent"), batch_id="t12", concurrency=2
    )
    task = asyncio.ensure_future(_drain(runner, list(range(4))))
    for _ in range(20):
        await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert agent.cancelled >= 1


def test_rejects_non_callable_run_item() -> None:
    with pytest.raises(TypeError):
        MapAgent(run_item="not-callable", _config=KnotConfig(id="map-agent"))  # type: ignore[arg-type]


async def test_rejects_bad_concurrency() -> None:
    # Value checks run when the batch runs (knot-design-rules.md Rule 3).
    runner = MapAgent(run_item=StubAgent(), _config=KnotConfig(id="map-agent"), concurrency=0)
    with pytest.raises(ValueError):
        await _drain(runner, ["a"])


async def test_rejects_negative_retries() -> None:
    # Value checks run when the batch runs (knot-design-rules.md Rule 3).
    runner = MapAgent(run_item=StubAgent(), _config=KnotConfig(id="map-agent"), retries=-1)
    with pytest.raises(ValueError):
        await _drain(runner, ["a"])


async def test_rejects_empty_batch_id() -> None:
    # Value checks run when the batch runs (knot-design-rules.md Rule 3).
    runner = MapAgent(run_item=StubAgent(), _config=KnotConfig(id="map-agent"), batch_id="")
    with pytest.raises(ValueError):
        await _drain(runner, ["a"])
