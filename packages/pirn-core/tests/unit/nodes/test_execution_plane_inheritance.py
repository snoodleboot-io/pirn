"""An inner run must execute under the enclosing run's execution plane.

`SubTapestry._run_inner` forwarded the outer history, emitters, data store and
transport into the inner tapestry, but not the outer *execution plane*: the
inner `Tapestry()` kept the `LocalDispatcher`, the unbounded admission gate,
the empty observer list and the default identity resolver it was constructed
with.  So a `ThreadDispatcher` pipeline dropped to the event loop inside every
`SubTapestry` body, an outer `max_in_flight` bounded nothing inside it, and an
adaptive controller attached at the top never heard an inner admission.  See
ADR agents-speaks-core WS0b (PIR-841 slice 3).

The gate is inherited *by identity*, so the assertions here are about one
shared budget: N containers x M inner leaves under an outer cap of K peak at
exactly K leaves in flight, whichever run they belong to.  Peaks are measured
with a gauge that holds each leaf inside its critical section until the
expected number of leaves is in there with it, so a cap that admits too few
times out and one that admits too many is caught by the peak assertion.
"""

from __future__ import annotations

import asyncio
import functools
import threading
import unittest
import warnings
from typing import TYPE_CHECKING, Any

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.concurrency.unused_concurrency_group_warning import UnusedConcurrencyGroupWarning
from pirn.core.execution_plane import ExecutionPlane
from pirn.core.identity.identity_resolver import IdentityResolver
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_context_vars import RunContextVars
from pirn.core.run_request import RunRequest
from pirn.engine.admission.admission_observer import AdmissionObserver
from pirn.engine.admission.limited_admission import LimitedAdmission
from pirn.engine.admission.unbounded_admission import UnboundedAdmission
from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.engine.admission.admission_event import AdmissionEvent
    from pirn.engine.dispatchers.dispatcher import Dispatcher


class _Gauge:
    """Counts leaves inside their critical section; each waits for company.

    A leaf leaves only once ``hold`` leaves are inside with it, or once every
    registered leaf has entered.  Works on one loop (``visit``) and across
    worker threads (``visit_blocking``).
    """

    def __init__(self, hold: int) -> None:
        self.hold = hold
        self.total = 0
        self.started = 0
        self.in_flight = 0
        self.peak = 0
        self.threads: set[str] = set()
        self._lock = threading.Lock()
        self._thread_cond = threading.Condition(self._lock)
        self._async_cond: asyncio.Condition | None = None

    def register(self) -> None:
        self.total += 1

    def _enter(self) -> None:
        self.started += 1
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        self.threads.add(threading.current_thread().name)

    def _may_leave(self) -> bool:
        return self.in_flight >= self.hold or self.started == self.total

    async def visit(self) -> None:
        if self._async_cond is None:
            self._async_cond = asyncio.Condition()
        cond = self._async_cond
        async with cond:
            with self._lock:
                self._enter()
            cond.notify_all()
            await cond.wait_for(self._may_leave)
        async with cond:
            with self._lock:
                self.in_flight -= 1
            cond.notify_all()

    def visit_blocking(self) -> None:
        with self._thread_cond:
            self._enter()
            self._thread_cond.notify_all()
            left = self._thread_cond.wait_for(functools.partial(self._may_leave), timeout=20)
            self.in_flight -= 1
            self._thread_cond.notify_all()
        if not left:
            raise TimeoutError("a leaf was never joined by the leaves it waited for")


class _Leaf(Knot):
    """A leaf that passes through the gauge and returns its id."""

    def __init__(self, *, gauge: _Gauge, blocking: bool = False, **kwargs: Any) -> None:
        self._gauge = gauge
        self._blocking = blocking
        super().__init__(**kwargs)
        gauge.register()

    async def process(self, **_: Any) -> str:
        if self._blocking:
            self._gauge.visit_blocking()
        else:
            await self._gauge.visit()
        return self.knot_id


class _Sub(SubTapestry):
    """A container over ``width`` gauged inner leaves, with optional overrides."""

    def __init__(
        self,
        *,
        gauge: _Gauge,
        width: int,
        blocking: bool = False,
        group: str | None = None,
        inner_limits: ConcurrencyLimits | None = None,
        inner_dispatcher: Dispatcher | None = None,
        **kwargs: Any,
    ) -> None:
        self._gauge = gauge
        self._width = width
        self._blocking = blocking
        self._group = group
        self._inner_limits = inner_limits
        self._inner_dispatcher_choice = inner_dispatcher
        super().__init__(**kwargs)

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        return self._inner_limits

    def _inner_dispatcher(self) -> Dispatcher | None:
        return self._inner_dispatcher_choice

    async def process(self, **_: Any) -> Knot:
        leaves = [
            _Leaf(
                gauge=self._gauge,
                blocking=self._blocking,
                _config=KnotConfig(id=f"{self.knot_id}-leaf{i}", concurrency_group=self._group),
            )
            for i in range(self._width)
        ]
        return _Join(
            **{f"p{i}": leaf for i, leaf in enumerate(leaves)},
            _config=KnotConfig(id=f"{self.knot_id}-join"),
        )


class _Join(Knot):
    async def process(self, **inputs: Any) -> int:
        return len(inputs)


class _PeakCounter:
    """Tracks concurrent occupancy by simple entry/exit counting.

    Unlike ``_Gauge``, a visitor never waits for company: it just records how
    many are in at once and leaves whenever it is done.  Good enough for
    peak-concurrency assertions because admission itself is what creates the
    overlap -- every knot the gate admits in one pass of the engine's ready
    loop starts before any of them awaits its own sleep, so knots genuinely
    running at the same time really do overlap in wall-clock time.
    """

    def __init__(self) -> None:
        self.in_flight = 0
        self.peak = 0
        self._lock = asyncio.Lock()

    async def enter(self) -> None:
        async with self._lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)

    async def leave(self) -> None:
        async with self._lock:
            self.in_flight -= 1


class _SleepWorker(Knot):
    """Occupies every counter in *counters* for a fixed duration."""

    def __init__(self, *, counters: list[_PeakCounter], seconds: float, **kwargs: Any) -> None:
        self._counters = counters
        self._seconds = seconds
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> str:
        for counter in self._counters:
            await counter.enter()
        try:
            await asyncio.sleep(self._seconds)
        finally:
            for counter in self._counters:
                await counter.leave()
        return self.knot_id


class _ChainedSub(SubTapestry):
    """A container declaring a *bounded* inner budget of its own."""

    def __init__(
        self,
        *,
        total: _PeakCounter,
        inner: _PeakCounter,
        width: int,
        inner_max_in_flight: int,
        seconds: float,
        **kwargs: Any,
    ) -> None:
        self._total = total
        self._inner = inner
        self._width = width
        self._inner_max_in_flight = inner_max_in_flight
        self._seconds = seconds
        super().__init__(**kwargs)

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        return ConcurrencyLimits(max_in_flight=self._inner_max_in_flight)

    async def process(self, **_: Any) -> Knot:
        leaves = [
            _SleepWorker(
                counters=[self._total, self._inner],
                seconds=self._seconds,
                _config=KnotConfig(id=f"{self.knot_id}-leaf{i}"),
            )
            for i in range(self._width)
        ]
        return _Join(
            **{f"p{i}": leaf for i, leaf in enumerate(leaves)},
            _config=KnotConfig(id=f"{self.knot_id}-join"),
        )


class _PlaneProbe(Knot):
    """Records the plane in force where it runs."""

    def __init__(self, *, seen: list[ExecutionPlane | None], **kwargs: Any) -> None:
        self._seen = seen
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        self._seen.append(ExecutionPlane.current())
        return 1


class _ProbeSub(SubTapestry):
    def __init__(self, *, seen: list[ExecutionPlane | None], **kwargs: Any) -> None:
        self._seen = seen
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Knot:
        return _PlaneProbe(seen=self._seen, _config=KnotConfig(id="probe"))


def _containers(
    gauge: _Gauge,
    *,
    containers: int,
    width: int,
    tapestry: Tapestry,
    blocking: bool = False,
    group: str | None = None,
) -> Tapestry:
    with tapestry:
        for i in range(containers):
            _Sub(
                gauge=gauge,
                width=width,
                blocking=blocking,
                group=group,
                _config=KnotConfig(id=f"sub{i}"),
            )
    return tapestry


class TestInnerLeavesShareTheOuterGate(unittest.IsolatedAsyncioTestCase):
    async def test_four_containers_of_four_leaves_peak_at_the_outer_cap(self) -> None:
        # Arrange: 16 leaves across 4 inner runs; without a shared gate the
        # peak is 16 (each inner run unbounded), with one it is exactly 2.
        gauge = _Gauge(hold=2)
        t = _containers(gauge, containers=4, width=4, tapestry=Tapestry())

        # Act
        result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=2)))

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 2)
        self.assertEqual(gauge.started, 16)

    async def test_the_tapestry_default_limits_reach_inner_leaves_too(self) -> None:
        gauge = _Gauge(hold=3)
        t = _containers(
            gauge,
            containers=3,
            width=3,
            tapestry=Tapestry(concurrency=ConcurrencyLimits(max_in_flight=3)),
        )
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 3)

    async def test_a_group_cap_bounds_the_group_across_every_inner_run(self) -> None:
        # Arrange: every inner leaf is in "api"; the outer limits cap it at 1.
        gauge = _Gauge(hold=1)
        t = _containers(gauge, containers=3, width=2, tapestry=Tapestry(), group="api")

        # Act: no inner run should warn that "api" is unused -- the limits
        # were declared for the whole tree.
        with warnings.catch_warnings():
            warnings.simplefilter("error", UnusedConcurrencyGroupWarning)
            result = await t.run(RunRequest(concurrency=ConcurrencyLimits(groups={"api": 1})))

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 1)
        self.assertEqual(gauge.started, 6)

    async def test_a_container_under_a_cap_of_one_does_not_deadlock(self) -> None:
        # Arrange: the container is slot-free, so the single slot goes to its
        # leaves one at a time rather than being held by the container itself.
        gauge = _Gauge(hold=1)
        t = _containers(gauge, containers=2, width=3, tapestry=Tapestry())

        # Act
        result = await asyncio.wait_for(
            t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1))), timeout=20
        )

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 1)
        self.assertEqual(gauge.started, 6)

    async def test_the_inner_plane_carries_the_very_same_gate(self) -> None:
        seen: list[ExecutionPlane | None] = []
        with Tapestry(concurrency=ConcurrencyLimits(max_in_flight=4)) as t:
            _ProbeSub(seen=seen, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(len(seen), 1)
        inner_plane = seen[0]
        assert inner_plane is not None
        self.assertIsInstance(inner_plane.gate, LimitedAdmission)
        self.assertEqual(inner_plane.limits, ConcurrencyLimits(max_in_flight=4))

    async def test_a_container_may_not_join_a_concurrency_group(self) -> None:
        gauge = _Gauge(hold=1)
        with self.assertRaises(ValueError) as caught, Tapestry():
            _Sub(gauge=gauge, width=1, _config=KnotConfig(id="sub", concurrency_group="api"))
        self.assertIn("api", str(caught.exception))


class TestInnerRunsMayNameTheirOwnLimits(unittest.IsolatedAsyncioTestCase):
    async def test_a_container_hook_gives_the_inner_run_its_own_gate(self) -> None:
        # Arrange: outer cap 1, but the container declares an unbounded inner
        # budget of its own, so its four leaves run together.
        gauge = _Gauge(hold=4)
        with Tapestry() as t:
            _Sub(
                gauge=gauge,
                width=4,
                inner_limits=ConcurrencyLimits(),
                _config=KnotConfig(id="sub"),
            )

        # Act
        result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1)))

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 4)

    async def test_a_tighter_inner_limit_applies_inside_only(self) -> None:
        gauge = _Gauge(hold=1)
        with Tapestry() as t:
            _Sub(
                gauge=gauge,
                width=3,
                inner_limits=ConcurrencyLimits(max_in_flight=1),
                _config=KnotConfig(id="sub"),
            )
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 1)

    async def test_run_inner_keyword_overrides_win(self) -> None:
        # The explicit ``_run_inner(concurrency=...)`` keyword still wins over
        # the tapestry-level default (``_Sub`` names none here), but since
        # PIR-870 a *bounded* override is chained under the outer cap rather
        # than replacing it, so the peak is the tighter of the two (1, not
        # the inner override's 2) -- the outer run declared 1 and nothing
        # opted out of it.
        class _Explicit(_Sub):
            async def _run_inner(self, tapestry: Tapestry, **kwargs: Any) -> RunResult:
                return await super()._run_inner(
                    tapestry, concurrency=ConcurrencyLimits(max_in_flight=2), **kwargs
                )

        gauge = _Gauge(hold=1)
        with Tapestry() as t:
            _Explicit(gauge=gauge, width=4, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1)))
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 1)

    async def test_a_bounded_inner_gate_is_chained_under_the_outer_cap(self) -> None:
        # Arrange (PIR-870): outer cap 3, inner cap 2.  Three outer-level
        # workers occupy the whole outer budget first; the container's four
        # inner leaves only get admitted as outer slots free, never more
        # than 2 at once, and the two budgets combined never exceed 3 in
        # flight.  Before this fix the inner gate was unrelated to the
        # outer one, so the inner leaves' own cap of 2 applied *in addition
        # to* the three outer workers -- a combined peak of 5.
        total = _PeakCounter()
        inner = _PeakCounter()
        with Tapestry() as t:
            for i in range(3):
                _SleepWorker(counters=[total], seconds=0.15, _config=KnotConfig(id=f"outer{i}"))
            _ChainedSub(
                total=total,
                inner=inner,
                width=4,
                inner_max_in_flight=2,
                seconds=0.15,
                _config=KnotConfig(id="sub"),
            )

        # Act
        result = await asyncio.wait_for(
            t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=3))), timeout=20
        )

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(inner.peak, 2)
        self.assertLessEqual(total.peak, 3)

    async def test_an_unbounded_inner_gate_still_opts_out_of_the_outer_cap(self) -> None:
        # An explicitly *unbounded* ConcurrencyLimits() is the documented
        # escape hatch (PIR-870 does not change it): its gate stays
        # unchained, so it is not bounded by the outer cap at all.
        gauge = _Gauge(hold=4)
        with Tapestry() as t:
            _Sub(
                gauge=gauge,
                width=4,
                inner_limits=ConcurrencyLimits(),
                _config=KnotConfig(id="sub"),
            )
        result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=2)))
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 4)


class TestInnerRunsInheritTheDispatcher(unittest.IsolatedAsyncioTestCase):
    async def test_a_container_does_not_occupy_the_pool_its_own_leaves_need(self) -> None:
        # Arrange (PIR-870): a pool of exactly one worker.  Before this fix
        # the container itself consumed that one worker for the life of its
        # inner run, and the inner run's leaves -- dispatched on the very
        # same pool -- could never get a worker to make progress: deadlock.
        # The container must run on the event loop instead, leaving the
        # pool's one worker free for its leaves.
        dispatcher = ThreadDispatcher(max_workers=1)
        gauge = _Gauge(hold=1)
        with Tapestry(dispatcher=dispatcher) as t:
            _Sub(gauge=gauge, width=2, blocking=True, _config=KnotConfig(id="sub"))

        # Act
        try:
            result = await asyncio.wait_for(t.run(RunRequest()), timeout=10)
        finally:
            dispatcher.shutdown(wait=False)

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.started, 2)

    async def test_inner_leaves_run_on_the_outer_thread_dispatcher(self) -> None:
        # Arrange
        dispatcher = ThreadDispatcher(max_workers=8)
        gauge = _Gauge(hold=1)
        history = InMemoryHistory()
        with Tapestry(dispatcher=dispatcher, history=history) as t:
            _Sub(gauge=gauge, width=2, blocking=True, _config=KnotConfig(id="sub"))

        # Act
        try:
            result = await t.run(RunRequest())
        finally:
            dispatcher.shutdown(wait=False)

        # Assert: the leaves ran on pool threads, and their lineage says so.
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertTrue(
            all(name.startswith("pirn-thread") for name in gauge.threads), gauge.threads
        )
        (inner,) = await history.children_of(result.run_id)
        self.assertEqual({row.dispatcher for row in inner.lineage}, {"ThreadDispatcher"})

    async def test_a_shared_cap_holds_across_worker_thread_loops(self) -> None:
        # Arrange: the inner runs execute on worker threads with loops of
        # their own, all admitting through the one outer gate.  A gate that
        # is not thread-safe hangs or over-admits here.
        dispatcher = ThreadDispatcher(max_workers=16)
        gauge = _Gauge(hold=2)
        t = _containers(
            gauge,
            containers=3,
            width=3,
            blocking=True,
            tapestry=Tapestry(
                dispatcher=dispatcher, concurrency=ConcurrencyLimits(max_in_flight=2)
            ),
        )

        # Act
        try:
            result = await asyncio.wait_for(t.run(RunRequest()), timeout=30)
        finally:
            dispatcher.shutdown(wait=False)

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 2)
        self.assertEqual(gauge.started, 9)

    async def test_a_container_hook_keeps_its_own_dispatcher(self) -> None:
        # Arrange: the container itself still runs on a pool thread (the
        # outer dispatcher's business); its *inner leaves* must not.
        dispatcher = ThreadDispatcher(max_workers=4)
        gauge = _Gauge(hold=1)
        history = InMemoryHistory()
        with Tapestry(dispatcher=dispatcher, history=history) as t:
            _Sub(
                gauge=gauge,
                width=2,
                inner_dispatcher=LocalDispatcher(),
                _config=KnotConfig(id="sub"),
            )
        try:
            result = await t.run(RunRequest())
        finally:
            dispatcher.shutdown(wait=False)
        self.assertTrue(result.succeeded, result.exceptions)
        (inner,) = await history.children_of(result.run_id)
        self.assertEqual(inner.dispatcher, "LocalDispatcher")
        self.assertEqual({row.dispatcher for row in inner.lineage}, {"LocalDispatcher"})

    async def test_an_inner_tapestry_built_with_its_own_dispatcher_keeps_it(self) -> None:
        # Arrange: the throwaway inner tapestry SubTapestry opens never names
        # a dispatcher, so exercise the explicit case through a
        # LoopSubTapestry iteration -- the one place user code builds the
        # inner tapestry itself.
        dispatcher = ThreadDispatcher(max_workers=4)
        gauge = _Gauge(hold=1)
        history = InMemoryHistory()
        with Tapestry(dispatcher=dispatcher, history=history) as t:
            _OneTurnLoop(
                gauge=gauge,
                iteration_dispatcher=LocalDispatcher(),
                state=_Seed(_config=KnotConfig(id="seed")),
                _config=KnotConfig(id="loop"),
            )
        try:
            result = await t.run(RunRequest())
        finally:
            dispatcher.shutdown(wait=False)
        self.assertTrue(result.succeeded, result.exceptions)
        (leaf_row,) = await history.query_lineage_by_knot_id("turn0-leaf0")
        self.assertEqual(leaf_row.dispatcher, "LocalDispatcher")


class _Seed(Source):
    async def process(self, **_: Any) -> int:
        return 0


class _OneTurnLoop(LoopSubTapestry[int]):
    """Runs ``turns`` iterations of ``width`` gauged leaves each."""

    def __init__(
        self,
        *,
        gauge: _Gauge,
        turns: int = 1,
        width: int = 1,
        iteration_dispatcher: Dispatcher | None = None,
        **kwargs: Any,
    ) -> None:
        self._gauge = gauge
        self._turns = turns
        self._width = width
        self._iteration_dispatcher = iteration_dispatcher
        super().__init__(**kwargs)

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= self._turns:
            return None
        tapestry = Tapestry(dispatcher=self._iteration_dispatcher)
        with tapestry:
            for i in range(self._width):
                _Leaf(gauge=self._gauge, _config=KnotConfig(id=f"turn{state}-leaf{i}"))
        return tapestry, state + 1

    def fold(self, state: int, result: RunResult) -> int:
        return state


class TestLoopIterationsShareTheOuterGate(unittest.IsolatedAsyncioTestCase):
    async def test_every_turn_s_leaves_are_bounded_by_the_outer_cap(self) -> None:
        gauge = _Gauge(hold=2)
        with Tapestry() as t:
            _OneTurnLoop(
                gauge=gauge,
                turns=3,
                width=4,
                state=_Seed(_config=KnotConfig(id="seed")),
                _config=KnotConfig(id="loop"),
            )
        result = await asyncio.wait_for(
            t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=2))), timeout=20
        )
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(gauge.peak, 2)
        self.assertEqual(gauge.started, 12)


class _RecordingObserver(AdmissionObserver):
    def __init__(self) -> None:
        self.admits: list[tuple[str, str]] = []

    def on_admit(self, event: AdmissionEvent) -> None:
        self.admits.append((event.run_id, event.knot_id))


class TestInnerRunsReportToTheOuterObservers(unittest.IsolatedAsyncioTestCase):
    async def test_an_outer_observer_hears_inner_admissions(self) -> None:
        observer = _RecordingObserver()
        gauge = _Gauge(hold=1)
        with Tapestry(admission_observers=[observer]) as t:
            _Sub(gauge=gauge, width=2, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1)))
        self.assertTrue(result.succeeded, result.exceptions)
        admitted = {knot_id for _, knot_id in observer.admits}
        self.assertIn("sub-leaf0", admitted)
        self.assertIn("sub-leaf1", admitted)
        self.assertGreater(len({run_id for run_id, _ in observer.admits}), 1)

    async def test_the_same_observer_at_both_levels_hears_each_admission_once(self) -> None:
        observer = _RecordingObserver()

        class _Observed(_Sub):
            def _inner_admission_observers(self) -> list[AdmissionObserver] | None:
                return [observer]

        gauge = _Gauge(hold=1)
        with Tapestry(admission_observers=[observer]) as t:
            _Observed(gauge=gauge, width=2, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1)))
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(len(observer.admits), len(set(observer.admits)))


class _Fixed(IdentityResolver):
    def __init__(self, actor: str) -> None:
        self._actor = actor

    def resolve(self) -> str | None:
        return self._actor


class TestInnerRunsInheritTheIdentityResolver(unittest.IsolatedAsyncioTestCase):
    async def test_the_inner_run_is_attributed_to_the_outer_actor(self) -> None:
        history = InMemoryHistory()
        seen: list[ExecutionPlane | None] = []
        with Tapestry(history=history, identity_resolver=_Fixed("alice")) as t:
            _ProbeSub(seen=seen, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(result.actor, "alice")
        (inner,) = await history.children_of(result.run_id)
        self.assertEqual(inner.actor, "alice")


class TestNestingDepthStillReachesInnerRuns(unittest.IsolatedAsyncioTestCase):
    async def test_a_depth_cap_set_at_the_top_refuses_the_innermost_run(self) -> None:
        seen: list[ExecutionPlane | None] = []

        class _Outer(SubTapestry):
            async def process(self, **_: Any) -> Knot:
                return _ProbeSub(seen=seen, _config=KnotConfig(id="mid"))

        with Tapestry(max_nesting_depth=1) as t:
            _Outer(_config=KnotConfig(id="outer"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
        self.assertEqual(seen, [])


class _Counting(Knot):
    def __init__(self, *, calls: list[str], **kwargs: Any) -> None:
        self._calls = calls
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        self._calls.append(self.knot_id)
        return 7


class _CountingSub(SubTapestry):
    def __init__(self, *, calls: list[str], **kwargs: Any) -> None:
        self._calls = calls
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Knot:
        return _Counting(calls=self._calls, _config=KnotConfig(id="inner"))


class TestInnerRunsInheritReplayPosture(unittest.IsolatedAsyncioTestCase):
    """An inner run started under an outer replay is served from its own recording.

    The outer session indexes the outer run's knots; the container's recorded
    row names the inner run (``extra["inner_run_id"]``), and that is what an
    inner run started under replay posture is served from.
    """

    async def _record(self) -> tuple[RunResult, InMemoryHistory, InMemoryDataStore, list[str]]:
        calls: list[str] = []
        history = InMemoryHistory()
        store = InMemoryDataStore()
        with Tapestry(history=history, data_store=store) as t:
            _CountingSub(calls=calls, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(calls, ["inner"])
        return result, history, store, calls

    @staticmethod
    def _plane(replay: ReplaySession | None) -> ExecutionPlane:
        return ExecutionPlane(
            dispatcher=LocalDispatcher(),
            gate=UnboundedAdmission(),
            limits=None,
            admission_observers=(),
            replay=replay,
            identity_resolver=_Fixed("replayer"),
        )

    async def test_the_inner_run_is_served_from_the_recorded_inner_run(self) -> None:
        # Arrange: a recorded outer run, and an inner tapestry identical to the
        # one the container built, started as if from inside an outer replay.
        outer, history, store, calls = await self._record()
        outer_session = ReplaySession(source_run=outer)
        recorded_inner_run_id = next(r for r in outer.lineage if r.knot_id == "sub").extra[
            "inner_run_id"
        ]
        with Tapestry(history=history, data_store=store) as inner:
            _Counting(calls=calls, _config=KnotConfig(id="inner"))

        # Act
        token_plane = RunContextVars.execution_plane.set(self._plane(outer_session))
        token_run = RunContextVars.run_id.set(outer.run_id)
        try:
            replayed = await inner.run(RunRequest(), _parent_knot_id="sub")
        finally:
            RunContextVars.run_id.reset(token_run)
            RunContextVars.execution_plane.reset(token_plane)

        # Assert: served, not executed.
        self.assertTrue(replayed.succeeded, replayed.exceptions)
        self.assertEqual(calls, ["inner"])
        self.assertEqual(replayed.outputs["inner"], 7)
        (row,) = replayed.lineage
        self.assertEqual(row.extra.get("replayed_from_run_id"), recorded_inner_run_id)

    async def test_a_container_without_a_recorded_row_runs_its_inner_pipeline_live(self) -> None:
        outer, history, store, calls = await self._record()
        outer_session = ReplaySession(source_run=outer)
        with Tapestry(history=history, data_store=store) as inner:
            _Counting(calls=calls, _config=KnotConfig(id="inner"))

        token_plane = RunContextVars.execution_plane.set(self._plane(outer_session))
        token_run = RunContextVars.run_id.set(outer.run_id)
        try:
            live = await inner.run(RunRequest(), _parent_knot_id="not-recorded")
        finally:
            RunContextVars.run_id.reset(token_run)
            RunContextVars.execution_plane.reset(token_plane)

        self.assertTrue(live.succeeded, live.exceptions)
        self.assertEqual(calls, ["inner", "inner"])
        (row,) = live.lineage
        self.assertNotIn("replayed_from_run_id", row.extra)

    async def test_an_explicit_replay_argument_wins_over_the_inherited_posture(self) -> None:
        outer, history, store, calls = await self._record()
        (recorded_inner,) = await history.children_of(outer.run_id)
        own_session = ReplaySession(source_run=recorded_inner)
        with Tapestry(history=history, data_store=store) as inner:
            _Counting(calls=calls, _config=KnotConfig(id="inner"))

        token_plane = RunContextVars.execution_plane.set(self._plane(None))
        token_run = RunContextVars.run_id.set(outer.run_id)
        try:
            replayed = await inner.run(RunRequest(), replay=own_session, _parent_knot_id="sub")
        finally:
            RunContextVars.run_id.reset(token_run)
            RunContextVars.execution_plane.reset(token_plane)

        self.assertTrue(replayed.succeeded, replayed.exceptions)
        self.assertEqual(calls, ["inner"])
