"""``NestedRunKnot``: a plain knot's inner runs belong to the run that started them.

The knot returns its own value -- no sink-returning contract -- and each inner
run it awaits through ``_run_inner`` inherits the enclosing run's observability,
value and execution planes, nests under it, and is recorded on the knot's
lineage row so a replay posture can find it again.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, ClassVar

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.assembler import Assembler
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.err import Err
from pirn.core.execution_plane import ExecutionPlane
from pirn.core.identity.identity_resolver import IdentityResolver
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_lineage import KnotLineage
from pirn.core.ok import Ok
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.emitters.emitter import Emitter
from pirn.engine.admission.unbounded_admission_gate import UnboundedAdmissionGate
from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry, _current_execution_plane, _current_run_id


class _Value(Knot):
    """A leaf returning a fixed value, recording each live execution."""

    def __init__(self, *, calls: list[str], **kwargs: Any) -> None:
        self._calls = calls
        super().__init__(**kwargs)

    async def process(self, value: int, **_: Any) -> int:
        self._calls.append(self.knot_id)
        await asyncio.sleep(0)
        return value


class _Boom(Knot):
    async def process(self, **_: Any) -> int:
        raise RuntimeError("inner boom")


class _PlaneProbe(Knot):
    def __init__(self, *, seen: list[ExecutionPlane | None], **kwargs: Any) -> None:
        self._seen = seen
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        self._seen.append(ExecutionPlane.current())
        return 1


class _TwoRunSum(NestedRunKnot):
    """Runs one inner tapestry per value, one after the other, and returns the sum."""

    def __init__(self, *, calls: list[str], **kwargs: Any) -> None:
        self._calls = calls
        super().__init__(**kwargs)

    async def process(self, values: tuple[int, ...], **_: Any) -> int:
        total = 0
        for index, value in enumerate(values):
            with Tapestry() as inner:
                _Value(calls=self._calls, value=value, _config=KnotConfig(id=f"leaf{index}"))
            run = await self._run_inner(inner)
            total += run.outputs[f"leaf{index}"]
        return total


class _FanOutSum(NestedRunKnot):
    """One inner run fanning ``width`` leaves into an ``Aggregator``."""

    def __init__(self, *, calls: list[str], **kwargs: Any) -> None:
        self._calls = calls
        super().__init__(**kwargs)

    async def process(self, width: int, **_: Any) -> int:
        with Tapestry() as inner:
            leaves = {
                f"v{i}": _Value(calls=self._calls, value=i, _config=KnotConfig(id=f"v{i}"))
                for i in range(width)
            }
            Aggregator(combine=_FanOutSum._total, _config=KnotConfig(id="total"), **leaves)
        run = await self._run_inner(inner)
        return run.outputs["total"]

    @staticmethod
    def _total(**values: int) -> int:
        return sum(values.values())


class _Failing(NestedRunKnot):
    async def process(self, **_: Any) -> int:
        with Tapestry() as inner:
            _Boom(_config=KnotConfig(id="boom"))
        await self._run_inner(inner)
        return 0


class _Probe(NestedRunKnot):
    def __init__(self, *, seen: list[ExecutionPlane | None], **kwargs: Any) -> None:
        self._seen = seen
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> str:
        with Tapestry() as inner:
            _PlaneProbe(seen=self._seen, _config=KnotConfig(id="probe"))
        await self._run_inner(inner)
        return "probed"


class _ProbingAssembler(Assembler, NestedRunKnot):
    """A marker base and the nested-run seam in one knot."""

    def __init__(self, *, seen: list[ExecutionPlane | None], **kwargs: Any) -> None:
        self._seen = seen
        super().__init__(**kwargs)

    async def process(self, raw: str, **_: Any) -> str:
        with Tapestry() as inner:
            _PlaneProbe(seen=self._seen, _config=KnotConfig(id="probe"))
        await self._run_inner(inner)
        return raw.upper()


class _OrdinalSpyTapestry(Tapestry):
    """Records the inner-run ordinal each run is started with."""

    ordinals: ClassVar[list[int | None]] = []

    async def run(self, request: RunRequest | None = None, **kwargs: Any) -> RunResult:
        _OrdinalSpyTapestry.ordinals.append(kwargs.get("_inner_run_ordinal"))
        return await super().run(request, **kwargs)


class _SpiedRuns(NestedRunKnot):
    async def process(self, count: int, **_: Any) -> int:
        for index in range(count):
            with _OrdinalSpyTapestry() as inner:
                _Value(calls=[], value=index, _config=KnotConfig(id=f"leaf{index}"))
            await self._run_inner(inner)
        return count


class _Fixed(IdentityResolver):
    def __init__(self, actor: str) -> None:
        self._actor = actor

    def resolve(self) -> str | None:
        return self._actor


class _LineageCollector(Emitter):
    def __init__(self) -> None:
        self.rows: list[KnotLineage] = []

    async def on_lineage(self, record: KnotLineage) -> None:
        self.rows.append(record)


class TestAPlainKnotReturnsItsOwnValue(unittest.IsolatedAsyncioTestCase):
    async def test_the_knot_output_is_what_process_returned(self) -> None:
        # Arrange
        calls: list[str] = []
        with Tapestry() as t:
            _TwoRunSum(calls=calls, values=(3, 4), _config=KnotConfig(id="host"))

        # Act
        result = await t.run(RunRequest())

        # Assert
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(result.outputs["host"], 7)
        self.assertEqual(calls, ["leaf0", "leaf1"])

    async def test_a_nested_run_knot_can_sit_beside_a_marker_base(self) -> None:
        seen: list[ExecutionPlane | None] = []
        with Tapestry() as t:
            _ProbingAssembler(seen=seen, raw="abc", _config=KnotConfig(id="asm"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(result.outputs["asm"], "ABC")
        self.assertEqual(len(seen), 1)

    def test_it_is_not_a_sub_tapestry_and_holds_no_slot(self) -> None:
        self.assertFalse(issubclass(_TwoRunSum, SubTapestry))
        self.assertTrue(issubclass(SubTapestry, NestedRunKnot))
        self.assertFalse(_TwoRunSum._holds_admission_slot)


class TestInnerRunsAreRecordedOnTheKnot(unittest.IsolatedAsyncioTestCase):
    async def test_every_inner_run_is_a_child_of_the_outer_run_and_knot(self) -> None:
        history = InMemoryHistory()
        with Tapestry(history=history) as t:
            _TwoRunSum(calls=[], values=(1, 2), _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())

        children = await history.children_of(result.run_id)
        self.assertEqual(len(children), 2)
        self.assertEqual({child.parent_knot_id for child in children}, {"host"})
        (row,) = [r for r in result.lineage if r.knot_id == "host"]
        self.assertEqual(row.extra["inner_run_ids"], [c.run_id for c in children])
        self.assertEqual(row.extra["inner_run_id"], row.extra["inner_run_ids"][-1])

    async def test_a_single_inner_run_records_no_run_list(self) -> None:
        with Tapestry() as t:
            _TwoRunSum(calls=[], values=(5,), _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        (row,) = [r for r in result.lineage if r.knot_id == "host"]
        self.assertIn("inner_run_id", row.extra)
        self.assertNotIn("inner_run_ids", row.extra)

    async def test_an_inner_failure_is_the_knot_s_err_and_still_names_the_run(self) -> None:
        with Tapestry() as t:
            _Failing(_config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
        (row,) = [r for r in result.lineage if r.knot_id == "host"]
        self.assertEqual(row.outcome, "err")
        self.assertEqual(row.extra["inner_failures"], 1)
        (record,) = [e for e in result.exceptions if e.knot_id == "host"]
        self.assertEqual(record.exc_type, "SubTapestryError")
        self.assertIn("inner boom", record.message)

    async def test_the_graph_knot_keeps_no_state_between_runs(self) -> None:
        calls: list[str] = []
        with Tapestry() as t:
            host = _TwoRunSum(calls=calls, values=(1, 2), _config=KnotConfig(id="host"))
        await t.run(RunRequest())
        second = await t.run(RunRequest())
        (row,) = [r for r in second.lineage if r.knot_id == "host"]
        self.assertEqual(len(row.extra["inner_run_ids"]), 2)
        self.assertEqual(host.lineage_extra(), {})

    async def test_called_directly_outside_a_run(self) -> None:
        host = _TwoRunSum(calls=[], values=(2, 2), _config=KnotConfig(id="host"))
        outcome = await host({})
        assert isinstance(outcome, Ok)
        self.assertEqual(outcome.value, 4)


class TestInnerRunsInheritTheEnclosingPlanes(unittest.IsolatedAsyncioTestCase):
    async def test_the_inner_run_shares_the_outer_gate(self) -> None:
        seen: list[ExecutionPlane | None] = []
        with Tapestry(concurrency=ConcurrencyLimits(max_in_flight=3)) as t:
            _Probe(seen=seen, _config=KnotConfig(id="host"))
        outer_gates: list[object] = []

        class _GateProbe(Knot):
            async def process(self, **_: Any) -> int:
                plane = ExecutionPlane.current()
                assert plane is not None
                outer_gates.append(plane.gate)
                return 0

        with t:
            _GateProbe(_config=KnotConfig(id="outer-probe"))
        result = await t.run(RunRequest())

        self.assertTrue(result.succeeded, result.exceptions)
        inner_plane = seen[0]
        assert inner_plane is not None
        self.assertIs(inner_plane.gate, outer_gates[0])

    async def test_a_cap_of_one_does_not_deadlock_the_knot_on_its_own_leaves(self) -> None:
        calls: list[str] = []
        with Tapestry() as t:
            _FanOutSum(calls=calls, width=4, _config=KnotConfig(id="host"))
        result = await asyncio.wait_for(
            t.run(RunRequest(concurrency=ConcurrencyLimits(max_in_flight=1))), timeout=20
        )
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(result.outputs["host"], 6)
        self.assertEqual(sorted(calls), ["v0", "v1", "v2", "v3"])

    async def test_the_inner_run_executes_on_the_outer_dispatcher(self) -> None:
        seen: list[ExecutionPlane | None] = []
        dispatcher = ThreadDispatcher(max_workers=2)
        with Tapestry(dispatcher=dispatcher) as t:
            _Probe(seen=seen, _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        inner_plane = seen[0]
        assert inner_plane is not None
        self.assertIs(inner_plane.dispatcher, dispatcher)

    async def test_outer_emitters_hear_inner_lineage(self) -> None:
        collector = _LineageCollector()
        with Tapestry(emitters=[collector]) as t:
            _TwoRunSum(calls=[], values=(1, 1), _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual({row.knot_id for row in collector.rows}, {"host", "leaf0", "leaf1"})

    async def test_inner_values_land_in_the_outer_data_store(self) -> None:
        history = InMemoryHistory()
        store = InMemoryDataStore()
        with Tapestry(history=history, data_store=store) as t:
            _TwoRunSum(calls=[], values=(9,), _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        (child,) = await history.children_of(result.run_id)
        (row,) = child.lineage
        assert row.output_hash is not None
        self.assertEqual(await store.get(row.output_hash), 9)

    async def test_the_inner_run_is_attributed_to_the_outer_actor(self) -> None:
        history = InMemoryHistory()
        with Tapestry(history=history, identity_resolver=_Fixed("alice")) as t:
            _TwoRunSum(calls=[], values=(1,), _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        (child,) = await history.children_of(result.run_id)
        self.assertEqual(child.actor, "alice")

    async def test_a_depth_cap_refuses_the_nested_run(self) -> None:
        calls: list[str] = []
        with Tapestry(max_nesting_depth=0) as t:
            _TwoRunSum(calls=calls, values=(1,), _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
        self.assertEqual(calls, [])

    def test_a_nested_run_knot_may_not_join_a_concurrency_group(self) -> None:
        with self.assertRaises(ValueError) as caught, Tapestry():
            _TwoRunSum(
                calls=[], values=(1,), _config=KnotConfig(id="host", concurrency_group="api")
            )
        self.assertIn("api", str(caught.exception))


class TestInheritedReplayPicksTheInnerRunByOrdinal(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _plane(replay: ReplaySession | None) -> ExecutionPlane:
        return ExecutionPlane(
            dispatcher=LocalDispatcher(),
            gate=UnboundedAdmissionGate(),
            limits=None,
            admission_observers=(),
            replay=replay,
            identity_resolver=_Fixed("replayer"),
        )

    async def _replay_inner(self, *, ordinal: int) -> tuple[str, str | None, list[str]]:
        # Arrange: a recorded run whose host started two inner runs.
        calls: list[str] = []
        history = InMemoryHistory()
        store = InMemoryDataStore()
        with Tapestry(history=history, data_store=store) as t:
            _TwoRunSum(calls=calls, values=(10, 20), _config=KnotConfig(id="host"))
        outer = await t.run(RunRequest())
        (row,) = [r for r in outer.lineage if r.knot_id == "host"]
        recording = row.extra["inner_run_ids"][ordinal]
        with Tapestry(history=history, data_store=store) as inner:
            _Value(
                calls=calls,
                value=(10, 20)[ordinal],
                _config=KnotConfig(id=f"leaf{ordinal}"),
            )

        # Act: start that inner run as the host's n-th, under outer replay.
        token_plane = _current_execution_plane.set(self._plane(ReplaySession(source_run=outer)))
        token_run = _current_run_id.set(outer.run_id)
        try:
            replayed = await inner.run(
                RunRequest(), _parent_knot_id="host", _inner_run_ordinal=ordinal
            )
        finally:
            _current_run_id.reset(token_run)
            _current_execution_plane.reset(token_plane)

        self.assertTrue(replayed.succeeded, replayed.exceptions)
        (replayed_row,) = replayed.lineage
        return recording, replayed_row.extra.get("replayed_from_run_id"), calls

    async def test_the_first_inner_run_is_served_from_the_first_recording(self) -> None:
        recording, served_from, calls = await self._replay_inner(ordinal=0)
        self.assertEqual(served_from, recording)
        self.assertEqual(calls, ["leaf0", "leaf1"])

    async def test_the_second_inner_run_is_served_from_the_second_recording(self) -> None:
        recording, served_from, calls = await self._replay_inner(ordinal=1)
        self.assertEqual(served_from, recording)
        self.assertEqual(calls, ["leaf0", "leaf1"])

    async def test_replaying_the_outer_run_serves_the_knot_without_inner_runs(self) -> None:
        calls: list[str] = []
        history = InMemoryHistory()
        store = InMemoryDataStore()
        with Tapestry(history=history, data_store=store) as t:
            _TwoRunSum(calls=calls, values=(1, 2), _config=KnotConfig(id="host"))
        outer = await t.run(RunRequest())
        session = await ReplaySession.from_history(history=history, run_id=outer.run_id)

        replayed = await t.run(RunRequest(), replay=session)

        self.assertTrue(replayed.succeeded, replayed.exceptions)
        self.assertEqual(replayed.outputs["host"], 3)
        self.assertEqual(calls, ["leaf0", "leaf1"])

    async def test_the_knot_reports_each_inner_run_s_ordinal(self) -> None:
        _OrdinalSpyTapestry.ordinals = []
        with Tapestry() as t:
            _SpiedRuns(count=3, _config=KnotConfig(id="host"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(_OrdinalSpyTapestry.ordinals, [0, 1, 2])

    def test_the_recorded_run_id_lookup(self) -> None:
        many = {"inner_run_id": "r2", "inner_run_ids": ["r1", "r2"]}
        one = {"inner_run_id": "r1"}
        lookup = Tapestry._recorded_inner_run_id
        self.assertEqual(lookup(many, 0), "r1")
        self.assertEqual(lookup(many, 1), "r2")
        self.assertIsNone(lookup(many, 2))
        self.assertEqual(lookup(many, None), "r2")
        self.assertEqual(lookup(one, 0), "r1")
        self.assertEqual(lookup(one, None), "r1")
        self.assertIsNone(lookup(one, 1))
        self.assertIsNone(lookup({}, 0))


class TestAnErrIsNotAnException(unittest.IsolatedAsyncioTestCase):
    async def test_direct_call_returns_err_for_an_inner_failure(self) -> None:
        outcome = await _Failing(_config=KnotConfig(id="host"))({})
        self.assertIsInstance(outcome, Err)


if __name__ == "__main__":
    unittest.main()
