"""Run-level and group concurrency limits (PIR-841 slice 2).

A run may cap how many knots are in flight at once (``max_in_flight``) and how
many knots of a named group are (``groups``).  These tests pin:

* exact peaks: a cap is reached, and never exceeded;
* no head-of-line blocking: a saturated group never holds up other knots;
* FIFO within a group, and no starvation behind a slow knot;
* slots come back on failure, skip and cancellation, so nothing deadlocks;
* limits change scheduling only -- never the record order or any hash;
* ``concurrency_group`` is not identity, so an old recording still replays.

Peaks are measured with a gauge that holds each knot inside its critical
section until the expected number of knots is in there with it.  A cap that
admits too few therefore times out, and one that admits too many is caught by
the peak assertion.  Nothing here waits on a sleep.
"""

from __future__ import annotations

import asyncio
import functools
import threading
from collections import Counter
from typing import Any

import pytest

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.lineage import KnotLineage
from pirn.core.parameter import Parameter
from pirn.core.result import Result
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.engine.admission.limited_admission_gate import LimitedAdmissionGate
from pirn.engine.admission.unbounded_admission_gate import UnboundedAdmissionGate
from pirn.engine.dispatchers.dispatcher import Dispatcher
from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.timeout(60)


class _Gauge:
    """Counts knots inside their critical section, overall and per group.

    A knot leaves only once the section holds as many knots as the test
    expects the limit to allow -- ``hold_global`` overall, or
    ``hold_groups[group]`` for its group -- or once every knot that could
    join it has already entered.  Counters are guarded by a thread lock so
    the same gauge serves knots on worker threads.
    """

    def __init__(
        self,
        *,
        hold_global: int | None = None,
        hold_groups: dict[str, int] | None = None,
    ) -> None:
        self.hold_global = hold_global
        self.hold_groups = dict(hold_groups or {})
        self.total = 0
        self.group_totals: Counter[str | None] = Counter()
        self.started = 0
        self.group_started: Counter[str | None] = Counter()
        self.in_flight = 0
        self.group_in_flight: Counter[str | None] = Counter()
        self.peak = 0
        self.group_peaks: Counter[str | None] = Counter()
        self.start_order: list[str] = []
        self.finish_order: list[str] = []
        self._lock = threading.Lock()
        self._thread_cond = threading.Condition(self._lock)
        self._async_cond: asyncio.Condition | None = None

    def register(self, group: str | None) -> None:
        self.total += 1
        self.group_totals[group] += 1

    def _enter(self, knot_id: str, group: str | None) -> None:
        self.started += 1
        self.group_started[group] += 1
        self.in_flight += 1
        self.group_in_flight[group] += 1
        self.peak = max(self.peak, self.in_flight)
        self.group_peaks[group] = max(self.group_peaks[group], self.group_in_flight[group])
        self.start_order.append(knot_id)

    def _leave(self, knot_id: str, group: str | None) -> None:
        self.in_flight -= 1
        self.group_in_flight[group] -= 1
        self.finish_order.append(knot_id)

    def may_leave(self, group: str | None) -> bool:
        if group is not None and group in self.hold_groups:
            return (
                self.group_in_flight[group] >= self.hold_groups[group]
                or self.group_started[group] == self.group_totals[group]
            )
        if self.hold_global is not None:
            return self.in_flight >= self.hold_global or self.started == self.total
        return True

    async def visit(
        self, knot_id: str, group: str | None, release: asyncio.Event | None = None
    ) -> None:
        """Enter, wait for company (and *release*, if given), then leave."""
        if self._async_cond is None:
            self._async_cond = asyncio.Condition()
        cond = self._async_cond
        async with cond:
            with self._lock:
                self._enter(knot_id, group)
            cond.notify_all()
            await cond.wait_for(functools.partial(self.may_leave, group))
        if release is not None:
            await release.wait()
        async with cond:
            with self._lock:
                self._leave(knot_id, group)
            cond.notify_all()

    def visit_blocking(self, knot_id: str, group: str | None) -> None:
        with self._thread_cond:
            self._enter(knot_id, group)
            self._thread_cond.notify_all()
            # Bounded: a regression must fail the test, not hang the worker.
            left = self._thread_cond.wait_for(functools.partial(self.may_leave, group), timeout=20)
            self._leave(knot_id, group)
            self._thread_cond.notify_all()
        if not left:
            raise TimeoutError(f"{knot_id} was never joined by the knots it waited for")


class _Gauged(Knot):
    """A knot that passes through a ``_Gauge`` and returns its own id."""

    def __init__(self, *, gauge: _Gauge, blocking: bool = False, **kwargs: Any) -> None:
        self._gauge = gauge
        self._blocking = blocking
        super().__init__(**kwargs)
        gauge.register(self.config.concurrency_group)

    async def process(self, **_inputs: Any) -> str:
        if self._blocking:
            # Runs on a ThreadDispatcher worker thread with its own loop.
            self._gauge.visit_blocking(self.knot_id, self.config.concurrency_group)
        else:
            await self._gauge.visit(self.knot_id, self.config.concurrency_group)
        return self.knot_id


class _Waiter(Knot):
    """Records its start, waits for a named event, then returns its id."""

    def __init__(
        self,
        *,
        log: list[str],
        events: dict[str, asyncio.Event],
        wait_for: str | None = None,
        announce: str | None = None,
        fail: bool = False,
        **kwargs: Any,
    ) -> None:
        self._log = log
        self._events = events
        self._wait_for = wait_for
        self._announce = announce
        self._fail = fail
        super().__init__(**kwargs)

    async def process(self, **_inputs: Any) -> str:
        self._log.append(f"start:{self.knot_id}")
        if self._announce is not None:
            self._events[self._announce].set()
        if self._wait_for is not None:
            await self._events[self._wait_for].wait()
        self._log.append(f"finish:{self.knot_id}")
        if self._fail:
            raise ValueError(f"{self.knot_id} failed on purpose")
        return self.knot_id


class _Counter(Knot):
    """Counts completions and sets an event once *expected* have finished."""

    def __init__(
        self, *, tally: dict[str, int], done: asyncio.Event, expected: int, **kwargs: Any
    ) -> None:
        self._tally = tally
        self._done = done
        self._expected = expected
        super().__init__(**kwargs)

    async def process(self, **_inputs: Any) -> str:
        self._tally["finished"] += 1
        if self._tally["finished"] == self._expected:
            self._done.set()
        return self.knot_id


class _SpyGate(LimitedAdmissionGate):
    """A LimitedAdmissionGate that remembers every instance built."""

    built: list[_SpyGate] = []  # noqa: RUF012 -- test-local registry

    def __init__(self, limits: ConcurrencyLimits) -> None:
        super().__init__(limits)
        _SpyGate.built.append(self)


@pytest.fixture
def spy_gates(monkeypatch: pytest.MonkeyPatch) -> list[_SpyGate]:
    _SpyGate.built = []
    monkeypatch.setattr("pirn.engine.engine.LimitedAdmissionGate", _SpyGate)
    return _SpyGate.built


def _siblings(
    gauge: _Gauge,
    width: int,
    *,
    group: str | None = None,
    prefix: str = "k",
    blocking: bool = False,
    tapestry: Tapestry | None = None,
) -> Tapestry:
    t = tapestry or Tapestry()
    with t:
        p = Parameter(f"x_{prefix}", int, default=1, _config=KnotConfig(id=f"p_{prefix}"))
        for i in range(width):
            _Gauged(
                x=p,
                gauge=gauge,
                blocking=blocking,
                _config=KnotConfig(id=f"{prefix}{i:03d}", concurrency_group=group),
            )
    return t


async def _run(t: Tapestry, limits: ConcurrencyLimits | None = None, **kwargs: Any) -> RunResult:
    return await asyncio.wait_for(t.run(RunRequest(concurrency=limits), **kwargs), timeout=30.0)


# ------------------------------------------------------------------ peaks


async def test_fifty_siblings_under_a_cap_of_eight_peak_at_exactly_eight() -> None:
    # Arrange
    gauge = _Gauge(hold_global=8)
    t = _siblings(gauge, 50)

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=8))

    # Assert
    assert result.succeeded
    assert len(result.outputs) == 51
    assert gauge.peak == 8


async def test_fifty_unbounded_siblings_peak_at_fifty() -> None:
    # Arrange: each knot waits until all 50 are inside together.
    gauge = _Gauge(hold_global=50)
    t = _siblings(gauge, 50)

    # Act
    result = await _run(t)

    # Assert
    assert result.succeeded
    assert gauge.peak == 50


async def test_empty_limits_are_unbounded(spy_gates: list[_SpyGate]) -> None:
    # Arrange
    gauge = _Gauge(hold_global=50)
    t = _siblings(gauge, 50)

    # Act
    result = await _run(t, ConcurrencyLimits())

    # Assert: no limited gate was even built.
    assert result.succeeded
    assert gauge.peak == 50
    assert spy_gates == []


async def test_a_cap_is_enforced_under_the_thread_dispatcher() -> None:
    # Arrange: knots run on worker threads, each on its own event loop; the
    # gate must still be touched only from the engine's loop, or it hangs.
    dispatcher = ThreadDispatcher(max_workers=50)
    gauge = _Gauge(hold_global=8)
    t = _siblings(gauge, 50, blocking=True, tapestry=Tapestry(dispatcher=dispatcher))

    # Act
    try:
        result = await _run(t, ConcurrencyLimits(max_in_flight=8))
    finally:
        dispatcher.shutdown(wait=False)

    # Assert
    assert result.succeeded
    assert gauge.peak == 8


async def test_a_group_cap_is_enforced_under_the_thread_dispatcher() -> None:
    # Arrange
    dispatcher = ThreadDispatcher(max_workers=40)
    gauge = _Gauge(hold_groups={"api": 3})
    t = Tapestry(dispatcher=dispatcher)
    _siblings(gauge, 20, group="api", prefix="api", blocking=True, tapestry=t)
    _siblings(gauge, 20, prefix="local", blocking=True, tapestry=t)

    # Act
    try:
        result = await _run(t, ConcurrencyLimits(groups={"api": 3}))
    finally:
        dispatcher.shutdown(wait=False)

    # Assert
    assert result.succeeded
    assert gauge.group_peaks["api"] == 3


# ---------------------------------------------------- groups and head of line


@pytest.mark.parametrize("api_calls", [4, 12])
async def test_a_full_api_group_does_not_hold_up_local_knots(api_calls: int) -> None:
    # Arrange: the ticket's example -- 200 local knots and a handful of API
    # calls in one wave, with the API group capped at 4 and no global cap.
    # API calls sort first, so they are at the head of the queue, and none
    # can finish until every local knot has.  Each local knot waits on a
    # 200-party barrier, so all 200 must be in flight together while the API
    # group is saturated.  Under a single FIFO the 5th API call would block
    # the queue and the run would time out.
    locals_width = 200
    log: list[str] = []
    events: dict[str, asyncio.Event] = {"locals_done": asyncio.Event()}
    barrier = asyncio.Barrier(locals_width)
    gauge = _Gauge(hold_groups={"api": min(4, api_calls)})
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        for i in range(api_calls):
            _ApiCall(
                x=p,
                gauge=gauge,
                released_by=events["locals_done"],
                log=log,
                _config=KnotConfig(id=f"api{i:02d}", concurrency_group="api"),
            )
        for i in range(locals_width):
            _Local(
                x=p,
                barrier=barrier,
                log=log,
                done=events["locals_done"],
                expected=locals_width,
                _config=KnotConfig(id=f"local{i:03d}"),
            )

    # Act
    result = await _run(t, ConcurrencyLimits(groups={"api": 4}))

    # Assert
    assert result.succeeded
    assert gauge.group_peaks["api"] == min(4, api_calls)
    first_api_finish = min(i for i, e in enumerate(log) if e.startswith("finish:api"))
    last_local_finish = max(i for i, e in enumerate(log) if e.startswith("finish:local"))
    assert last_local_finish < first_api_finish


class _ApiCall(Knot):
    """An API call held open until the local work is done, via a gauge."""

    def __init__(
        self,
        *,
        gauge: _Gauge,
        released_by: asyncio.Event,
        log: list[str],
        **kwargs: Any,
    ) -> None:
        self._gauge = gauge
        self._released_by = released_by
        self._log = log
        super().__init__(**kwargs)
        gauge.register(self.config.concurrency_group)

    async def process(self, **_inputs: Any) -> str:
        self._log.append(f"start:{self.knot_id}")
        await self._gauge.visit(
            self.knot_id, self.config.concurrency_group, release=self._released_by
        )
        self._log.append(f"finish:{self.knot_id}")
        return self.knot_id


class _Local(Knot):
    """Local work: waits until every local knot is in flight, then counts itself done."""

    def __init__(
        self,
        *,
        barrier: asyncio.Barrier,
        log: list[str],
        done: asyncio.Event,
        expected: int,
        **kwargs: Any,
    ) -> None:
        self._barrier = barrier
        self._log = log
        self._done = done
        self._expected = expected
        super().__init__(**kwargs)

    async def process(self, **_inputs: Any) -> str:
        await self._barrier.wait()
        self._log.append(f"finish:{self.knot_id}")
        if sum(e.startswith("finish:local") for e in self._log) == self._expected:
            self._done.set()
        return self.knot_id


async def test_a_global_cap_tighter_than_the_group_cap_wins() -> None:
    # Arrange
    gauge = _Gauge(hold_global=3)
    t = _siblings(gauge, 20, group="api")

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=3, groups={"api": 10}))

    # Assert
    assert result.succeeded
    assert gauge.peak == 3


async def test_a_group_cap_tighter_than_the_global_cap_wins() -> None:
    # Arrange
    gauge = _Gauge(hold_groups={"api": 2})
    t = _siblings(gauge, 20, group="api", prefix="api")
    _siblings(gauge, 20, prefix="local", tapestry=t)

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=10, groups={"api": 2}))

    # Assert
    assert result.succeeded
    assert gauge.group_peaks["api"] == 2
    assert gauge.peak <= 10


async def test_global_and_group_caps_hold_together() -> None:
    # Arrange: API calls wait for their group to fill; local knots wait for
    # the whole run to fill.  Either cap admitting too few times out.
    gauge = _Gauge(hold_global=4, hold_groups={"api": 2})
    t = _siblings(gauge, 12, group="api", prefix="api")
    _siblings(gauge, 12, prefix="local", tapestry=t)

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=4, groups={"api": 2}))

    # Assert
    assert result.succeeded
    assert gauge.peak == 4
    assert gauge.group_peaks["api"] == 2


async def test_a_group_the_limits_do_not_define_is_bounded_only_globally() -> None:
    # Arrange: design §11 Q5 -- naming an undefined group is not an error.
    gauge = _Gauge(hold_global=5)
    t = _siblings(gauge, 20, group="unlisted")

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=5, groups={"api": 1}))

    # Assert
    assert result.succeeded
    assert gauge.peak == 5


# ---------------------------------------------------- fairness and starvation


async def test_knots_in_a_group_start_in_readiness_order() -> None:
    # Arrange: one slot, eight grouped siblings.
    gauge = _Gauge()
    t = _siblings(gauge, 8, group="api", prefix="api")

    # Act
    result = await _run(t, ConcurrencyLimits(groups={"api": 1}))

    # Assert
    assert result.succeeded
    assert gauge.group_peaks["api"] == 1
    assert gauge.start_order == [f"api{i:03d}" for i in range(8)]


async def test_a_later_ready_knot_does_not_overtake_one_already_waiting() -> None:
    # Arrange: group cap 1.  `m_hold` takes the slot; `z_wait` queues behind
    # it.  `trigger` (ungrouped) then finishes and releases `a_late`, whose
    # id sorts first but which became ready later.  Once `m_hold` lets go,
    # `z_wait` must go before `a_late`.
    # `releaser`, trigger's other child, lets m_hold go; it became ready in
    # the same batch as a_late, so a_late is queued by the time it runs.  The
    # shed's topological order puts a_late (index 3) before z_wait (index 5),
    # so a queue ordered by topology alone would let a_late jump ahead.
    log: list[str] = []
    events = {"go": asyncio.Event()}
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _Waiter(
            x=p,
            log=log,
            events=events,
            wait_for="go",
            _config=KnotConfig(id="m_hold", concurrency_group="api"),
        )
        _Waiter(
            x=p, log=log, events=events, _config=KnotConfig(id="z_wait", concurrency_group="api")
        )
        trigger = _Waiter(x=p, log=log, events=events, _config=KnotConfig(id="trigger"))
        _Waiter(
            x=trigger,
            log=log,
            events=events,
            _config=KnotConfig(id="a_late", concurrency_group="api"),
        )
        _Waiter(x=trigger, log=log, events=events, announce="go", _config=KnotConfig(id="releaser"))

    # Act
    result = await _run(t, ConcurrencyLimits(groups={"api": 1}))

    # Assert
    assert result.succeeded
    starts = [e.removeprefix("start:") for e in log if e.startswith("start:")]
    grouped = [k for k in starts if k in {"m_hold", "z_wait", "a_late"}]
    assert grouped == ["m_hold", "z_wait", "a_late"]


async def test_a_slow_knot_holding_a_slot_does_not_starve_its_siblings() -> None:
    # Arrange: group cap 2.  `slow` holds one slot until every sibling has
    # finished, so they can only get through the other slot, one at a time.
    siblings = 10
    tally = {"finished": 0}
    done = asyncio.Event()
    log: list[str] = []
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _Waiter(
            x=p,
            log=log,
            events={"done": done},
            wait_for="done",
            _config=KnotConfig(id="a_slow", concurrency_group="api"),
        )
        for i in range(siblings):
            _Counter(
                x=p,
                tally=tally,
                done=done,
                expected=siblings,
                _config=KnotConfig(id=f"b{i:02d}", concurrency_group="api"),
            )

    # Act
    result = await _run(t, ConcurrencyLimits(groups={"api": 2}))

    # Assert
    assert result.succeeded
    assert tally["finished"] == siblings
    assert log == ["start:a_slow", "finish:a_slow"]


# ------------------------------------------------------------ slot release


async def test_every_knot_failing_under_a_cap_does_not_deadlock(spy_gates: list[_SpyGate]) -> None:
    # Arrange: 20 failing siblings, each with a child that is then skipped.
    log: list[str] = []
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        for i in range(20):
            s = _Waiter(x=p, log=log, events={}, fail=True, _config=KnotConfig(id=f"s{i:02d}"))
            _Waiter(x=s, log=log, events={}, _config=KnotConfig(id=f"c{i:02d}"))

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=2))

    # Assert
    assert not result.succeeded
    assert len(result.exceptions) == 20
    assert len(result.skipped) == 20
    assert [g.in_flight for g in spy_gates] == [0]


async def test_skipped_and_synthetic_failures_give_their_slot_back(
    spy_gates: list[_SpyGate],
) -> None:
    # Arrange: under a cap of one, a failed parent fans out to skipped and
    # REQUIRE_ALL_PARENTS children, then more work must still run.
    log: list[str] = []
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        bad = _Waiter(x=p, log=log, events={}, fail=True, _config=KnotConfig(id="bad"))
        for i in range(10):
            _Waiter(x=bad, log=log, events={}, _config=KnotConfig(id=f"skip{i}"))
            _Waiter(
                x=bad,
                log=log,
                events={},
                _config=KnotConfig(id=f"strict{i}", error_policy=ErrorPolicy.REQUIRE_ALL_PARENTS),
            )
        for i in range(5):
            _Waiter(x=p, log=log, events={}, _config=KnotConfig(id=f"ok{i}"))

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=1))

    # Assert
    assert sorted(result.skipped) == sorted(f"skip{i}" for i in range(10))
    assert {f"ok{i}" for i in range(5)} <= set(result.outputs)
    assert [g.in_flight for g in spy_gates] == [0]


async def test_a_knot_that_swallows_its_cancellation_gives_its_slot_back() -> None:
    # Arrange: CancelledError raised inside process() becomes an Err in
    # Knot.__call__ (PIR-849); the slot must still come back.
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _SelfCancelling(x=p, _config=KnotConfig(id="a_cancel"))
        for i in range(5):
            _Waiter(x=p, log=[], events={}, _config=KnotConfig(id=f"b{i}"))

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=1))

    # Assert
    assert [rec.knot_id for rec in result.exceptions] == ["a_cancel"]
    assert {f"b{i}" for i in range(5)} <= set(result.outputs)


class _SelfCancelling(Knot):
    async def process(self, **_inputs: Any) -> str:
        raise asyncio.CancelledError


class _CancellingDispatcher(Dispatcher):
    """Raises CancelledError out of dispatch for one knot, bypassing Knot.__call__."""

    def __init__(self, victim: str) -> None:
        self._victim = victim
        self._inner = LocalDispatcher()

    @property
    def name(self) -> str:
        return "CancellingDispatcher"

    async def dispatch(self, knot: Knot, inputs: Any) -> Result[Any]:
        if knot.knot_id == self._victim:
            raise asyncio.CancelledError
        return await self._inner.dispatch(knot, inputs)


async def test_a_cancelled_dispatch_does_not_leak_slots(spy_gates: list[_SpyGate]) -> None:
    # Arrange: the dispatch itself is cancelled, so no Knot.__call__ is there
    # to turn it into an Err.  The run aborts; every slot must come back.
    log: list[str] = []
    events = {"never": asyncio.Event()}
    with Tapestry(dispatcher=_CancellingDispatcher("victim")) as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _Waiter(x=p, log=log, events=events, wait_for="never", _config=KnotConfig(id="held"))
        _Waiter(x=p, log=log, events=events, _config=KnotConfig(id="victim"))
        for i in range(5):
            _Waiter(x=p, log=log, events=events, _config=KnotConfig(id=f"w{i}"))

    # Act / Assert
    with pytest.raises(asyncio.CancelledError):
        await _run(t, ConcurrencyLimits(max_in_flight=2))
    assert [g.in_flight for g in spy_gates] == [0]


async def test_cancelling_a_capped_run_releases_every_slot(spy_gates: list[_SpyGate]) -> None:
    # Arrange: two knots stuck in flight, more queued behind the cap.
    log: list[str] = []
    events = {"never": asyncio.Event(), "held1": asyncio.Event()}
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        _Waiter(x=p, log=log, events=events, wait_for="never", _config=KnotConfig(id="held0"))
        _Waiter(
            x=p,
            log=log,
            events=events,
            wait_for="never",
            announce="held1",
            _config=KnotConfig(id="held1"),
        )
        for i in range(5):
            _Waiter(x=p, log=log, events=events, _config=KnotConfig(id=f"queued{i}"))
    run = asyncio.create_task(t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=2))))
    await asyncio.wait_for(events["held1"].wait(), timeout=10)

    # Act
    run.cancel()

    # Assert
    with pytest.raises(asyncio.CancelledError):
        await run
    assert not any(e.startswith("start:queued") for e in log)
    assert [g.in_flight for g in spy_gates] == [0]


# ------------------------------------------------------------- precedence


async def test_the_tapestry_default_applies_when_the_request_has_none() -> None:
    # Arrange
    gauge = _Gauge(hold_global=1)
    t = _siblings(gauge, 10, tapestry=Tapestry(concurrency=ConcurrencyLimits(max_in_flight=1)))

    # Act
    result = await _run(t)

    # Assert
    assert result.succeeded
    assert gauge.peak == 1


async def test_the_request_limits_override_the_tapestry_default() -> None:
    # Arrange
    gauge = _Gauge(hold_global=4)
    t = _siblings(gauge, 10, tapestry=Tapestry(concurrency=ConcurrencyLimits(max_in_flight=1)))

    # Act
    result = await _run(t, ConcurrencyLimits(max_in_flight=4))

    # Assert
    assert result.succeeded
    assert gauge.peak == 4


async def test_empty_request_limits_lift_the_tapestry_default() -> None:
    # Arrange: an explicit ConcurrencyLimits() is "unbounded", not "unset".
    gauge = _Gauge(hold_global=10)
    t = _siblings(gauge, 10, tapestry=Tapestry(concurrency=ConcurrencyLimits(max_in_flight=1)))

    # Act
    result = await _run(t, ConcurrencyLimits())

    # Assert
    assert result.succeeded
    assert gauge.peak == 10


def test_tapestry_exposes_its_default_limits() -> None:
    # Arrange
    limits = ConcurrencyLimits(max_in_flight=3)

    # Act / Assert
    assert Tapestry(concurrency=limits).concurrency == limits
    assert Tapestry().concurrency is None


async def test_no_limits_anywhere_uses_the_unbounded_gate(
    monkeypatch: pytest.MonkeyPatch, spy_gates: list[_SpyGate]
) -> None:
    # Arrange
    built: list[UnboundedAdmissionGate] = []
    monkeypatch.setattr(
        "pirn.engine.engine.UnboundedAdmissionGate",
        functools.partial(_record_unbounded, built),
    )
    gauge = _Gauge()
    t = _siblings(gauge, 3)

    # Act
    result = await _run(t)

    # Assert
    assert result.succeeded
    assert len(built) == 1
    assert spy_gates == []


def _record_unbounded(built: list[UnboundedAdmissionGate]) -> UnboundedAdmissionGate:
    gate = UnboundedAdmissionGate()
    built.append(gate)
    return gate


# ------------------------------------------ records and hashes are unaffected


def _mixed_graph() -> Tapestry:
    """Grouped and ungrouped knots with successes, failures, skips and a join."""
    log: list[str] = []
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="p"))
        heads = [
            _Waiter(
                x=p,
                log=log,
                events={},
                fail=i == 2,
                _config=KnotConfig(id=f"s{i}", concurrency_group="api" if i % 2 else None),
            )
            for i in range(6)
        ]
        for i, head in enumerate(heads):
            _Waiter(
                x=head,
                log=log,
                events={},
                _config=KnotConfig(id=f"c{i}", concurrency_group="db" if i % 3 == 0 else None),
            )
        _Waiter(
            x=heads[3],
            y=heads[2],
            log=log,
            events={},
            _config=KnotConfig(id="join", error_policy=ErrorPolicy.REQUIRE_ALL_PARENTS),
        )
        _Waiter(
            x=heads[1],
            y=heads[2],
            log=log,
            events={},
            _config=KnotConfig(id="recv", error_policy=ErrorPolicy.RECEIVE_ERRORS),
        )
    return t


def _masked_input_hashes(row: KnotLineage, outcomes: dict[str, str]) -> list[tuple[str, str]]:
    parents = row.extra.get("parent_knot_ids", {})
    return sorted(
        (name, digest if outcomes.get(parents.get(name, "")) == "ok" else "<not ok>")
        for name, digest in row.parent_input_hashes.items()
    )


def _fingerprint(result: RunResult) -> dict[str, Any]:
    """Everything order- or hash-bearing in a run, minus per-run identifiers.

    The hash of an ``Err`` input covers its exception record's uuid, which is
    unique per run by design, so inputs from a failed parent are masked.
    """
    outcomes = {row.knot_id: row.outcome for row in result.lineage}
    return {
        "lineage": [
            (
                row.knot_id,
                row.outcome,
                row.output_hash,
                _masked_input_hashes(row, outcomes),
                row.knot_config_hash,
                row.config_values_hash,
                row.skip_reason,
            )
            for row in result.lineage
        ],
        "exceptions": [(rec.knot_id, rec.exc_type, rec.message) for rec in result.exceptions],
        "skipped": list(result.skipped),
        "outputs": list(result.outputs.items()),
    }


@pytest.mark.parametrize(
    "limits",
    [
        ConcurrencyLimits(max_in_flight=1),
        ConcurrencyLimits(max_in_flight=3),
        ConcurrencyLimits(groups={"api": 1}),
        ConcurrencyLimits(groups={"api": 1, "db": 1}),
        ConcurrencyLimits(max_in_flight=2, groups={"api": 1, "db": 2}),
    ],
    ids=["global1", "global3", "api1", "api1_db1", "global2_api1_db2"],
)
async def test_limits_do_not_change_record_order_or_hashes(limits: ConcurrencyLimits) -> None:
    # Arrange
    unbounded = _fingerprint(await _run(_mixed_graph()))

    # Act
    limited = _fingerprint(await _run(_mixed_graph(), limits))

    # Assert
    assert limited == unbounded
    assert [row[0] for row in limited["lineage"]][:1] == ["p"]


async def test_a_recording_made_without_groups_replays_with_groups() -> None:
    # Arrange: record a graph whose knots name no group ...
    with Tapestry() as recorded:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _Waiter(x=p, log=[], events={}, _config=KnotConfig(id="call0"))
        _Waiter(x=p, log=[], events={}, _config=KnotConfig(id="call1"))
    original = await recorded.run(RunRequest(parameters={"x": 5}))
    assert original.succeeded

    # ... then replay it against the same knots placed in a capped group.
    replay_log: list[str] = []
    with Tapestry(history=recorded.history, data_store=recorded.data_store) as grouped:
        p2 = Parameter("x", int, _config=KnotConfig(id="p"))
        for i in range(2):
            _Waiter(
                x=p2,
                log=replay_log,
                events={},
                _config=KnotConfig(id=f"call{i}", concurrency_group="api"),
            )
    session = await ReplaySession.from_history(history=recorded.history, run_id=original.run_id)

    # Act
    replayed = await asyncio.wait_for(
        grouped.run(
            RunRequest(parameters={"x": 5}, concurrency=ConcurrencyLimits(groups={"api": 1})),
            replay=session,
        ),
        timeout=30,
    )

    # Assert: served from the recording, not executed.
    assert replayed.succeeded
    assert replayed.outputs == original.outputs
    assert replay_log == []
    assert [r.knot_config_hash for r in replayed.lineage] == [
        r.knot_config_hash for r in original.lineage
    ]
