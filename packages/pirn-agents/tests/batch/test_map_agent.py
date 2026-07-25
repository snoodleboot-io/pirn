"""Isolation, concurrency, ordering, backpressure, timeout, retry, and
cancellation tests for :class:`MapAgent` (F28-S1).

Written in the project's ``asyncio_mode = "auto"`` style: module-level
``async def test_...`` functions with plain ``assert`` statements. Stub doubles
make every behaviour deterministic without real elapsed time.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.batch.batch_item_status import BatchItemStatus
from pirn_agents.batch.map_agent import MapAgent
from pirn_agents.llm.retry_policy import RetryPolicy
from tests.batch.batch_doubles import (
    InFlightCounter,
    StubAgent,
    TrackingIterable,
    gated_agent,
)


async def _drain(runner: MapAgent, inputs: object) -> list:
    return [result async for result in runner.run(inputs)]  # type: ignore[arg-type]


async def test_maps_agent_over_all_inputs() -> None:
    agent = StubAgent()
    runner = MapAgent(agent, concurrency=4)

    results = await _drain(runner, ["a", "b", "c"])

    by_key = {r.key: r for r in results}
    assert set(by_key) == {"0", "1", "2"}
    assert all(r.status is BatchItemStatus.OK for r in results)
    assert by_key["0"].output == "done:a"


async def test_single_item_failure_does_not_abort_batch() -> None:
    agent = StubAgent(fail_items={"bad"})
    runner = MapAgent(agent, concurrency=4)

    results = await _drain(runner, ["ok1", "bad", "ok2"])

    by_key = {r.key: r for r in results}
    assert by_key["0"].status is BatchItemStatus.OK
    assert by_key["1"].status is BatchItemStatus.ERROR
    assert by_key["1"].error is not None and "permanent failure" in by_key["1"].error
    assert by_key["2"].status is BatchItemStatus.OK


async def test_concurrency_cap_respected() -> None:
    counter = InFlightCounter()
    gate = asyncio.Event()
    runner = MapAgent(gated_agent(gate, counter), concurrency=2)

    task = asyncio.ensure_future(_drain(runner, list(range(6))))
    # Let the runner saturate its two slots before releasing the gate.
    for _ in range(20):
        await asyncio.sleep(0)
    assert counter.peak == 2
    gate.set()
    results = await task

    assert len(results) == 6
    assert counter.peak == 2


async def test_backpressure_pulls_inputs_lazily() -> None:
    counter = InFlightCounter()
    gate = asyncio.Event()
    source = TrackingIterable(list(range(10)))
    runner = MapAgent(gated_agent(gate, counter), concurrency=3)

    task = asyncio.ensure_future(_drain(runner, source))
    for _ in range(20):
        await asyncio.sleep(0)
    # Only enough items to fill the 3 in-flight slots have been pulled.
    assert source.pulled == 3
    gate.set()
    await task
    assert source.pulled == 10


async def test_results_stream_in_completion_order() -> None:
    # Item 0 is slow, item 1 is fast: the fast one settles (and is yielded) first.
    async def agent(item: object) -> object:
        await asyncio.sleep(0.05 if item == "slow" else 0.0)
        return f"done:{item}"

    runner = MapAgent(agent, concurrency=4)

    order = [r.key async for r in runner.run(["slow", "fast"])]

    assert order == ["1", "0"]


async def test_timeout_isolated_from_siblings() -> None:
    async def agent(item: object) -> object:
        if item == "slow":
            await asyncio.sleep(0.5)
        return f"done:{item}"

    runner = MapAgent(agent, concurrency=4, timeout=0.05)

    results = await _drain(runner, ["slow", "fast"])

    by_key = {r.key: r for r in results}
    assert by_key["0"].status is BatchItemStatus.TIMEOUT
    assert by_key["0"].error is not None and "timed out" in by_key["0"].error
    assert by_key["1"].status is BatchItemStatus.OK


async def test_retry_then_success() -> None:
    agent = StubAgent(fail_times={"flaky": 2})
    runner = MapAgent(agent, concurrency=2, retries=2, retry_policy=RetryPolicy(base_delay=0.0))

    results = await _drain(runner, ["flaky"])

    assert results[0].status is BatchItemStatus.OK
    assert results[0].attempts == 3


async def test_retry_exhausted_returns_error() -> None:
    agent = StubAgent(fail_times={"flaky": 5})
    runner = MapAgent(agent, concurrency=2, retries=1, retry_policy=RetryPolicy(base_delay=0.0))

    results = await _drain(runner, ["flaky"])

    assert results[0].status is BatchItemStatus.ERROR
    assert results[0].attempts == 2


async def test_retry_delay_comes_from_the_composed_retry_policy() -> None:
    # The backoff delay is RetryPolicy.backoff_delay, not a hand-rolled formula.
    slept: list[float] = []

    async def _record(delay: float) -> None:
        slept.append(delay)

    policy = RetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=1.0, jitter=True)
    agent = StubAgent(fail_times={"flaky": 2})
    runner = MapAgent(
        agent, concurrency=2, retries=2, retry_policy=policy, rng=lambda: 0.5, sleep=_record
    )

    await _drain(runner, ["flaky"])

    assert slept == [
        policy.backoff_delay(0, rng=lambda: 0.5),
        policy.backoff_delay(1, rng=lambda: 0.5),
    ]


async def test_custom_key_fn_used_for_result_key() -> None:
    agent = StubAgent()
    runner = MapAgent(agent, concurrency=2, key_fn=lambda item: f"id-{item}")

    results = await _drain(runner, ["x", "y"])

    assert {r.key for r in results} == {"id-x", "id-y"}


async def test_empty_input_yields_nothing() -> None:
    runner = MapAgent(StubAgent(), concurrency=2)
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

    runner = MapAgent(_slow, concurrency=2)
    task = asyncio.ensure_future(_drain(runner, list(range(4))))
    for _ in range(20):
        await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert agent.cancelled >= 1


def test_rejects_non_callable_run_item() -> None:
    with pytest.raises(TypeError):
        MapAgent("not-callable")  # type: ignore[arg-type]


def test_rejects_bad_concurrency() -> None:
    with pytest.raises(ValueError):
        MapAgent(StubAgent(), concurrency=0)


def test_rejects_negative_retries() -> None:
    with pytest.raises(ValueError):
        MapAgent(StubAgent(), retries=-1)
