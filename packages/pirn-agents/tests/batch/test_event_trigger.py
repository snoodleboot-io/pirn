"""On-demand tests for :class:`EventTrigger` (PIR-723 / WS8-D2).

``EventTrigger`` is a core :class:`pirn.triggers.base.Trigger` backed by an
in-process queue: each awaited :meth:`fire` yields one ``RunRequest`` carrying
its 1-based ``fire_ordinal``, and the now-async :meth:`close` ends the stream
idempotently. No broker is imported on this path.
"""

from __future__ import annotations

import asyncio

import pytest
from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger

from pirn_agents.batch.event_trigger import EventTrigger


async def test_is_a_core_trigger() -> None:
    trigger = EventTrigger()

    assert isinstance(trigger, Trigger)
    assert trigger.name == "EventTrigger"


async def test_one_run_request_per_fire_until_closed() -> None:
    trigger = EventTrigger()
    await trigger.fire()
    await trigger.fire()
    await trigger.close()

    requests = [request async for request in trigger.stream()]

    assert all(isinstance(request, RunRequest) for request in requests)
    assert [request.parameters["fire_ordinal"] for request in requests] == [1, 2]


async def test_close_stops_a_live_consumer() -> None:
    trigger = EventTrigger()
    seen: list[int] = []

    async def consume() -> None:
        async for request in trigger.stream():
            seen.append(request.parameters["fire_ordinal"])

    consumer = asyncio.ensure_future(consume())
    await trigger.fire()
    await asyncio.sleep(0)  # let the consumer drain the signal
    await trigger.close()
    await consumer

    assert seen == [1]


async def test_fire_after_close_raises() -> None:
    trigger = EventTrigger()
    await trigger.close()

    with pytest.raises(RuntimeError):
        await trigger.fire()


async def test_close_is_idempotent() -> None:
    trigger = EventTrigger()
    await trigger.close()
    await trigger.close()

    requests = [request async for request in trigger.stream()]

    # The second close must not queue a second sentinel that a later stream
    # would mistake for a live signal.
    assert requests == []


async def test_restreaming_an_ended_trigger_raises_instead_of_blocking() -> None:
    """Closing is terminal; a second stream must not park on a dead queue."""
    trigger = EventTrigger()
    await trigger.fire()
    await trigger.close()

    assert [request.parameters["fire_ordinal"] async for request in trigger.stream()] == [1]

    # Pre-fix this blocked forever in queue.get(): the sentinel was consumed by
    # the first stream and close() refuses to queue a second one.
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(anext(trigger.stream()), timeout=1.0)


async def test_a_second_concurrent_consumer_is_released_by_close() -> None:
    """No consumer may outlive close() parked on the queue waiting for a signal."""
    trigger = EventTrigger()

    async def drain() -> list[int]:
        return [request.parameters["fire_ordinal"] async for request in trigger.stream()]

    first = asyncio.ensure_future(drain())
    second = asyncio.ensure_future(drain())
    await asyncio.sleep(0)  # park both consumers on the empty queue
    await trigger.close()

    # Only one sentinel exists, so the other consumer is freed by the
    # closed-and-empty guard rather than waiting for a signal that cannot come.
    results = await asyncio.wait_for(asyncio.gather(first, second), timeout=1.0)

    assert results == [[], []]
