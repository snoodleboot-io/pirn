"""On-demand tests for :class:`EventTrigger` (F28-S5 / PIR-584).

Each awaited :meth:`fire` yields one ordinal; :meth:`close` ends the stream and a
fire afterwards is rejected. In-process queue only — no broker.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.batch.event_trigger import EventTrigger


async def test_one_ordinal_per_fire_until_closed() -> None:
    trigger = EventTrigger()
    await trigger.fire()
    await trigger.fire()
    trigger.close()

    ordinals = [ordinal async for ordinal in trigger.fires()]

    assert ordinals == [1, 2]


async def test_close_stops_a_live_consumer() -> None:
    trigger = EventTrigger()
    seen: list[int] = []

    async def consume() -> None:
        async for ordinal in trigger.fires():
            seen.append(ordinal)

    consumer = asyncio.ensure_future(consume())
    await trigger.fire()
    await asyncio.sleep(0)  # let the consumer drain the signal
    trigger.close()
    await consumer

    assert seen == [1]


async def test_fire_after_close_raises() -> None:
    trigger = EventTrigger()
    trigger.close()
    with pytest.raises(RuntimeError):
        await trigger.fire()
