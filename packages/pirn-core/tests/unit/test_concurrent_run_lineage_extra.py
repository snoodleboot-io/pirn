"""Concurrent runs against one shared ``Tapestry`` must record their own lineage.

Sibling defect to PIR-802.  That one was about a run *computing* with another
run's input; this one is about a run *recording* another run's answer.  Four
knots publish run-derived metadata by writing it onto the shared graph knot,
and ``Engine._record_lineage`` reads it back after an ``await``:

* ``SubTapestry`` writes ``inner_run_id`` / ``inner_knot_count`` /
  ``inner_failures``,
* ``Knot._fan_out`` writes ``map_type`` / ``element_count`` / ``dict_keys``,
* ``Branch`` writes ``selected_branch``,
* ``Gate`` writes ``predicate_passed``.

Every run still computes and returns the right value, so the corruption is
invisible in the outputs -- it shows up only in the lineage record, which is
exactly where nobody looks until they need it.  ``inner_run_id`` is the only
navigation path from an outer lineage record to its child run, so a wrong one
sends an investigator to a different request's child run.

These tests pin the contract that run-derived lineage metadata is per-run.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.branch.branch import Branch
from pirn.nodes.gate.gate import Gate
from pirn.nodes.map_markers import DictMap, Map, ZipMap
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _identity(value: Any) -> Any:
    await asyncio.sleep(0.01)
    return value


@knot
async def _inner_double(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


# Fan-out corruption is a real race: the shared slot is overwritten only if a
# sibling run's ``_fan_out`` finishes inside the window between this run's
# dispatch returning and the engine reading the slot back.  Left to chance the
# reproduction passes perhaps half the time, so the fan-out tests gate every
# element on one barrier.  All runs' collections then resolve in the same tick,
# which puts every write inside every other run's window and makes
# last-writer-wins deterministic rather than lucky.
_barrier: asyncio.Barrier | None = None


async def _wait_for_siblings() -> None:
    if _barrier is not None:
        await _barrier.wait()


@knot
async def _per_element(item: int) -> int:
    await _wait_for_siblings()
    return item


@knot
async def _pair(left: int, right: int) -> int:
    await _wait_for_siblings()
    return left + right


@knot
async def _entry(key: str, value: int) -> str:
    await _wait_for_siblings()
    return f"{key}={value}"


class _Doubler(SubTapestry):
    async def process(self, x: int, **_: Any) -> Knot:
        return _inner_double(x=x, _config=KnotConfig(id="inner"))


def _extra(result: RunResult, knot_id: str) -> dict[str, Any]:
    """Return the lineage ``extra`` recorded for ``knot_id`` in this run."""
    for row in result.lineage:
        if row.knot_id == knot_id:
            return row.extra
    raise AssertionError(f"no lineage row for {knot_id!r} in run {result.run_id}")


class SubTapestryLineageTests(unittest.IsolatedAsyncioTestCase):
    """``inner_run_id`` must name *this* run's child run."""

    async def test_concurrent_runs_record_distinct_inner_run_ids(self):
        with Tapestry() as t:
            p = Parameter("x", int)
            sub = _Doubler(x=p, _config=KnotConfig(id="sub"))

        requests = [RunRequest(parameters={"x": n}) for n in range(6)]
        results = await asyncio.gather(*(t.run(r, terminals=sub) for r in requests))

        assert all(r.succeeded for r in results)
        inner_ids = [_extra(r, "sub")["inner_run_id"] for r in results]
        assert len(set(inner_ids)) == len(results), (
            f"{len(set(inner_ids))} distinct inner_run_id out of {len(results)}: {inner_ids}"
        )

    async def test_recorded_inner_run_id_names_a_run_that_produced_this_output(self):
        """A wrong ``inner_run_id`` still looks plausible; tie it to the output.

        The child run's own lineage is written to the same history, so the
        recorded id must lead to the inner run that actually computed this
        run's answer.
        """
        with Tapestry() as t:
            p = Parameter("x", int)
            sub = _Doubler(x=p, _config=KnotConfig(id="sub"))

        submitted = (1, 2, 3, 4, 5, 6)
        requests = [RunRequest(parameters={"x": n}) for n in submitted]
        results = await asyncio.gather(*(t.run(r, terminals=sub) for r in requests))

        for result, n in zip(results, submitted, strict=True):
            inner_run_id = _extra(result, "sub")["inner_run_id"]
            inner = await t.history.get_run(inner_run_id)
            assert inner is not None, f"inner run {inner_run_id} not recorded"
            assert inner.outputs["inner"] == n * 2, (
                f"run for x={n} points at an inner run that produced "
                f"{inner.outputs['inner']}, not {n * 2}"
            )


class FanOutLineageTests(unittest.IsolatedAsyncioTestCase):
    """``element_count`` must describe *this* run's collection."""

    def setUp(self) -> None:
        global _barrier
        _barrier = None

    def tearDown(self) -> None:
        global _barrier
        _barrier = None

    @staticmethod
    def _arm(total_elements: int) -> None:
        global _barrier
        _barrier = asyncio.Barrier(total_elements)

    async def test_concurrent_map_runs_record_their_own_element_count(self):
        with Tapestry() as t:
            p = Parameter("items", list)
            src = _identity(value=p, _config=KnotConfig(id="src"))
            mapped = _per_element(item=Map(src), _config=KnotConfig(id="mapped"))

        sizes = (1, 5, 9, 13)
        self._arm(sum(sizes))
        requests = [RunRequest(parameters={"items": list(range(n))}) for n in sizes]
        results = await asyncio.gather(*(t.run(r, terminals=mapped) for r in requests))

        assert all(r.succeeded for r in results)
        # The outputs are correct even when the lineage is not -- that is the
        # trap this test exists to catch.
        assert [len(r.outputs["mapped"]) for r in results] == list(sizes)
        counts = [_extra(r, "mapped")["element_count"] for r in results]
        assert counts == list(sizes), f"lineage element_count {counts}, expected {list(sizes)}"

    async def test_concurrent_zip_map_runs_record_their_own_element_count(self):
        with Tapestry() as t:
            p = Parameter("items", list)
            src = _identity(value=p, _config=KnotConfig(id="src"))
            mapped = _pair(left=ZipMap(src), right=ZipMap(src), _config=KnotConfig(id="zipped"))

        sizes = (1, 5, 9, 13)
        self._arm(sum(sizes))
        requests = [RunRequest(parameters={"items": list(range(n))}) for n in sizes]
        results = await asyncio.gather(*(t.run(r, terminals=mapped) for r in requests))

        counts = [_extra(r, "zipped")["element_count"] for r in results]
        assert counts == list(sizes)
        assert [_extra(r, "zipped")["map_type"] for r in results] == ["zip_map"] * len(sizes)

    async def test_concurrent_dict_map_runs_record_their_own_dict_keys(self):
        with Tapestry() as t:
            p = Parameter("mapping", dict)
            src = _identity(value=p, _config=KnotConfig(id="src"))
            mapped = _entry(key=DictMap(src), value=DictMap(src), _config=KnotConfig(id="entries"))

        payloads = [{f"k{i}": i for i in range(n)} for n in (1, 5, 9, 13)]
        self._arm(sum(len(p) for p in payloads))
        requests = [RunRequest(parameters={"mapping": p}) for p in payloads]
        results = await asyncio.gather(*(t.run(r, terminals=mapped) for r in requests))

        recorded = [_extra(r, "entries")["dict_keys"] for r in results]
        assert recorded == [list(p) for p in payloads]


class ThreadDispatcherLineageTests(unittest.IsolatedAsyncioTestCase):
    """The state has to survive the dispatcher's ``copy_context()`` thread hop.

    ``ThreadDispatcher`` hands the knot to a worker thread in the same
    process, so the engine and the knot share the instance and the metadata
    still travels on it.  Pinned because a fix that moved the state into a
    ContextVar set inside the dispatched coroutine would be invisible to the
    engine reading it back.
    """

    async def test_concurrent_sub_tapestry_runs_record_distinct_inner_run_ids(self):
        from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher

        with Tapestry() as t:
            p = Parameter("x", int)
            sub = _Doubler(x=p, _config=KnotConfig(id="sub"))

        dispatcher = ThreadDispatcher()
        try:
            requests = [RunRequest(parameters={"x": n}) for n in range(6)]
            results = await asyncio.gather(
                *(t.run(r, terminals=sub, dispatcher=dispatcher) for r in requests)
            )
        finally:
            dispatcher.shutdown()

        assert all(r.succeeded for r in results)
        inner_ids = [_extra(r, "sub")["inner_run_id"] for r in results]
        assert len(set(inner_ids)) == len(results), inner_ids


class BranchLineageTests(unittest.IsolatedAsyncioTestCase):
    """``selected_branch`` must name the branch *this* run routed to."""

    async def test_concurrent_runs_record_their_own_selected_branch(self):
        with Tapestry() as t:
            p = Parameter("name", str)
            src = _identity(value=p, _config=KnotConfig(id="src"))
            br = Branch(
                input=src,
                selector=lambda v: str(v),
                branches=("a", "b", "c", "d"),
                _config=KnotConfig(id="br"),
            )
            sinks = [
                _identity(value=br[name], _config=KnotConfig(id=f"sink-{name}"))
                for name in ("a", "b", "c", "d")
            ]

        chosen = ("a", "b", "c", "d")
        requests = [RunRequest(parameters={"name": c}) for c in chosen]
        results = await asyncio.gather(*(t.run(r, terminals=sinks) for r in requests))

        recorded = [_extra(r, "br")["selected_branch"] for r in results]
        assert recorded == list(chosen), f"lineage selected_branch {recorded}"
        # Routing itself was always right; only the record was wrong.
        for result, name in zip(results, chosen, strict=True):
            assert result.outputs[f"sink-{name}"] == name


class GateLineageTests(unittest.IsolatedAsyncioTestCase):
    """``predicate_passed`` must describe *this* run's predicate outcome."""

    async def test_concurrent_runs_record_their_own_predicate_outcome(self):
        with Tapestry() as t:
            p = Parameter("n", int)
            src = _identity(value=p, _config=KnotConfig(id="src"))
            g = Gate(
                input=src,
                predicate=lambda v: bool(v % 2),
                _config=KnotConfig(id="g"),
            )
            sink = _identity(value=g, _config=KnotConfig(id="sink"))

        submitted = (1, 2, 3, 4, 5, 6)
        requests = [RunRequest(parameters={"n": n}) for n in submitted]
        results = await asyncio.gather(*(t.run(r, terminals=sink) for r in requests))

        recorded = [_extra(r, "g")["predicate_passed"] for r in results]
        assert recorded == [bool(n % 2) for n in submitted], f"lineage predicate_passed {recorded}"


class SharedGraphIsNotMutatedTests(unittest.IsolatedAsyncioTestCase):
    """A run must leave the shared graph knots exactly as it found them.

    Even without concurrency, writing run-derived state onto the shared knot
    leaves it there for the *next* run to read -- and for a knot that does not
    dispatch at all in that run, the stale value is what lineage reports.
    """

    async def test_a_run_leaves_no_lineage_state_on_the_shared_sub_tapestry(self):
        with Tapestry() as t:
            p = Parameter("x", int, default=1)
            sub = _Doubler(x=p, _config=KnotConfig(id="sub"))

        await t.run(RunRequest(), terminals=sub)

        assert sub.lineage_extra() == {}

    async def test_a_run_leaves_no_lineage_state_on_the_shared_gate(self):
        with Tapestry() as t:
            p = Parameter("n", int, default=1)
            src = _identity(value=p, _config=KnotConfig(id="src"))
            g = Gate(input=src, predicate=bool, _config=KnotConfig(id="g"))

        await t.run(RunRequest(), terminals=g)

        assert g.lineage_extra() == {}

    async def test_a_run_leaves_no_lineage_state_on_the_shared_mapped_knot(self):
        with Tapestry() as t:
            p = Parameter("items", list, default=[1, 2, 3])
            src = _identity(value=p, _config=KnotConfig(id="src"))
            mapped = _per_element(item=Map(src), _config=KnotConfig(id="mapped"))

        await t.run(RunRequest(), terminals=mapped)

        assert mapped.lineage_extra() == {}


class RunScopedCopyTests(unittest.TestCase):
    """Pin the properties the engine's id-keyed bookkeeping relies on.

    The copy stands in for the graph knot for the length of one dispatch, so
    it has to be indistinguishable to everything keyed by ``knot_id`` while
    owning its own mutable state.
    """

    def test_the_copy_keeps_the_knot_id(self):
        """Results, handles, status and lineage are all keyed by knot_id."""
        with Tapestry():
            p = Parameter("x", int, default=1)
            k = _identity(value=p, _config=KnotConfig(id="k"))

        assert k.run_scoped_copy().knot_id == k.knot_id

    def test_the_copy_keeps_config_and_parents(self):
        """``_decide`` and ``_record_lineage`` both read these off the knot."""
        with Tapestry():
            p = Parameter("x", int, default=1)
            k = _identity(value=p, _config=KnotConfig(id="k"))

        clone = k.run_scoped_copy()

        assert clone.config is k.config
        assert clone.parents == k.parents

    def test_the_copy_is_the_same_class(self):
        """Lineage records ``knot_class`` from ``type(knot)``."""
        with Tapestry():
            g = Gate(
                input=_identity(value=1, _config=KnotConfig(id="src")),
                predicate=bool,
                _config=KnotConfig(id="g"),
            )

        assert type(g.run_scoped_copy()) is Gate

    def test_writing_lineage_state_on_the_copy_does_not_reach_the_original(self):
        """The whole point: the slot the four sites write to must be per-copy."""
        with Tapestry():
            p = Parameter("x", int, default=1)
            k = _identity(value=p, _config=KnotConfig(id="k"))
        clone = k.run_scoped_copy()

        clone._mutable_fan_out_extra = {"map_type": "map", "element_count": 7}

        assert k.lineage_extra() == {}
        assert clone.lineage_extra() == {"map_type": "map", "element_count": 7}

    def test_the_copy_does_not_register_with_the_tapestry(self):
        """It belongs to one dispatch, not to the graph."""
        with Tapestry() as t:
            p = Parameter("x", int, default=1)
            k = _identity(value=p, _config=KnotConfig(id="k"))
        before = len(t._store.all())

        k.run_scoped_copy()

        assert len(t._store.all()) == before
