"""Unit tests for SubTapestry and SubTapestryError."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.managers.exception_record import ExceptionRecord
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.nodes.sub_tapestry_error import SubTapestryError
from pirn.tapestry import Tapestry


def _make_failed_result() -> RunResult:
    exc = ExceptionRecord(
        run_id="r",
        knot_id="fail",
        exc_type="RuntimeError",
        message="inner failure",
        traceback_text="",
    )
    return RunResult(
        run_id="r",
        terminals_requested=["fail"],
        outputs={},
        exceptions=[exc],
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        dispatcher="local",
    )


class TestSubTapestryError(unittest.TestCase):
    def test_message_includes_exception_count_and_run_id(self) -> None:
        result = _make_failed_result()
        err = SubTapestryError(result)
        self.assertIn("1", str(err))
        self.assertIn("r", str(err))

    def test_inner_result_accessible(self) -> None:
        result = _make_failed_result()
        err = SubTapestryError(result)
        self.assertIs(err.inner_result, result)


class _DoubleSource(Source):
    async def process(self, **_: Any) -> int:
        return 21


class _InnerPipeline(SubTapestry):
    async def process(self, upstream: Any, **_: Any) -> Any:
        from pirn.nodes.source import Source as _Source

        class _PassThrough(_Source):
            async def process(self, **_kw: Any) -> Any:
                return upstream * 2

        return _PassThrough(_config=KnotConfig(id="pt"))


class TestSubTapestryProcess(unittest.IsolatedAsyncioTestCase):
    async def test_run_inner_runs_inner_tapestry(self) -> None:
        with Tapestry() as t:
            src = _DoubleSource(_config=KnotConfig(id="src"))
            _InnerPipeline(upstream=src, _config=KnotConfig(id="pipeline"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["pipeline"], 42)

    async def test_base_process_raises_not_implemented(self) -> None:
        class _Bare(SubTapestry):
            pass

        with Tapestry() as t:
            src = _DoubleSource(_config=KnotConfig(id="src2"))
            _Bare(upstream=src, _config=KnotConfig(id="bare"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)


class _Leaf(Source):
    async def process(self, **_: Any) -> int:
        return 42


class _Depth2(SubTapestry):
    """A pipeline constructed inside _Depth1.process() — the nesting that broke."""

    async def process(self, **_: Any) -> Any:
        return _Leaf(_config=KnotConfig(id="leaf"))


class _Depth1(SubTapestry):
    async def process(self, **_: Any) -> Any:
        return _Depth2(_config=KnotConfig(id="l2"))


class TestNestedSubTapestryHistory(unittest.IsolatedAsyncioTestCase):
    """A SubTapestry nested inside another SubTapestry's process() must record.

    Before PIR-764 the depth-2 pipeline captured its history at construction
    time from the ambient tapestry — which, inside a parent's process(), is the
    throwaway ``with Tapestry() as inner:`` that __call__ opens. That store is
    discarded when the parent's inner run ends, so everything below depth 2
    vanished while the run still reported success with the right answer.

    A plain Knot at depth 1 was always recorded; only pipeline-in-pipeline
    nesting was affected. Both bounds are asserted here.
    """

    async def _run(self) -> tuple[Any, Any]:
        from pirn.backends.in_memory.in_memory_history import InMemoryHistory

        history = InMemoryHistory()
        with Tapestry(history=history) as outer:
            _Depth1(_config=KnotConfig(id="l1"))
        return await outer.run(RunRequest()), history

    async def test_depth_two_inner_run_is_recorded(self) -> None:
        result, history = await self._run()
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["l1"], 42)

        depth1 = await history.children_of(result.run_id)
        self.assertEqual([c.parent_knot_id for c in depth1], ["l1"])
        depth2 = await history.children_of(depth1[0].run_id)
        self.assertEqual([c.parent_knot_id for c in depth2], ["l2"])

    async def test_leaf_below_the_nested_pipeline_has_lineage(self) -> None:
        _, history = await self._run()
        self.assertEqual(len(await history.query_lineage_by_knot_id("l1")), 1)
        self.assertEqual(len(await history.query_lineage_by_knot_id("l2")), 1)
        self.assertEqual(len(await history.query_lineage_by_knot_id("leaf")), 1)


class _Flaky(SubTapestry):
    """Succeeds or fails depending on a mutable flag, to exercise reuse."""

    should_fail = False

    async def process(self, **_: Any) -> Any:
        if type(self).should_fail:

            class _Boom(Source):
                async def process(self, **_kw: Any) -> Any:
                    raise RuntimeError("inner blew up")

            return _Boom(_config=KnotConfig(id="boom"))
        return _Leaf(_config=KnotConfig(id="ok_leaf"))


class TestInnerRunMetaOnFailure(unittest.IsolatedAsyncioTestCase):
    """A failed inner run must not report the previous run's inner_run_id."""

    @staticmethod
    def _recorded_meta(result: RunResult, knot_id: str) -> dict[str, Any]:
        """Return the lineage ``extra`` the engine recorded for ``knot_id``.

        Read from the run's lineage rather than from the knot instance: since
        PIR-809 the engine dispatches a per-run copy, so the shared graph knot
        carries no run state for either run to inspect.  The lineage record is
        where this metadata was always headed anyway.
        """
        for row in result.lineage:
            if row.knot_id == knot_id:
                return row.extra
        raise AssertionError(f"no lineage row for {knot_id!r}")

    async def test_failure_does_not_inherit_the_previous_runs_meta(self) -> None:
        _Flaky.should_fail = False
        try:
            with Tapestry() as t:
                _Flaky(_config=KnotConfig(id="flaky"))
            ok_run = await t.run(RunRequest())
            self.assertTrue(ok_run.succeeded)
            first_inner_id = self._recorded_meta(ok_run, "flaky")["inner_run_id"]

            _Flaky.should_fail = True
            fail_run = await t.run(RunRequest())
            self.assertFalse(fail_run.succeeded)
            meta = self._recorded_meta(fail_run, "flaky")
            # Populated, and pointing at the run that actually failed.
            self.assertIn("inner_run_id", meta)
            self.assertNotEqual(meta["inner_run_id"], first_inner_id)
            self.assertEqual(meta["inner_failures"], 1)
        finally:
            _Flaky.should_fail = False

    async def test_the_shared_knot_carries_no_inner_run_meta_after_a_run(self) -> None:
        """The reset in ``__call__`` protects the copy; the graph knot stays clean.

        Pins that the staleness PIR-764 fixed cannot come back through the
        shared instance either -- there is nothing on it to go stale.
        """
        _Flaky.should_fail = False
        with Tapestry() as t:
            knot = _Flaky(_config=KnotConfig(id="flaky"))
        await t.run(RunRequest())

        self.assertEqual(knot.lineage_extra(), {})


class _GatedSink(SubTapestry):
    """Inner pipeline whose sink sits behind a ``Gate`` that ``open`` decides."""

    async def process(self, open: bool, **_: Any) -> Any:
        from pirn.nodes.gate.gate import Gate

        class _Value(Source):
            async def process(self, **_kw: Any) -> int:
                return 7

        value = _Value(_config=KnotConfig(id="value"))
        return Gate(input=value, predicate=lambda _v: open, _config=KnotConfig(id="gate"))


class TestSkippedSinkPassesThrough(unittest.IsolatedAsyncioTestCase):
    """A sink the inner run skipped makes the container ``Skipped``, not ``Err``."""

    async def test_open_gate_surfaces_the_value(self) -> None:
        with Tapestry() as t:
            _GatedSink(open=True, _config=KnotConfig(id="outer"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["outer"], 7)

    async def test_closed_gate_skips_the_container_with_the_sinks_reason(self) -> None:
        with Tapestry() as t:
            _GatedSink(open=False, _config=KnotConfig(id="outer"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertIn("outer", result.skipped)
        self.assertNotIn("outer", result.outputs)
        row = next(r for r in result.lineage if r.knot_id == "outer")
        self.assertEqual(row.outcome, "skipped")
        self.assertEqual(row.skip_reason, "gate_closed")


class _CappedNesting(SubTapestry):
    """Chooses its own inner tapestry: a nesting cap the outer run never set."""

    def _make_inner_tapestry(self) -> Tapestry:
        return Tapestry(max_nesting_depth=1)

    async def process(self, **_: Any) -> Any:
        return _Depth2(_config=KnotConfig(id="deeper"))


class TestMakeInnerTapestrySeam(unittest.IsolatedAsyncioTestCase):
    """``_make_inner_tapestry`` lets a container configure the run it starts."""

    async def test_default_is_a_bare_tapestry(self) -> None:
        with Tapestry():
            knot = _InnerPipeline(
                upstream=_DoubleSource(_config=KnotConfig(id="s")), _config=KnotConfig(id="p")
            )
        inner = knot._make_inner_tapestry()
        self.assertIsInstance(inner, Tapestry)
        self.assertIsNone(inner.max_nesting_depth)

    async def test_override_reaches_the_inner_run(self) -> None:
        """The cap set by the override refuses the deeper run, as a normal Err."""
        with Tapestry() as t:
            _CappedNesting(_config=KnotConfig(id="capped"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
        self.assertEqual([rec.exc_type for rec in result.exceptions], ["SubTapestryError"])
        inner_runs = await t.history.children_of(result.run_id)
        inner_types = {rec.exc_type for run in inner_runs for rec in run.exceptions}
        self.assertIn("NestingDepthExceededError", inner_types)


class _Explodes(Source):
    async def process(self, **_: Any) -> int:
        raise RuntimeError("boom")


class _CombinesFailures(SubTapestry):
    """Sink receives the failed knot's ``Err`` and reports it as a value."""

    _inner_failures_reach_sink = True

    async def process(self, **_: Any) -> Any:
        from pirn.core.error_policy import ErrorPolicy
        from pirn.nodes.aggregator import Aggregator

        bad = _Explodes(_config=KnotConfig(id="bad"))
        return Aggregator(
            combine=lambda bad: bad.record.exc_type,
            bad=bad,
            _config=KnotConfig(id="report", error_policy=ErrorPolicy.RECEIVE_ERRORS),
        )


class _DoesNotCombineFailures(_CombinesFailures):
    _inner_failures_reach_sink = False


class TestInnerFailuresReachSink(unittest.IsolatedAsyncioTestCase):
    async def test_opted_in_container_surfaces_the_sinks_value(self) -> None:
        with Tapestry() as t:
            _CombinesFailures(_config=KnotConfig(id="outer"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(result.outputs["outer"], "RuntimeError")
        inner_runs = await t.history.children_of(result.run_id)
        self.assertEqual(
            {rec.exc_type for run in inner_runs for rec in run.exceptions}, {"RuntimeError"}
        )

    async def test_default_container_fails_on_an_inner_failure(self) -> None:
        with Tapestry() as t:
            _DoesNotCombineFailures(_config=KnotConfig(id="outer"))
        result = await t.run(RunRequest())
        self.assertFalse(result.succeeded)
        self.assertEqual([rec.exc_type for rec in result.exceptions], ["SubTapestryError"])
