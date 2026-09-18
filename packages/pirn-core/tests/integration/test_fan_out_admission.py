"""A fan-out's elements are bounded, timed and retried one element at a time.

``Knot._fan_out`` used to be a bare ``asyncio.gather`` inside the single
admission slot the knot was admitted with, so a ``Map`` started every element
at once whatever ``max_in_flight`` said, ``KnotConfig.timeout`` bounded the
whole batch and ``KnotConfig.retry`` re-ran all of it.  These tests fail on that
code and pass on the per-element one (PIR-873).
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import pytest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.map import Map
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.exceptions.knot_timeout_error import KnotTimeoutError
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.timeout(60)


class _PeakWatcher(Knot):
    """Records the greatest number of its own elements running at once."""

    async def process(self, value: int, **_: Any) -> int:
        live = type(self)._live + 1
        type(self)._live = live
        type(self)._peak = max(type(self)._peak, live)
        try:
            await asyncio.sleep(0.01)
            return value
        finally:
            type(self)._live -= 1

    _live: ClassVar[int] = 0
    _peak: ClassVar[int] = 0

    @classmethod
    def reset(cls) -> None:
        cls._live = 0
        cls._peak = 0


class _SlowForOneElement(Knot):
    """Sleeps far past the timeout for one nominated element only."""

    _slow_value: ClassVar[int] = 2

    async def process(self, value: int, **_: Any) -> int:
        if value == type(self)._slow_value:
            await asyncio.sleep(5)
        return value


class _SleepsPerElement(Knot):
    """Each element sleeps well under the timeout; the batch total is well over it."""

    _nap: ClassVar[float] = 0.08

    async def process(self, value: int, **_: Any) -> int:
        await asyncio.sleep(type(self)._nap)
        return value


class _FailsOneElementOnce(Knot):
    """One nominated element fails its first call; counts calls per element."""

    _calls: ClassVar[dict[int, int]] = {}

    async def process(self, value: int, **_: Any) -> int:
        seen = type(self)._calls.get(value, 0) + 1
        type(self)._calls[value] = seen
        if value == 2 and seen == 1:
            raise RuntimeError("transient on 2")
        return value

    @classmethod
    def reset(cls) -> None:
        cls._calls = {}


class _FailsOneElementForever(Knot):
    """One element always fails; the rest record whether they were cancelled."""

    _started: ClassVar[list[int]] = []
    _cancelled: ClassVar[list[int]] = []
    _completed: ClassVar[list[int]] = []

    async def process(self, value: int, **_: Any) -> int:
        type(self)._started.append(value)
        if value == 0:
            raise RuntimeError("always")
        try:
            await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            type(self)._cancelled.append(value)
            raise
        type(self)._completed.append(value)
        return value

    @classmethod
    def reset(cls) -> None:
        cls._started = []
        cls._cancelled = []
        cls._completed = []


async def test_element_concurrency_honours_max_in_flight() -> None:
    _PeakWatcher.reset()
    with Tapestry() as t:
        source = Parameter("xs", list[int], default=[1, 2, 3, 4, 5, 6], _config=KnotConfig(id="xs"))
        _PeakWatcher(value=Map(source), _config=KnotConfig(id="fan"))

    result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=2)))

    assert result.succeeded
    assert result.outputs["fan"] == [1, 2, 3, 4, 5, 6]
    assert _PeakWatcher._peak <= 2, f"{_PeakWatcher._peak} elements ran at once under a cap of 2"


async def test_element_concurrency_honours_the_knots_group_cap() -> None:
    _PeakWatcher.reset()
    with Tapestry() as t:
        source = Parameter("xs", list[int], default=[1, 2, 3, 4, 5, 6], _config=KnotConfig(id="xs"))
        _PeakWatcher(value=Map(source), _config=KnotConfig(id="fan", concurrency_group="api"))

    result = await t.run(RunRequest(concurrency=ConcurrencyLimits(groups={"api": 1})))

    assert result.succeeded
    assert _PeakWatcher._peak == 1, (
        f"{_PeakWatcher._peak} elements ran at once under a group cap of 1"
    )


async def test_an_unbounded_run_leaves_the_fan_out_unbounded() -> None:
    _PeakWatcher.reset()
    with Tapestry() as t:
        source = Parameter("xs", list[int], default=[1, 2, 3, 4], _config=KnotConfig(id="xs"))
        _PeakWatcher(value=Map(source), _config=KnotConfig(id="fan"))

    result = await t.run(RunRequest())

    assert result.succeeded
    assert _PeakWatcher._peak == 4


async def test_the_timeout_bounds_each_element_not_the_batch() -> None:
    # Three elements, 0.08 s each, run one at a time: 0.24 s of batch against a
    # 0.15 s timeout.  A batch-level timeout kills the knot; a per-element one
    # is never reached.
    with Tapestry() as t:
        source = Parameter("xs", list[int], default=[1, 2, 3], _config=KnotConfig(id="xs"))
        _SleepsPerElement(value=Map(source), _config=KnotConfig(id="fan", timeout=0.15))

    result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1)))

    assert result.succeeded, [record.exc_type for record in result.exceptions]
    assert result.outputs["fan"] == [1, 2, 3]


async def test_an_element_that_outlives_the_timeout_is_its_own_timeout_error() -> None:
    with Tapestry() as t:
        source = Parameter("xs", list[int], default=[1, 2, 3], _config=KnotConfig(id="xs"))
        _SlowForOneElement(value=Map(source), _config=KnotConfig(id="fan", timeout=0.1))

    result = await t.run(RunRequest())

    # The slow element's own expiry is what fails the knot, and it is a
    # KnotTimeoutError rather than a batch-wide cancellation.
    assert not result.succeeded
    assert any(record.exc_type == KnotTimeoutError.__name__ for record in result.exceptions), [
        record.exc_type for record in result.exceptions
    ]


async def test_retry_reruns_only_the_element_that_failed() -> None:
    _FailsOneElementOnce.reset()
    with Tapestry() as t:
        source = Parameter("xs", list[int], default=[1, 2, 3], _config=KnotConfig(id="xs"))
        _FailsOneElementOnce(
            value=Map(source),
            _config=KnotConfig(
                id="fan", retry=KnotRetryPolicy(max_attempts=2, base_delay=0.0, jitter=False)
            ),
        )

    result = await t.run(RunRequest())

    assert result.succeeded
    assert result.outputs["fan"] == [1, 2, 3]
    # Only element 2 ran twice. A batch-level retry re-ran the whole batch, so
    # elements 1 and 3 were called a second time even though they had already
    # produced their answer.
    assert _FailsOneElementOnce._calls == {1: 1, 2: 2, 3: 1}


async def test_the_first_failure_cancels_the_elements_still_running() -> None:
    _FailsOneElementForever.reset()
    with Tapestry() as t:
        source = Parameter("xs", list[int], default=[1, 2, 3, 0], _config=KnotConfig(id="xs"))
        _FailsOneElementForever(value=Map(source), _config=KnotConfig(id="fan"))

    result = await t.run(RunRequest())

    assert not result.succeeded
    assert sorted(_FailsOneElementForever._started) == [0, 1, 2, 3]
    # asyncio.gather propagates the first exception and leaves its siblings
    # running, so none of them was ever cancelled -- the docstring said
    # otherwise for as long as it existed.
    assert sorted(_FailsOneElementForever._cancelled) == [1, 2, 3]
    assert _FailsOneElementForever._completed == []
