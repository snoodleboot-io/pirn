"""Schedule tests for :class:`IntervalTrigger` (F28-S5 / PIR-584).

Injected ``sleep`` records the scheduled delays with no wall-clock wait, so the
fixed-interval path, the ``delay_fn`` cron seam, the ``max_fires`` bound, and the
constructor validation are all asserted deterministically.
"""

from __future__ import annotations

import pytest

from pirn_agents.batch.interval_trigger import IntervalTrigger


async def test_fires_on_fixed_interval_bounded_by_max_fires() -> None:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    trigger = IntervalTrigger(interval=5.0, max_fires=3, sleep=fake_sleep)

    ordinals = [ordinal async for ordinal in trigger.fires()]

    assert ordinals == [1, 2, 3]
    assert recorded == [5.0, 5.0, 5.0]


async def test_delay_fn_is_the_cron_seam() -> None:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    # A cron backend would supply "seconds until next instant"; here ordinal*2.
    trigger = IntervalTrigger(delay_fn=lambda ordinal: ordinal * 2.0, max_fires=2, sleep=fake_sleep)

    ordinals = [ordinal async for ordinal in trigger.fires()]

    assert ordinals == [1, 2]
    assert recorded == [2.0, 4.0]


async def test_zero_interval_does_not_sleep() -> None:
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    trigger = IntervalTrigger(interval=0.0, max_fires=2, sleep=fake_sleep)

    ordinals = [ordinal async for ordinal in trigger.fires()]

    assert ordinals == [1, 2]
    assert recorded == []


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
