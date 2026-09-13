"""``KnotConfig.timeout`` / ``KnotConfig.retry`` through a real run (WS0).

The engine, not the knot, honours both: a timed-out attempt is recorded as
``Err(KnotTimeoutError)`` and skips its children, a flaky knot under a retry
policy succeeds with its attempt count in lineage, and a knot that holds an
admission slot while retrying still gives it back.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.timeout(60)

_fast_retry = KnotRetryPolicy(max_attempts=3, base_delay=0.001, max_delay=0.001, jitter=False)


class _Flaky(Knot):
    """Fails the first ``failures`` calls, then succeeds.

    Counts on a ``_mutable_`` slot: the engine dispatches a run-scoped copy and
    reuses that copy for every attempt, so the count survives across attempts
    while the graph knot stays untouched.
    """

    def __init__(self, *, failures: int, **kwargs: Any) -> None:
        self._failures = failures
        self._mutable_calls = 0
        super().__init__(**kwargs)

    async def process(self, x: int, **_: Any) -> int:
        self._mutable_calls += 1
        if self._mutable_calls <= self._failures:
            raise RuntimeError(f"flake {self._mutable_calls}")
        return x + self._mutable_calls


class _Sleeper(Knot):
    async def process(self, x: int, seconds: float, **_: Any) -> int:
        await asyncio.sleep(seconds)
        return x


class _Echo(Knot):
    async def process(self, x: int, **_: Any) -> int:
        return x


async def test_a_flaky_knot_succeeds_under_retry_and_records_its_attempts() -> None:
    # Arrange
    with Tapestry() as t:
        p = Parameter("x", int, default=10, _config=KnotConfig(id="p"))
        flaky = _Flaky(failures=2, x=p, _config=KnotConfig(id="flaky", retry=_fast_retry))
        _Echo(x=flaky, _config=KnotConfig(id="child"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert result.succeeded
    assert result.outputs["flaky"] == 13
    assert result.outputs["child"] == 13
    record = next(rec for rec in result.lineage if rec.knot_id == "flaky")
    assert record.extra["attempts"] == 3
    assert record.outcome == "ok"


async def test_retry_exhaustion_records_the_last_err() -> None:
    # Arrange
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _Flaky(failures=10, x=p, _config=KnotConfig(id="flaky", retry=_fast_retry))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert not result.succeeded
    assert [rec.message for rec in result.exceptions] == ["flake 3"]
    record = next(rec for rec in result.lineage if rec.knot_id == "flaky")
    assert record.extra["attempts"] == 3


async def test_a_knot_without_a_policy_reports_no_attempts() -> None:
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _Echo(x=p, _config=KnotConfig(id="echo"))
    result = await t.run(RunRequest())
    record = next(rec for rec in result.lineage if rec.knot_id == "echo")
    assert "attempts" not in record.extra


async def test_a_timed_out_knot_is_an_err_and_its_children_are_skipped() -> None:
    # Arrange
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        slow = _Sleeper(x=p, seconds=10.0, _config=KnotConfig(id="slow", timeout=0.05))
        _Echo(x=slow, _config=KnotConfig(id="child"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert not result.succeeded
    assert [rec.exc_type for rec in result.exceptions] == ["KnotTimeoutError"]
    assert result.skipped == ["child"]
    assert "slow" not in result.outputs


async def test_a_timely_knot_is_unaffected_by_its_timeout() -> None:
    with Tapestry() as t:
        p = Parameter("x", int, default=7, _config=KnotConfig(id="p"))
        _Sleeper(x=p, seconds=0.0, _config=KnotConfig(id="quick", timeout=5.0))
    result = await t.run(RunRequest())
    assert result.outputs["quick"] == 7


async def test_a_timed_out_attempt_is_retried_under_a_policy() -> None:
    # Arrange: the first attempt sleeps past the timeout; the retry is instant.
    class _SlowOnce(Knot):
        def __init__(self, **kwargs: Any) -> None:
            self._mutable_calls = 0
            super().__init__(**kwargs)

        async def process(self, x: int, **_: Any) -> int:
            self._mutable_calls += 1
            if self._mutable_calls == 1:
                await asyncio.sleep(10.0)
            return x

    with Tapestry() as t:
        p = Parameter("x", int, default=4, _config=KnotConfig(id="p"))
        _SlowOnce(x=p, _config=KnotConfig(id="k", timeout=0.05, retry=_fast_retry))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert result.succeeded
    assert result.outputs["k"] == 4
    assert next(rec for rec in result.lineage if rec.knot_id == "k").extra["attempts"] == 2


async def test_a_retrying_knot_gives_its_slot_back() -> None:
    # Arrange: under a cap of one, a knot that retries must not wedge the run.
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _Flaky(failures=1, x=p, _config=KnotConfig(id="flaky", retry=_fast_retry))
        for i in range(3):
            _Echo(x=p, _config=KnotConfig(id=f"e{i}"))

    # Act
    result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1)))

    # Assert
    assert result.succeeded
    assert {"flaky", "e0", "e1", "e2"} <= set(result.outputs)


async def test_a_timeout_on_a_worker_thread_is_recorded_without_stopping_the_thread() -> None:
    # Arrange: the thread keeps sleeping; the engine must still record the
    # timeout promptly and finish the run.
    dispatcher = ThreadDispatcher(max_workers=2)
    try:
        with Tapestry(dispatcher=dispatcher) as t:
            p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
            _Sleeper(x=p, seconds=0.5, _config=KnotConfig(id="slow", timeout=0.05))

        # Act
        result = await asyncio.wait_for(t.run(RunRequest()), timeout=5.0)

        # Assert
        assert [rec.exc_type for rec in result.exceptions] == ["KnotTimeoutError"]
    finally:
        dispatcher.shutdown(wait=True)
