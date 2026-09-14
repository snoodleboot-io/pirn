"""``MapAgent.run`` yields each item the moment it settles (ADR agents-speaks-core, WS0b).

WS4b's engine-scheduled ``MapAgent`` joined its items through a core
``Aggregator``, so the standalone ``run()`` shim could only yield the whole
batch once the join completed. Core's ``Emitter.on_knot_result`` now fires
inside the engine loop as each knot settles, and ``_BatchItemStreamer``
turns that into the pre-migration stream: a fast item is yielded while a
slow sibling is still running.
"""

from __future__ import annotations

import asyncio

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped

from pirn_agents.batch.map_agent import MapAgent


async def test_a_fast_item_is_yielded_before_a_slow_sibling_finishes() -> None:
    # Arrange: "slow" blocks on a gate the test controls; "fast" returns at once.
    release = asyncio.Event()

    async def agent(item: object) -> object:
        if item == "slow":
            await release.wait()
        return f"done:{item}"

    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="stream", concurrency=4
    )
    stream = runner.run(["slow", "fast"])

    # Act: the first result must arrive while "slow" is still held.
    first = await asyncio.wait_for(stream.__anext__(), timeout=5)

    # Assert
    assert not release.is_set()
    assert first.key == "1"
    assert first.succeeded
    assert first.output == "done:fast"

    release.set()
    rest = [result async for result in stream]
    assert [r.key for r in rest] == ["0"]
    assert rest[0].output == "done:slow"


async def test_every_item_is_yielded_exactly_once_in_completion_order() -> None:
    order: list[str] = []

    async def agent(item: object) -> object:
        await asyncio.sleep(0.01 * (3 - int(str(item))))
        order.append(str(item))
        return item

    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="order", concurrency=4
    )

    results = [result async for result in runner.run([0, 1, 2, 3])]

    assert sorted(r.key for r in results) == ["0", "1", "2", "3"]
    assert [r.key for r in results] == order


async def test_a_failed_item_streams_with_its_exception_record_and_attempts() -> None:
    async def agent(item: object) -> object:
        raise ValueError(f"nope {item}")

    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="fail",
        concurrency=2,
        retries=1,
    )

    (only,) = [result async for result in runner.run(["x"])]

    assert isinstance(only.outcome, Err)
    assert only.exception is not None
    assert only.exception.exc_type == "ValueError"
    assert only.exception.knot_id == "item:fail:0"
    # The lineage row carries the attempt count the Aggregator join could not.
    assert only.attempts == 2


async def test_resumed_items_are_yielded_first_and_not_re_run() -> None:
    # Arrange: run once against a history, then again with the same batch id.
    calls: list[object] = []

    async def agent(item: object) -> object:
        calls.append(item)
        return item

    history = InMemoryHistory()
    first_runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="resume",
        concurrency=2,
        history=history,
    )
    await asyncio.wait_for(_drain(first_runner, ["a", "b"]), timeout=5)
    assert calls == ["a", "b"] or calls == ["b", "a"]

    second_runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        batch_id="resume",
        concurrency=2,
        history=history,
    )

    # Act
    results = await asyncio.wait_for(_drain(second_runner, ["a", "b", "c"]), timeout=5)

    # Assert: the two resumed items come first as SKIPPED, the new one ran.
    assert all(isinstance(r.outcome, Skipped) for r in results[:2])
    assert results[2].key == "2"
    assert results[2].succeeded
    assert calls.count("c") == 1
    assert len(calls) == 3


async def test_closing_the_stream_early_cancels_the_run() -> None:
    release = asyncio.Event()
    cancelled: list[object] = []

    async def agent(item: object) -> object:
        if item == "slow":
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.append(item)
                raise
        return item

    runner = MapAgent(
        run_item=agent, _config=KnotConfig(id="map-agent"), batch_id="close", concurrency=4
    )
    stream = runner.run(["slow", "fast"])
    first = await asyncio.wait_for(stream.__anext__(), timeout=5)
    assert first.key == "1"

    await stream.aclose()

    assert cancelled == ["slow"]


async def _drain(runner: MapAgent, inputs: list[object]) -> list:
    return [result async for result in runner.run(inputs)]
