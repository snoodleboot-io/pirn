"""Schedule tests for :class:`IntervalTrigger` (PIR-723 / WS8-D2).

``IntervalTrigger`` is a core :class:`pirn.triggers.base.Trigger` that delegates
its schedule to :class:`pirn.triggers.cron.CronTrigger`'s ``delay_fn`` seam, so
these tests assert both the core contract (``name``/``stream()``/``close()``
yielding ``RunRequest``) and the schedule itself. The injected ``sleep`` records
the scheduled delays with no wall-clock wait, keeping the fixed-interval path,
the ``delay_fn`` cron seam, the ``max_fires`` bound and the constructor
validation deterministic.
"""

from __future__ import annotations

import asyncio

import pytest
from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger

from pirn_agents.batch.interval_trigger import IntervalTrigger


async def test_is_a_core_trigger() -> None:
    trigger = IntervalTrigger(interval=0.0, max_fires=1)

    assert isinstance(trigger, Trigger)
    assert trigger.name == "IntervalTrigger"


async def test_fires_on_fixed_interval_bounded_by_max_fires() -> None:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    trigger = IntervalTrigger(interval=5.0, max_fires=3, sleep=fake_sleep)

    requests = [request async for request in trigger.stream()]

    assert [request.parameters["fire_ordinal"] for request in requests] == [1, 2, 3]
    assert all(isinstance(request, RunRequest) for request in requests)
    # The delay is awaited *before* every fire, ordinal 1 included: an interval
    # batch collects a window's worth of data before it runs.
    assert recorded == [5.0, 5.0, 5.0]


async def test_delay_fn_is_the_cron_seam() -> None:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    # A cron backend would supply "seconds until next instant"; here ordinal*2.
    trigger = IntervalTrigger(delay_fn=lambda ordinal: ordinal * 2.0, max_fires=2, sleep=fake_sleep)

    requests = [request async for request in trigger.stream()]

    assert [request.parameters["fire_ordinal"] for request in requests] == [1, 2]
    assert recorded == [2.0, 4.0]


async def test_zero_interval_still_awaits_the_sleep() -> None:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    trigger = IntervalTrigger(interval=0.0, max_fires=2, sleep=fake_sleep)

    requests = [request async for request in trigger.stream()]

    assert [request.parameters["fire_ordinal"] for request in requests] == [1, 2]
    # A zero delay is still awaited so an unbounded zero-interval trigger stays
    # cooperative rather than starving the event loop.
    assert recorded == [0.0, 0.0]


async def test_close_ends_an_unbounded_stream() -> None:
    async def fake_sleep(delay: float) -> None:
        return None

    trigger = IntervalTrigger(interval=1.0, sleep=fake_sleep)
    stream = trigger.stream()

    first = await anext(stream)
    await trigger.close()

    assert first.parameters["fire_ordinal"] == 1
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


async def test_close_is_idempotent() -> None:
    trigger = IntervalTrigger(interval=1.0)

    await trigger.close()
    await trigger.close()


async def test_sequential_streams_are_independent() -> None:
    """Each ``stream()`` call numbers its own fires from 1, as ``fires()`` did."""

    async def fake_sleep(delay: float) -> None:
        return None

    trigger = IntervalTrigger(interval=1.0, max_fires=2, sleep=fake_sleep)

    first = [request.parameters["fire_ordinal"] async for request in trigger.stream()]
    second = [request.parameters["fire_ordinal"] async for request in trigger.stream()]

    assert first == [1, 2]
    assert second == [1, 2]


async def test_concurrent_streams_do_not_interleave_ordinals() -> None:
    """Two live consumers each see a full 1..n run, never a shared counter."""

    async def fake_sleep(delay: float) -> None:
        # Yield to the loop so the two consumers genuinely interleave; a shared
        # ordinal counter shows up as 1,3,5 / 2,4,6 rather than 1,2,3 / 1,2,3.
        await asyncio.sleep(0)

    trigger = IntervalTrigger(interval=0.0, max_fires=3, sleep=fake_sleep)

    async def drain() -> list[int]:
        return [request.parameters["fire_ordinal"] async for request in trigger.stream()]

    first, second = await asyncio.gather(drain(), drain())

    assert first == [1, 2, 3]
    assert second == [1, 2, 3]


def test_requires_exactly_one_of_interval_or_delay_fn() -> None:
    with pytest.raises(ValueError):
        IntervalTrigger()
    with pytest.raises(ValueError):
        IntervalTrigger(interval=1.0, delay_fn=lambda o: 1.0)


def test_rejects_negative_interval_and_bad_max_fires() -> None:
    with pytest.raises(ValueError):
        IntervalTrigger(interval=-1.0)
    with pytest.raises(ValueError):
        IntervalTrigger(interval=1.0, max_fires=0)
