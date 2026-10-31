"""Cancellation through a whole run (PIR-849).

Cancellation is how an ``asyncio`` timeout, a task group's teardown and
interpreter shutdown all reach the code they are tearing down, so a run has to
let it through.  ``Knot.__call__``, the fan-out and ``SubTapestry.__call__``
each turn an exception a knot raises into ``Err``; a cancellation of the task
is not the knot's to report and propagates instead.

These tests pin that property where a caller sees it: an outer
``asyncio.wait_for`` around ``Tapestry.run`` raises ``TimeoutError`` rather
than returning a failed ``RunResult``, cancelling the task running a run
reaches the awaiter, everything the run had in flight is wound down *before*
the awaiter sees the cancellation, a cancelled run leaves no ``Err`` behind,
and a retry policy does not re-attempt a cancelled knot.  The last test is the
guard in the other direction: an ordinary failure is still recorded as an
``Err``, exactly as before.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.map import Map
from pirn.core.parameter import Parameter
from pirn.core.run_result import RunResult
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.timeout(60)


class _Blocking(Knot):
    """Blocks until cancelled, logging what it started, cancelled and finished.

    ``cancelled`` is appended from the ``except`` clause before the
    cancellation is re-raised, so a test can tell "the knot was cancelled and
    its cleanup ran" from "the knot is still sitting on the loop".
    """

    def __init__(self, *, log: dict[str, list[str]], **kwargs: Any) -> None:
        self._log = log
        super().__init__(**kwargs)

    async def process(self, x: int, **_: Any) -> int:
        self._log.setdefault("started", []).append(self.knot_id)
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self._log.setdefault("cancelled", []).append(self.knot_id)
            raise
        self._log.setdefault("finished", []).append(self.knot_id)
        return x


class _BlockingSource(Source):
    """``_Blocking`` with no inputs, for a loop iteration's inner tapestry."""

    def __init__(self, *, log: dict[str, list[str]], **kwargs: Any) -> None:
        self._log = log
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        self._log.setdefault("started", []).append(self.knot_id)
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self._log.setdefault("cancelled", []).append(self.knot_id)
            raise
        self._log.setdefault("finished", []).append(self.knot_id)
        return 1


def _blocking_run(log: dict[str, list[str]], *, history: InMemoryHistory | None = None) -> Tapestry:
    tapestry = Tapestry(history=history) if history is not None else Tapestry()
    with tapestry:
        upstream = Parameter("x", int, default=1, _config=KnotConfig(id="up"))
        _Blocking(x=upstream, log=log, _config=KnotConfig(id="blocked"))
    return tapestry


async def test_an_outer_wait_for_around_a_blocked_run_raises_timeout_error() -> None:
    # Arrange: the ticket's acceptance test.  A swallowed cancellation makes
    # the blocked knot "finish" with an Err, so wait_for returns a failed
    # RunResult and never raises.
    log: dict[str, list[str]] = {}
    tapestry = _blocking_run(log)

    # Act / Assert
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(tapestry.run(), timeout=0.1)
    assert log["started"] == ["blocked"]
    assert log["cancelled"] == ["blocked"]
    assert "finished" not in log


async def test_cancelling_the_task_running_a_run_propagates_to_the_awaiter() -> None:
    # Arrange
    log: dict[str, list[str]] = {}
    tapestry = _blocking_run(log)
    task = asyncio.create_task(tapestry.run())
    await asyncio.sleep(0.05)

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task
    assert log["cancelled"] == ["blocked"]
    assert "finished" not in log


async def test_a_cancelled_run_records_no_err_for_the_knot() -> None:
    # Arrange: a cancelled run never completes, so it persists nothing -- no
    # RunResult, no lineage row, and in particular no Err that would read like
    # the knot failed on its own.
    log: dict[str, list[str]] = {}
    history = InMemoryHistory()
    tapestry = _blocking_run(log, history=history)
    task = asyncio.create_task(tapestry.run())
    await asyncio.sleep(0.05)

    # Act
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Assert
    assert await history.query_lineage_by_knot_id("blocked") == []
    assert await history.query_lineage_by_knot_id("up") == []


class _BlockingSub(SubTapestry):
    def __init__(self, *, log: dict[str, list[str]], **kwargs: Any) -> None:
        self._log = log
        super().__init__(**kwargs)

    async def process(self, x: int, **_: Any) -> Knot:
        inner_upstream = Parameter("x", int, default=x, _config=KnotConfig(id="inner_up"))
        return _Blocking(x=inner_upstream, log=self._log, _config=KnotConfig(id="inner_blocked"))


async def test_cancellation_through_a_sub_tapestry_winds_the_inner_run_down() -> None:
    # Arrange
    log: dict[str, list[str]] = {}
    with Tapestry() as tapestry:
        upstream = Parameter("x", int, default=1, _config=KnotConfig(id="up"))
        _BlockingSub(x=upstream, log=log, _config=KnotConfig(id="sub"))
    task = asyncio.create_task(tapestry.run())
    await asyncio.sleep(0.1)
    assert log["started"] == ["inner_blocked"]

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task
    assert log["cancelled"] == ["inner_blocked"]
    assert "finished" not in log


async def test_a_sub_tapestry_timeout_is_recorded_as_a_knot_timeout_error() -> None:
    # Arrange: the scenario the ticket was raised from.  ``KnotConfig.timeout``
    # puts the container's own dispatch under ``asyncio.wait_for`` in the
    # dispatching task, so the expiry's cancellation lands inside
    # ``SubTapestry.__call__``.  Swallowed, it returns an ordinary failed
    # result, ``wait_for`` sees a body that completed and never raises
    # ``TimeoutError``, and the run records the inner deadlock as
    # ``Err(CancelledError)`` -- a knot that reported its own cancellation --
    # instead of the timeout that actually happened.
    log: dict[str, list[str]] = {}
    with Tapestry() as tapestry:
        upstream = Parameter("x", int, default=1, _config=KnotConfig(id="up"))
        _BlockingSub(x=upstream, log=log, _config=KnotConfig(id="sub", timeout=0.1))

    # Act
    result = await tapestry.run()

    # Assert
    assert not result.succeeded
    assert [rec.exc_type for rec in result.exceptions] == ["KnotTimeoutError"]
    assert log["cancelled"] == ["inner_blocked"]
    assert "finished" not in log


class _BlockingLoop(LoopSubTapestry[int]):
    """A loop whose every iteration blocks forever."""

    def __init__(self, *, log: dict[str, list[str]], **kwargs: Any) -> None:
        self._log = log
        super().__init__(**kwargs)

    async def astep(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= 2:
            return None
        with Tapestry() as iteration:
            _BlockingSource(log=self._log, _config=KnotConfig(id=f"iter_{state}"))
        return iteration, state + 1

    async def afold(self, state: int, result: RunResult) -> int:
        return state


async def test_cancellation_through_a_loop_sub_tapestry_iteration_propagates() -> None:
    # Arrange
    log: dict[str, list[str]] = {}
    with Tapestry() as tapestry:
        upstream = Parameter("state", int, default=0, _config=KnotConfig(id="seed"))
        _BlockingLoop(state=upstream, log=log, _config=KnotConfig(id="loop"))
    task = asyncio.create_task(tapestry.run())
    await asyncio.sleep(0.1)
    assert log["started"] == ["iter_0"]

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task
    assert log["cancelled"] == ["iter_0"]
    assert "finished" not in log


class _CountingBlocking(Knot):
    """Counts its attempts, then blocks until cancelled."""

    def __init__(self, *, attempts: list[str], **kwargs: Any) -> None:
        self._attempts = attempts
        super().__init__(**kwargs)

    async def process(self, x: int, **_: Any) -> int:
        self._attempts.append(self.knot_id)
        await asyncio.sleep(30)
        return x


async def test_retry_does_not_reattempt_after_a_cancellation() -> None:
    # Arrange: a retry policy re-dispatches an Err.  A cancellation recorded as
    # an Err would be retried -- up to max_attempts fresh attempts of a knot
    # whose run is already being torn down.
    attempts: list[str] = []
    policy = KnotRetryPolicy(max_attempts=5, base_delay=0.0, max_delay=0.0, jitter=False)
    with Tapestry() as tapestry:
        upstream = Parameter("x", int, default=1, _config=KnotConfig(id="up"))
        _CountingBlocking(
            x=upstream, attempts=attempts, _config=KnotConfig(id="flaky", retry=policy)
        )
    task = asyncio.create_task(tapestry.run())
    await asyncio.sleep(0.05)

    # Act
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Assert
    await asyncio.sleep(0.1)
    assert attempts == ["flaky"]


async def test_a_cancelled_fan_out_winds_every_element_down() -> None:
    # Arrange: asyncio.wait does not cancel what it waits on when the waiter is
    # cancelled, so every element used to be left orphaned on the loop, still
    # running its process() after the run had already raised.
    log: dict[str, list[str]] = {}
    with Tapestry() as tapestry:
        upstream = Parameter("x", list, default=[1, 2, 3], _config=KnotConfig(id="up"))
        _Blocking(x=Map(upstream), log=log, _config=KnotConfig(id="elements"))
    task = asyncio.create_task(tapestry.run())
    await asyncio.sleep(0.05)
    assert log["started"] == ["elements"] * 3

    # Act
    task.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await task
    assert log["cancelled"] == ["elements"] * 3
    assert "finished" not in log


async def test_an_ordinary_failure_in_a_run_is_still_recorded_as_an_err() -> None:
    # Arrange: the guard in the other direction -- the cancellation rule must
    # not turn a real failure into a propagating exception.
    class _Boom(Knot):
        async def process(self, x: int, **_: Any) -> int:
            raise RuntimeError("boom")

    history = InMemoryHistory()
    with Tapestry(history=history) as tapestry:
        upstream = Parameter("x", int, default=1, _config=KnotConfig(id="up"))
        _Boom(x=upstream, _config=KnotConfig(id="boom"))

    # Act
    result = await tapestry.run()

    # Assert
    assert not result.succeeded
    assert [rec.exc_type for rec in result.exceptions] == ["RuntimeError"]
    assert [rec.message for rec in result.exceptions] == ["boom"]
    assert await history.get_run(result.run_id) is not None
