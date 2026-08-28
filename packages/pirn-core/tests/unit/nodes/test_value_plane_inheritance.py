"""An inner run must write its values where its lineage rows point.

`SubTapestry` forwarded the outer `RunHistory` into the inner tapestry but not
the outer `DataStore`, so the inner `Tapestry()` kept the fresh
`InMemoryDataStore` it was constructed with and threw it away when the inner run
ended.  Inner-run *lineage* was durable; inner-run *values* were not, and a
`KnotLineage` row for an inner knot advertised an `output_hash` that resolved
against nothing.  See PIR-837, sibling to PIR-834 (emitters).

Every value here is deliberately distinct.  Content addressing makes an inner
hash resolve in the outer store whenever the inner value happens to equal an
outer one — the sink of an inner pipeline always does, since it *is* the
SubTapestry's output — so a probe built on equal values reports a pass that has
nothing to do with the store being shared.  The knot under test is therefore an
inner *source* whose value no outer knot ever produces, and
``test_the_probe_value_is_unique_to_the_inner_run`` guards that property.

The transport rides along, with one asymmetry pinned here: the data store is
forwarded unconditionally because a lineage row and the value it names are two
halves of one record, while the transport yields to an inner tapestry that named
its own — a transport is intra-run plumbing that no durable record references.
"""

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, Any

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.inline_transport import InlineTransport
from pirn.core.transport.transport_handle import TransportHandle
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry, _apply_inherited_value_plane
from pirn.tapestry import Tapestry

if TYPE_CHECKING:
    from pirn.core.lineage import KnotLineage
    from pirn.core.run_result import RunResult

#: Produced only by the inner source, so its hash cannot be planted in the outer
#: store by any other knot in these pipelines.
INNER_ONLY = 424242


class _Upstream(Knot):
    async def process(self, **_: Any) -> int:
        return 1000


class _InnerSource(Knot):
    async def process(self, **_: Any) -> int:
        return INNER_ONLY


class _InnerSink(Knot):
    async def process(self, v: int, **_: Any) -> int:
        return v + 7


class _Sub(SubTapestry):
    """Two inner knots, so the inner *source* is not also the inner sink.

    A one-knot body cannot detect this defect: its output is the SubTapestry's
    output, so the outer run stores that exact value under that exact hash.
    """

    async def process(self, v: int, **_: Any) -> Knot:
        source = _InnerSource(_config=KnotConfig(id="inner-source"))
        return _InnerSink(v=source, _config=KnotConfig(id="inner-sink"))


class _Nesting(SubTapestry):
    """Builds a nested SubTapestry inside its own `process()` body.

    The `_Sub` instance is constructed while the ambient tapestry is the
    throwaway one `SubTapestry.__call__` opened, whose data store is a fresh
    `InMemoryDataStore` about to be discarded.  Inheritance has to read the live
    contextvar to find the real outer store, exactly as history does after
    PIR-764/PIR-773.
    """

    async def process(self, v: int, **_: Any) -> Knot:
        return _Sub(v=v, _config=KnotConfig(id="nested-sub"))


class _RecordingTransport(DataTransport):
    """Inline transport that records the run-scoped calls made against it."""

    def __init__(self) -> None:
        self._delegate = InlineTransport()
        self.begun: list[str] = []
        self.ended: list[str] = []
        self.writes: list[tuple[str, str]] = []

    @property
    def transport_id(self) -> str:
        return f"recording:{id(self)}"

    async def begin_run(self, run_id: str) -> None:
        self.begun.append(run_id)
        await self._delegate.begin_run(run_id)

    async def write(self, run_id: str, knot_id: str, value: Any) -> TransportHandle:
        self.writes.append((run_id, knot_id))
        # The delegate's handle is returned unchanged: the engine reads a value
        # back through the transport recorded in its own ``handle_transports``
        # map, not through the handle's ``transport_id``.
        return await self._delegate.write(run_id, knot_id, value)

    async def read(self, handle: TransportHandle) -> Any:
        return await self._delegate.read(handle)

    async def exists(self, handle: TransportHandle) -> bool:
        return await self._delegate.exists(handle)

    async def end_run(self, run_id: str, *, success: bool) -> None:
        self.ended.append(run_id)
        await self._delegate.end_run(run_id, success=success)

    @property
    def written_knots(self) -> set[str]:
        return {knot_id for _, knot_id in self.writes}


async def _all_rows(history: InMemoryHistory, result: RunResult) -> list[KnotLineage]:
    """Every lineage row of *result* and of every run descended from it."""
    rows = list(result.lineage)
    pending = [result.run_id]
    seen = {result.run_id}
    while pending:
        for child in await history.children_of(pending.pop()):
            if child.run_id in seen:
                continue
            seen.add(child.run_id)
            rows.extend(child.lineage)
            pending.append(child.run_id)
    return rows


class _ValuePlaneCase(unittest.IsolatedAsyncioTestCase):
    """Runs one SubTapestry shape and exposes the store, history and rows."""

    sub_type: type[SubTapestry] = _Sub

    async def asyncSetUp(self) -> None:
        self.store = InMemoryDataStore()
        self.history = InMemoryHistory()
        with Tapestry(history=self.history, data_store=self.store) as tapestry:
            upstream = _Upstream(_config=KnotConfig(id="up"))
            self.sub_type(v=upstream, _config=KnotConfig(id="sub"))
        self.result = await tapestry.run(RunRequest())
        self.assertTrue(self.result.succeeded, self.result.exceptions)
        self.rows = await _all_rows(self.history, self.result)

    def _row(self, knot_id: str) -> KnotLineage:
        matches = [row for row in self.rows if row.knot_id == knot_id]
        self.assertEqual(1, len(matches), f"expected exactly one {knot_id!r} row")
        return matches[0]


class TestSubTapestryValuesReachTheOuterStore(_ValuePlaneCase):
    async def test_the_inner_source_value_resolves_in_the_outer_store(self) -> None:
        """The regression: this hash used to name nothing at all."""
        row = self._row("inner-source")
        self.assertTrue(
            await self.store.has(row.output_hash),
            "inner lineage row points at a value the outer store cannot resolve",
        )
        self.assertEqual(INNER_ONLY, await self.store.get(row.output_hash))

    async def test_the_probe_value_is_unique_to_the_inner_run(self) -> None:
        """Guards the test above against a content-addressing false positive.

        If the inner source's hash matched an outer knot's, the assertion would
        pass on a store that was never shared.
        """
        inner_hash = self._row("inner-source").output_hash
        outer_hashes = {row.output_hash for row in self.result.lineage}
        self.assertNotIn(inner_hash, outer_hashes)

    async def test_every_recorded_row_across_every_run_resolves(self) -> None:
        """A durable lineage row with a dangling value is the defect, generalised."""
        dangling = [row.knot_id for row in self.rows if not await self.store.has(row.output_hash)]
        self.assertEqual([], dangling)

    async def test_the_inner_run_is_still_recorded_in_the_outer_history(self) -> None:
        """Forwarding the value plane must not disturb what PIR-764 established."""
        children = await self.history.children_of(self.result.run_id)
        self.assertEqual(1, len(children))
        self.assertEqual({"inner-source", "inner-sink"}, {r.knot_id for r in children[0].lineage})

    async def test_the_outer_result_is_unchanged(self) -> None:
        self.assertEqual({"up": 1000, "sub": INNER_ONLY + 7}, dict(self.result.outputs))


class TestNestedSubTapestryReachesTheRealOuterStore(_ValuePlaneCase):
    """The case the construction-time capture gets wrong.

    A `SubTapestry` built inside another's `process()` captures the throwaway
    inner tapestry, whose data store dies with the parent's inner run.  Only the
    live contextvar names the store the top-level run is actually writing to.
    """

    sub_type = _Nesting

    async def test_the_innermost_value_resolves_at_the_top_level(self) -> None:
        row = self._row("inner-source")
        self.assertTrue(await self.store.has(row.output_hash))
        self.assertEqual(INNER_ONLY, await self.store.get(row.output_hash))

    async def test_all_three_nesting_levels_are_recorded_and_resolvable(self) -> None:
        by_knot = {row.knot_id for row in self.rows}
        self.assertEqual({"up", "sub", "nested-sub", "inner-source", "inner-sink"}, by_knot)
        for row in self.rows:
            self.assertTrue(await self.store.has(row.output_hash), row.knot_id)


class TestTransportIsInheritedByInnerRuns(unittest.IsolatedAsyncioTestCase):
    """A tapestry-level transport must not stop at the SubTapestry boundary.

    Otherwise a pipeline configured with a disk- or object-store-backed
    transport silently drops back to `InlineTransport` inside a SubTapestry
    body, which is exactly where the bulk of its data often moves — defeating
    the memory-pressure reason the transport was chosen for.
    """

    async def _run(self) -> tuple[RunResult, _RecordingTransport]:
        transport = _RecordingTransport()
        with Tapestry(history=InMemoryHistory(), transport=transport) as tapestry:
            upstream = _Upstream(_config=KnotConfig(id="up"))
            _Sub(v=upstream, _config=KnotConfig(id="sub"))
        result = await tapestry.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        return result, transport

    async def test_inner_knots_are_written_through_the_outer_transport(self) -> None:
        _, transport = await self._run()
        self.assertEqual({"up", "sub", "inner-source", "inner-sink"}, transport.written_knots)

    async def test_the_inner_run_gets_its_own_transport_lifecycle(self) -> None:
        """Sharing one instance is safe because every call is keyed by run_id."""
        result, transport = await self._run()
        self.assertEqual(2, len(transport.begun))
        self.assertEqual(sorted(transport.begun), sorted(transport.ended))
        self.assertIn(result.run_id, transport.begun)
        inner_run_ids = {run_id for run_id, knot in transport.writes if knot == "inner-source"}
        self.assertEqual(1, len(inner_run_ids))
        self.assertNotIn(result.run_id, inner_run_ids)

    async def test_the_inner_run_ends_before_the_outer_one(self) -> None:
        result, transport = await self._run()
        self.assertEqual(result.run_id, transport.ended[-1])


class _CounterLoop(LoopSubTapestry[int]):
    """Counts up to a target; one iteration run per turn.

    ``iteration_transport`` lets a test give the iteration tapestry a transport
    of its own, which is the only way a user-built inner tapestry gets one.
    """

    def __init__(
        self,
        *,
        target: int,
        iteration_transport: DataTransport | None = None,
        **kwargs: Any,
    ) -> None:
        self._target = target
        self._iteration_transport = iteration_transport
        super().__init__(**kwargs)

    def step(self, state: int) -> tuple[Tapestry, int] | None:
        if state >= self._target:
            return None
        # Closed over rather than declared as an input: the engine reads
        # `process`'s parameter names as the knot's inputs.  Offset so no two
        # turns, and no outer knot, produce the same value.
        produced = INNER_ONLY + state + 1

        class _Incr(Source):
            async def process(self, **_: Any) -> int:
                return produced

        tapestry = Tapestry(transport=self._iteration_transport)
        with tapestry:
            _Incr(_config=KnotConfig(id="incr"))
        return tapestry, state + 1

    def fold(self, state: int, result: RunResult) -> int:
        # `state` is already the value `step` returned for this turn, so the
        # count advances in `step` alone; folding it again would skip a turn.
        return state


class _Seed(Source):
    async def process(self, **_: Any) -> int:
        return 0


class TestLoopIterationsInheritTheValuePlane(unittest.IsolatedAsyncioTestCase):
    """Each turn runs its own tapestry, built by user code inside `step()`.

    Those tapestries are constructed with defaults just like the SubTapestry
    throwaway, so a turn's values went to a store discarded at the end of the
    turn while its lineage rows were recorded in the outer history.
    """

    async def _run_loop(self, target: int) -> tuple[RunResult, InMemoryDataStore, InMemoryHistory]:
        store = InMemoryDataStore()
        history = InMemoryHistory()
        with Tapestry(history=history, data_store=store) as tapestry:
            seed = _Seed(_config=KnotConfig(id="seed"))
            _CounterLoop(target=target, state=seed, _config=KnotConfig(id="loop"))
        result = await tapestry.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        return result, store, history

    async def test_each_turn_s_value_resolves_in_the_outer_store(self) -> None:
        result, store, history = await self._run_loop(3)
        rows = await _all_rows(history, result)
        incr_rows = [row for row in rows if row.knot_id == "incr"]
        self.assertEqual(3, len(incr_rows))
        for turn, row in enumerate(sorted(incr_rows, key=lambda r: r.output_hash)):
            self.assertTrue(await store.has(row.output_hash), f"turn {turn} value is dangling")
        self.assertEqual(
            {INNER_ONLY + 1, INNER_ONLY + 2, INNER_ONLY + 3},
            {await store.get(row.output_hash) for row in incr_rows},
        )

    async def test_no_recorded_row_anywhere_in_the_loop_dangles(self) -> None:
        result, store, history = await self._run_loop(2)
        rows = await _all_rows(history, result)
        dangling = [row.knot_id for row in rows if not await store.has(row.output_hash)]
        self.assertEqual([], dangling)


class TestLoopIterationTransportChoiceWins(unittest.IsolatedAsyncioTestCase):
    """The one place an inner tapestry can name its own transport.

    `SubTapestry.__call__` builds `Tapestry()` with no arguments, so only a
    `LoopSubTapestry` iteration can arrive with a transport its author chose.
    Inheritance must not overwrite that — it would be the same silent override
    the ticket complains about, pointed the other way.
    """

    async def _run(self, iteration_transport: DataTransport | None) -> tuple[Any, Any]:
        outer = _RecordingTransport()
        with Tapestry(history=InMemoryHistory(), transport=outer) as tapestry:
            seed = _Seed(_config=KnotConfig(id="seed"))
            _CounterLoop(
                target=2,
                iteration_transport=iteration_transport,
                state=seed,
                _config=KnotConfig(id="loop"),
            )
        result = await tapestry.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        return outer, result

    async def test_an_iteration_without_its_own_transport_inherits(self) -> None:
        outer, _ = await self._run(None)
        self.assertIn("incr", outer.written_knots)
        self.assertEqual(2, len([k for _, k in outer.writes if k == "incr"]))

    async def test_an_iteration_that_named_a_transport_keeps_it(self) -> None:
        own = _RecordingTransport()
        outer, _ = await self._run(own)
        self.assertEqual(2, len([k for _, k in own.writes if k == "incr"]))
        self.assertNotIn("incr", outer.written_knots)

    async def test_the_loop_s_own_run_still_uses_the_outer_transport(self) -> None:
        """Only the iteration tapestry opted out; the loop run itself did not."""
        own = _RecordingTransport()
        outer, _ = await self._run(own)
        self.assertIn("step_1", outer.written_knots)
        self.assertNotIn("step_1", own.written_knots)


class TestApplyInheritedValuePlane(unittest.TestCase):
    """Unit coverage for the rule the two forwarding sites share."""

    def test_nothing_to_inherit_leaves_both_halves_alone(self) -> None:
        inner = Tapestry()
        store, transport = inner.data_store, inner.transport
        _apply_inherited_value_plane(inner, data_store=None, transport=None)
        self.assertIs(store, inner.data_store)
        self.assertIs(transport, inner.transport)

    def test_the_data_store_is_replaced(self) -> None:
        inner, outer_store = Tapestry(), InMemoryDataStore()
        _apply_inherited_value_plane(inner, data_store=outer_store, transport=None)
        self.assertIs(outer_store, inner.data_store)

    def test_the_data_store_is_replaced_even_when_the_inner_named_one(self) -> None:
        """Pins the asymmetry: the store follows the history, which is also forced.

        A row routed to the outer history whose value went to some other store
        is the dangling reference PIR-837 is about, so an inner tapestry does
        not get to keep its own store while its rows are recorded elsewhere.
        """
        inner = Tapestry(data_store=InMemoryDataStore())
        outer_store = InMemoryDataStore()
        _apply_inherited_value_plane(inner, data_store=outer_store, transport=None)
        self.assertIs(outer_store, inner.data_store)

    def test_a_defaulted_transport_is_replaced(self) -> None:
        inner, outer_transport = Tapestry(), _RecordingTransport()
        _apply_inherited_value_plane(inner, data_store=None, transport=outer_transport)
        self.assertIs(outer_transport, inner.transport)

    def test_an_explicit_transport_is_kept(self) -> None:
        own = _RecordingTransport()
        inner = Tapestry(transport=own)
        _apply_inherited_value_plane(inner, data_store=None, transport=_RecordingTransport())
        self.assertIs(own, inner.transport)

    def test_an_explicitly_passed_inline_transport_is_also_kept(self) -> None:
        """The explicit flag exists because the default cannot be recognised by type."""
        own = InlineTransport()
        inner = Tapestry(transport=own)
        _apply_inherited_value_plane(inner, data_store=None, transport=_RecordingTransport())
        self.assertIs(own, inner.transport)


class TestTapestryPublishesItsValuePlane(unittest.IsolatedAsyncioTestCase):
    """`run()` has to publish both halves for the forwarding sites to read them."""

    async def test_the_running_tapestry_s_store_and_transport_are_visible(self) -> None:
        from pirn.tapestry import _current_data_store, _current_transport

        seen: dict[str, Any] = {}

        class _Peek(Source):
            async def process(self, **_: Any) -> int:
                seen["store"] = _current_data_store.get(None)
                seen["transport"] = _current_transport.get(None)
                return 1

        store, transport = InMemoryDataStore(), _RecordingTransport()
        with Tapestry(data_store=store, transport=transport) as tapestry:
            _Peek(_config=KnotConfig(id="peek"))
        self.assertTrue((await tapestry.run(RunRequest())).succeeded)
        self.assertIs(store, seen["store"])
        self.assertIs(transport, seen["transport"])

    async def test_the_vars_are_cleared_when_the_run_ends(self) -> None:
        from pirn.tapestry import _current_data_store, _current_transport

        with Tapestry() as tapestry:
            _Seed(_config=KnotConfig(id="seed"))
        await tapestry.run(RunRequest())
        self.assertIsNone(_current_data_store.get(None))
        self.assertIsNone(_current_transport.get(None))
