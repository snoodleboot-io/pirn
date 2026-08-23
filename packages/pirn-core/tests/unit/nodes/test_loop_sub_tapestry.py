"""Unit tests for LoopSubTapestry."""

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class _InitSource(Source):
    def __init__(self, *, init_state: Any, **kwargs: Any) -> None:
        self._init = init_state
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._init


class _CounterLoop(LoopSubTapestry[int]):
    """Counts up to a target by incrementing state each iteration."""

    def __init__(self, *, target: int, **kwargs: Any) -> None:
        self._target = target
        super().__init__(**kwargs)

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= self._target:
            return None

        class _IncrSource(Source):
            def __init__(cls_self, *, val: int, **kw: Any) -> None:
                cls_self._val = val
                super().__init__(**kw)

            async def process(self, **_: Any) -> int:
                return self._val + 1

        t = Tapestry()
        with t:
            _IncrSource(val=state, _config=KnotConfig(id="incr"))
        return t, state + 1

    def fold(self, state: int, result: RunResult) -> int:
        return result.outputs["incr"]


class TestLoopSubTapestryConstruction(unittest.TestCase):
    def test_constructs_as_sub_tapestry(self) -> None:
        with Tapestry():
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            loop = _CounterLoop(target=3, state=src, _config=KnotConfig(id="loop"))
        self.assertIsNotNone(loop)

    def test_step_id_default(self) -> None:
        loop = _CounterLoop.__new__(_CounterLoop)
        loop._target = 5
        self.assertEqual(loop.step_id(0, 1), "step_1")
        self.assertEqual(loop.step_id(0, 42), "step_42")


class TestLoopSubTapestryProcess(unittest.IsolatedAsyncioTestCase):
    async def test_loop_runs_to_completion(self) -> None:
        with Tapestry() as t:
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            _CounterLoop(target=3, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["loop"], 3)

    async def test_loop_with_zero_iterations(self) -> None:
        """When step returns None immediately, loop returns initial state."""
        with Tapestry() as t:
            src = _InitSource(init_state=5, _config=KnotConfig(id="init"))
            _CounterLoop(target=0, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["loop"], 5)


class TestLoopSubTapestryDepth(unittest.IsolatedAsyncioTestCase):
    """A long loop must not die on CPython's recursion limit.

    Each iteration adds one parent-chain level, and the engine validates the
    graph on every run with a DFS that used to recurse per level. Runs
    succeeded at 900 iterations and failed from ~984 upward with a
    RecursionError recorded against the loop knot. PIR-766 made that walk
    iterative; this pins the result well past the old ceiling.

    This is PIR-763's step 3 ("a regression test at a few thousand
    iterations"), discharged here rather than in that ticket.
    """

    # ~12s on an idle box, but iteration cost is quadratic in chain length and
    # the whole test stretches with machine load — measured at 73-80s under load
    # average 54, which overruns the suite's `--timeout=60` and reddens a gate
    # for reasons that have nothing to do with the code (PIR-810). An explicit
    # timeout keeps the coverage instead of trading it away for a marker that
    # would stop running the test at all.
    @pytest.mark.timeout(300)
    async def test_runs_far_past_the_old_recursion_ceiling(self) -> None:
        # Comfortably past the measured ~984 ceiling. Iteration cost here is
        # quadratic in the chain length, so a larger target buys no extra
        # confidence and costs real wall time in every CI run; the unbounded
        # case is covered directly and cheaply by TestCycleDetectorDepth at
        # 5000 nodes.
        target = 1200
        with Tapestry() as t:
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            _CounterLoop(target=target, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, [e.exc_type for e in result.exceptions])
        self.assertEqual(result.outputs["loop"], target)


class TestLoopSubTapestryHistory(unittest.IsolatedAsyncioTestCase):
    """Loop iterations must be recorded on the default backend.

    `_IterationChainKnot` used to inject the outer history only when it was
    *not* an InMemoryHistory. The intent was sound — an open-ended
    conversational loop records one child run per turn and an ephemeral store
    cannot absorb that — but InMemoryHistory is the default backend
    (`tapestry.py`), so out of the box a loop's iterations were recorded
    nowhere at all.

    The growth guard now lives on the store as a declared `retention`
    capability, so recording is bounded rather than absent. See PIR-765.
    """

    async def test_iterations_are_recorded_against_the_default_backend(self) -> None:
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory

        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            _CounterLoop(target=3, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["loop"], 3)

        # The loop's own inner run, then one child run per iteration beneath it.
        loop_runs = await history.children_of(result.run_id)
        self.assertEqual([r.parent_knot_id for r in loop_runs], ["loop"])
        iterations = await history.children_of(loop_runs[0].run_id)
        self.assertEqual([r.parent_knot_id for r in iterations], ["step_1", "step_2", "step_3"])

    async def test_per_iteration_lineage_is_queryable(self) -> None:
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory

        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            _CounterLoop(target=3, state=src, _config=KnotConfig(id="loop"))
        await t.run(RunRequest())
        self.assertEqual(len(await history.query_lineage_by_knot_id("incr")), 3)


class _RecordingLoop(LoopSubTapestry[int]):
    """Records what ``fold`` is handed on each iteration.

    ``step`` advances by 100 and ``fold`` by 1, so the two are distinguishable
    in the recorded sequence: a run that folds against ``step``'s returned state
    and one that folds against the previous ``fold`` output produce different
    numbers, not merely different orderings.
    """

    def __init__(self, *, limit: int, **kwargs: Any) -> None:
        self._limit = limit
        self.folded_states: list[int] = []
        self.stepped_states: list[int] = []
        super().__init__(**kwargs)

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if len(self.stepped_states) >= self._limit:
            return None
        self.stepped_states.append(state)
        emitted = state + 100

        class _Emit(Source):
            async def process(self, **_: Any) -> int:
                return emitted

        t = Tapestry()
        with t:
            _Emit(_config=KnotConfig(id="emit"))
        return t, emitted

    def fold(self, state: int, result: RunResult) -> int:
        self.folded_states.append(state)
        return state + 1


class TestLoopSubTapestryFoldStateContract(unittest.IsolatedAsyncioTestCase):
    """Characterization suite for the state-threading contract (PIR-754).

    PIR-754 fixed a divergence between iteration 1 and iterations 2+: the first
    passed ``step``'s returned state to ``fold``, later ones re-used the
    *previous fold's output* because ``state=self`` was doing double duty as
    both the value and the sequencing edge. It shipped with **zero** tests.

    This is the evidence base any port onto ``LoopSubTapestry`` depends on, so
    it lives in core beside the node rather than in a consumer package.
    The existing ``_CounterLoop.fold`` above never reads ``state``, which is
    why reverting the fix reddens nothing without these.
    """

    async def _run(self, limit: int) -> _RecordingLoop:
        with Tapestry() as t:
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            loop = _RecordingLoop(limit=limit, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, [e.exc_type for e in result.exceptions])
        return loop

    async def test_fold_receives_the_state_step_returned(self) -> None:
        """Not the previous fold's output — the distinction PIR-754 turned on.

        step: s -> s+100, fold: s -> s+1, initial 0.
          folding against step's return  => 100, 201, 302
          folding against fold's output  => 100, 101, 102   (the pre-fix bug)
        """
        loop = await self._run(3)
        self.assertEqual(loop.folded_states, [100, 201, 302])

    async def test_step_receives_the_state_fold_returned(self) -> None:
        """The other half of the round trip."""
        loop = await self._run(3)
        self.assertEqual(loop.stepped_states, [0, 101, 202])

    async def test_iterations_are_sequential(self) -> None:
        """Ordering survives `state` no longer being the sequencing edge.

        PIR-754 split the two jobs apart, adding an explicit
        ``_previous_iteration`` parent. If that edge were dropped the recorded
        sequences could interleave.
        """
        loop = await self._run(4)
        self.assertEqual(loop.stepped_states, sorted(loop.stepped_states))
        self.assertEqual(loop.folded_states, sorted(loop.folded_states))
        self.assertEqual(len(loop.stepped_states), 4)

    async def test_step_returning_none_terminates(self) -> None:
        loop = await self._run(1)
        self.assertEqual(loop.stepped_states, [0])
        self.assertEqual(loop.folded_states, [100])

    async def test_final_output_is_the_last_fold(self) -> None:
        with Tapestry() as t:
            src = _InitSource(init_state=0, _config=KnotConfig(id="init"))
            _RecordingLoop(limit=3, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["loop"], 303)


class _RetryLoop(LoopSubTapestry[dict]):
    """Retry-until-success — the shape that was inexpressible before PIR-772.

    The attempt counter is a list on the loop instance. Not a class attribute —
    each iteration builds a fresh source class, so that would reset every time.
    Not an ``int`` either: ``Knot`` freezes the instance, so rebinding an
    attribute from inside ``process`` raises. Appending to a list mutates
    without a ``setattr``.
    """

    _tolerate_iteration_failures: ClassVar[bool] = True

    def __init__(self, *, fail_times: int, max_attempts: int, **kwargs: Any) -> None:
        self._fail_times = fail_times
        self._max_attempts = max_attempts
        self._attempts: list[int] = []
        self.folded: list[bool] = []
        super().__init__(**kwargs)

    def step(self, state: dict) -> tuple[Tapestry, dict] | None:
        if state.get("done") or state.get("attempts", 0) >= self._max_attempts:
            return None
        loop = self

        class _Attempt(Source):
            async def process(self, **_: Any) -> str:
                loop._attempts.append(1)
                if len(loop._attempts) <= loop._fail_times:
                    raise RuntimeError(f"attempt {len(loop._attempts)} failed")
                return "ok"

        t = Tapestry()
        with t:
            _Attempt(_config=KnotConfig(id="attempt"))
        return t, {**state, "attempts": state.get("attempts", 0) + 1}

    def fold(self, state: dict, result: RunResult) -> dict:
        self.folded.append(result.succeeded)
        if result.succeeded:
            return {**state, "done": True, "value": result.outputs["attempt"]}
        return state


class TestLoopSubTapestryIterationFailure(unittest.IsolatedAsyncioTestCase):
    """A failed iteration should be survivable — but only on request.

    Before PIR-772 any failed iteration raised SubTapestryError and killed the
    whole loop, so `fold` never saw the failure and retry-until-success could
    not be written at all.
    """

    async def test_default_still_fails_the_whole_loop(self) -> None:
        """Opt-in, not opt-out: tolerating silently would turn a real error
        into a quietly wrong final state for loops with no retry logic."""

        class _StrictLoop(_RetryLoop):
            _tolerate_iteration_failures: ClassVar[bool] = False

        with Tapestry() as t:
            src = _InitSource(init_state={}, _config=KnotConfig(id="init"))
            _StrictLoop(fail_times=1, max_attempts=3, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
        self.assertEqual([e.exc_type for e in result.exceptions], ["SubTapestryError"])

    async def test_fold_receives_the_failed_run_and_the_loop_retries(self) -> None:
        with Tapestry() as t:
            src = _InitSource(init_state={}, _config=KnotConfig(id="init"))
            loop = _RetryLoop(
                fail_times=2, max_attempts=5, state=src, _config=KnotConfig(id="loop")
            )
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, [e.exc_type for e in result.exceptions])
        # Two failures observed by fold, then the success that terminates.
        self.assertEqual(loop.folded, [False, False, True])
        self.assertEqual(result.outputs["loop"]["value"], "ok")
        self.assertEqual(result.outputs["loop"]["attempts"], 3)

    async def test_a_tolerated_failure_still_reaches_history(self) -> None:
        """The failed iteration is a real child run and must remain visible."""
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory

        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            src = _InitSource(init_state={}, _config=KnotConfig(id="init"))
            _RetryLoop(fail_times=1, max_attempts=5, state=src, _config=KnotConfig(id="loop"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        loop_runs = await history.children_of(result.run_id)
        iterations = await history.children_of(loop_runs[0].run_id)
        self.assertEqual([r.succeeded for r in iterations], [False, True])


class _LoopHost(SubTapestry):
    """A pipeline whose body is a loop — the PIR-713 pilot's shape."""

    async def process(self, **_: Any) -> Any:
        src = _InitSource(init_state=0, _config=KnotConfig(id="host_init"))
        return _CounterLoop(target=3, state=src, _config=KnotConfig(id="host_loop"))


class TestLoopNestedInsideAPipeline(unittest.IsolatedAsyncioTestCase):
    """A loop built inside another SubTapestry's process() must still record.

    `LoopSubTapestry.process` read the construction-time history capture, which
    inside a parent's `process()` is the throwaway `with Tapestry() as inner:`
    that `__call__` opens — discarded when the parent's inner run ends. Every
    iteration run below it went into a store nobody keeps, while the run
    reported success with the right answer.

    Same defect PIR-764 fixed in `SubTapestry._run_inner`; this call site had no
    consumer to expose it until the PIR-713 pilot nested a loop in a pipeline.
    See PIR-773.
    """

    async def test_iterations_are_recorded_from_inside_a_pipeline(self) -> None:
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory

        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            _LoopHost(_config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["host"], 3)

        host_runs = await history.children_of(result.run_id)
        self.assertEqual([r.parent_knot_id for r in host_runs], ["host"])
        loop_runs = await history.children_of(host_runs[0].run_id)
        self.assertEqual([r.parent_knot_id for r in loop_runs], ["host_loop"])
        iterations = await history.children_of(loop_runs[0].run_id)
        self.assertEqual([r.parent_knot_id for r in iterations], ["step_1", "step_2", "step_3"])

    async def test_per_iteration_lineage_survives_the_nesting(self) -> None:
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory

        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            _LoopHost(_config=KnotConfig(id="host"))
        await t.run(RunRequest())
        self.assertEqual(len(await history.query_lineage_by_knot_id("incr")), 3)
