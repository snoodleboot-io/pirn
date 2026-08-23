"""An emitter attached to the outer tapestry must also see inner-run work.

`SubTapestry` forwarded the outer `RunHistory` into the inner tapestry but not
the outer emitters, and `Engine` fans `on_status` / `on_lineage` /
`on_run_result` per run.  So a knot moved into a SubTapestry body was recorded
in `history.children_of(outer_run_id)` and emitted nothing at all — the two
observability planes disagreed about the same execution, and anything relying
on emitters for spans, metrics or logs silently lost coverage while still
looking fully traced in the explorer.  See PIR-834.

The nested case is the one that bites: a SubTapestry constructed inside another
SubTapestry's `process()` captures the *throwaway* `with Tapestry() as inner:`
that `__call__` opens, which carries no emitters at all.  Inheritance therefore
has to read the live contextvar first, exactly as history does after
PIR-764/PIR-773.
"""

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.emitters.base import Emitter
from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry, _inherited_emitters
from pirn.tapestry import Tapestry

if TYPE_CHECKING:
    from pirn.core.lineage import KnotLineage
    from pirn.core.run_result import RunResult
    from pirn.managers.status_event import StatusEvent


class _Recorder(Emitter):
    """Captures every event the engine fans at it, tagged with its run."""

    def __init__(self) -> None:
        self.lineage: list[tuple[str, str]] = []
        self.status: list[tuple[str, str]] = []
        self.runs: list[str] = []

    async def on_lineage(self, record: KnotLineage) -> None:
        self.lineage.append((record.run_id, record.knot_id))

    async def on_status(self, event: StatusEvent) -> None:
        self.status.append((event.run_id, event.knot_id))

    async def on_run_result(self, result: RunResult) -> None:
        self.runs.append(result.run_id)

    @property
    def lineage_knots(self) -> set[str]:
        return {knot_id for _, knot_id in self.lineage}

    @property
    def status_knots(self) -> set[str]:
        return {knot_id for _, knot_id in self.status}


class _Double(Knot):
    async def process(self, v: int, **_: Any) -> int:
        return v * 2


class _Sub(SubTapestry):
    """One inner knot, so the inner run is trivially identifiable."""

    async def process(self, v: int, **_: Any) -> Knot:
        return _Double(v=v, _config=KnotConfig(id="inner-double"))


class _Outer(SubTapestry):
    """Builds a *nested* SubTapestry inside its own `process()` body.

    The `_Sub` instance is therefore constructed while the ambient tapestry is
    the throwaway one `SubTapestry.__call__` opened, which has no emitters.
    """

    async def process(self, v: int, **_: Any) -> Knot:
        return _Sub(v=v, _config=KnotConfig(id="nested-sub"))


class TestPlainSubTapestryForwardsEmitters(unittest.IsolatedAsyncioTestCase):
    async def _run(self) -> tuple[RunResult, _Recorder, InMemoryHistory]:
        recorder = _Recorder()
        history = InMemoryHistory()
        with Tapestry(history=history, emitters=[recorder]) as t:
            _Sub(v=3, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        return result, recorder, history

    async def test_inner_knot_reaches_the_outer_emitter(self) -> None:
        """The regression: 'inner-double' used to be absent from both streams."""
        _, recorder, _ = await self._run()
        self.assertIn("inner-double", recorder.lineage_knots)
        self.assertIn("inner-double", recorder.status_knots)

    async def test_the_inner_run_itself_is_emitted(self) -> None:
        result, recorder, _ = await self._run()
        self.assertEqual(len(recorder.runs), 2)
        self.assertIn(result.run_id, recorder.runs)

    async def test_emitters_and_history_now_agree(self) -> None:
        """The point of the ticket: neither plane may see work the other misses."""
        result, recorder, history = await self._run()
        recorded = {result.run_id}
        for child in await history.children_of(result.run_id):
            recorded.add(child.run_id)
        self.assertEqual(set(recorder.runs), recorded)

    async def test_each_record_is_emitted_exactly_once(self) -> None:
        """Forwarding must not double-fan the outer run's own records."""
        _, recorder, _ = await self._run()
        self.assertEqual(len(recorder.lineage), len(set(recorder.lineage)))

    async def test_an_opted_out_run_stays_opted_out(self) -> None:
        """`run(emitters=[])` is explicit; inner runs must not resurrect a capture."""
        recorder = _Recorder()
        with Tapestry(emitters=[recorder]) as t:
            _Sub(v=3, _config=KnotConfig(id="sub"))
        result = await t.run(RunRequest(), emitters=[])
        self.assertTrue(result.succeeded)
        self.assertEqual(recorder.lineage, [])
        self.assertEqual(recorder.runs, [])


class TestNestedSubTapestryForwardsTheRealOuterEmitters(unittest.IsolatedAsyncioTestCase):
    """A SubTapestry built inside another SubTapestry's `process()`.

    Its construction-time capture is the throwaway inner tapestry, which has no
    emitters — so if inheritance trusted that capture the innermost knot would
    stay invisible.  PIR-764 fixed the same shape for history.
    """

    async def test_the_innermost_knot_reaches_the_top_level_emitter(self) -> None:
        recorder = _Recorder()
        with Tapestry(history=InMemoryHistory(), emitters=[recorder]) as t:
            _Outer(v=3, _config=KnotConfig(id="outer"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["outer"], 6)
        self.assertEqual(
            {"outer", "nested-sub", "inner-double"},
            recorder.lineage_knots,
        )
        self.assertEqual(3, len(recorder.runs), "one run per nesting level")

    async def test_every_nested_run_is_distinct(self) -> None:
        recorder = _Recorder()
        with Tapestry(history=InMemoryHistory(), emitters=[recorder]) as t:
            _Outer(v=3, _config=KnotConfig(id="outer"))
        await t.run(RunRequest())
        self.assertEqual(len(recorder.runs), len(set(recorder.runs)))


class _FailsOnInnerKnot(Emitter):
    """Raises only for the inner knot's lineage record.

    Scoped that narrowly so a RAISE policy can be attributed to the *inner*
    run's fan-out rather than to the outer run's.
    """

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def on_lineage(self, record: KnotLineage) -> None:
        self.seen.append(record.knot_id)
        if record.knot_id == "inner-double":
            raise RuntimeError("emitter boom")


class TestEmitterErrorPolicyIsHonouredForInnerRuns(unittest.IsolatedAsyncioTestCase):
    """The policy travels with the emitters it governs.

    Forwarding the list while leaving the inner run on its own default would
    silently downgrade a RAISE subscription to WARN for exactly the events this
    ticket made visible.
    """

    async def _run_with(self, policy: EmitterErrorPolicy) -> RunResult:
        with Tapestry(emitters=[_FailsOnInnerKnot()], emitter_error_policy=policy) as t:
            _Sub(v=3, _config=KnotConfig(id="sub"))
        return await t.run(RunRequest())

    async def test_warn_lets_the_inner_run_finish(self) -> None:
        result = await self._run_with(EmitterErrorPolicy.WARN)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["sub"], 6)

    async def test_ignore_lets_the_inner_run_finish(self) -> None:
        result = await self._run_with(EmitterErrorPolicy.IGNORE)
        self.assertTrue(result.succeeded)

    async def test_raise_fails_the_sub_tapestry_knot(self) -> None:
        """RAISE aborts inner-run finalisation, which surfaces as an Err on the knot."""
        result = await self._run_with(EmitterErrorPolicy.RAISE)
        self.assertFalse(result.succeeded)
        self.assertTrue(any("emitter boom" in r.message for r in result.exceptions))


class _CounterLoop(LoopSubTapestry[int]):
    """Counts up to a target, one iteration run per turn."""

    def __init__(self, *, target: int, iteration_emitters: list[Any] | None = None, **kwargs: Any):
        self._target = target
        self._iteration_emitters = iteration_emitters
        super().__init__(**kwargs)

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= self._target:
            return None
        # Closed over rather than passed as an input: the engine reads
        # `process`'s parameter names as declared inputs, so the knot must not
        # grow a parameter just to carry the turn's value.
        incremented = state + 1

        class _Incr(Source):
            async def process(self, **_: Any) -> int:
                return incremented

        t = Tapestry(emitters=self._iteration_emitters)
        with t:
            _Incr(_config=KnotConfig(id="incr"))
        return t, state + 1

    def fold(self, state: int, result: RunResult) -> int:
        return result.outputs["incr"]


class _Seed(Source):
    async def process(self, **_: Any) -> int:
        return 0


class TestLoopSubTapestryEmitsPerTurn(unittest.IsolatedAsyncioTestCase):
    """Forwarding into a loop is unconditional, and that is the decision.

    `LoopSubTapestry` records one child run per turn, so an emitter sees one
    `on_run_result` per turn plus every knot inside it.  `RunRetention`
    (PIR-765) bounds *history* growth because `InMemoryHistory` is the default
    backend; there is no default emitter, so every emitter present was attached
    deliberately and its intake is proportional to work the loop performed.
    Suppressing iteration events would reproduce PIR-834 one level down.
    """

    async def _run_loop(self, target: int, **loop_kwargs: Any) -> _Recorder:
        recorder = _Recorder()
        with Tapestry(history=InMemoryHistory(), emitters=[recorder]) as t:
            seed = _Seed(_config=KnotConfig(id="seed"))
            _CounterLoop(target=target, state=seed, _config=KnotConfig(id="loop"), **loop_kwargs)
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["loop"], target)
        return recorder

    async def test_every_turn_produces_a_run_result(self) -> None:
        recorder = await self._run_loop(3)
        # outer run + the loop's own extensible run + one run per turn.
        self.assertEqual(len(recorder.runs), 2 + 3)

    async def test_the_work_inside_each_turn_is_emitted(self) -> None:
        recorder = await self._run_loop(3)
        incr_records = [r for r in recorder.lineage if r[1] == "incr"]
        self.assertEqual(len(incr_records), 3)
        self.assertEqual(len({run_id for run_id, _ in incr_records}), 3, "distinct runs")

    async def test_the_iteration_chain_knots_are_emitted(self) -> None:
        recorder = await self._run_loop(2)
        self.assertLessEqual({"step_1", "step_2", "__loop_terminal__"}, recorder.lineage_knots)

    async def test_volume_scales_with_turns(self) -> None:
        """Pins the decision numerically, so a later cap is a deliberate change."""
        short = await self._run_loop(1)
        long = await self._run_loop(4)
        self.assertEqual(len(long.runs) - len(short.runs), 3)

    async def test_an_emitter_on_both_tapestries_is_not_double_fanned(self) -> None:
        """A user may attach the same emitter to an iteration tapestry."""
        shared = _Recorder()
        with Tapestry(history=InMemoryHistory(), emitters=[shared]) as t:
            seed = _Seed(_config=KnotConfig(id="seed"))
            _CounterLoop(
                target=2,
                iteration_emitters=[shared],
                state=seed,
                _config=KnotConfig(id="loop"),
            )
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(len(shared.lineage), len(set(shared.lineage)))
        self.assertEqual(len(shared.runs), len(set(shared.runs)))


class TestInheritedEmitters(unittest.TestCase):
    """Unit coverage for the merge rule the two forwarding sites share."""

    def test_nothing_to_inherit_leaves_the_inner_subscription_alone(self) -> None:
        own = [_Recorder()]
        self.assertIsNone(_inherited_emitters(own, None))

    def test_an_empty_inherited_list_is_also_a_no_override(self) -> None:
        """`run(emitters=[])` must not be turned into 'use the inner defaults'."""
        self.assertIsNone(_inherited_emitters([], []))

    def test_inherited_emitters_are_appended_after_the_tapestry_s_own(self) -> None:
        own, outer = _Recorder(), _Recorder()
        self.assertEqual([own, outer], _inherited_emitters([own], [outer]))

    def test_a_shared_instance_appears_once(self) -> None:
        shared, other = _Recorder(), _Recorder()
        self.assertEqual([shared, other], _inherited_emitters([shared], [shared, other]))

    def test_deduplication_is_by_identity_not_equality(self) -> None:
        class _AlwaysEqual(Emitter):
            def __eq__(self, other: object) -> bool:
                return True

            def __hash__(self) -> int:
                return 0

        first, second = _AlwaysEqual(), _AlwaysEqual()
        merged = _inherited_emitters([first], [second])
        assert merged is not None
        self.assertEqual(2, len(merged))
        self.assertIs(first, merged[0])
        self.assertIs(second, merged[1])
