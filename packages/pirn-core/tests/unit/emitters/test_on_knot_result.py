"""``Emitter.on_knot_result`` — the live per-knot outcome stream (ADR WS0b).

`on_lineage` fires only after the run is persisted, in the run's reported
order, and carries no value; the `Err`'s `ExceptionRecord` was reachable only
from the final `RunResult.exceptions`.  So a consumer of a fan-out — a
`MapAgent` yielding each item as it finishes — had nothing to stream from
until the join completed.  `on_knot_result` fires inside the scheduling loop
the moment each knot settles, with the full `Result` and the lineage row, and
before the knot's children are released.
"""

from __future__ import annotations

import logging
import unittest
from typing import TYPE_CHECKING, Any

from pirn.core.err import Err
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.emitters.emitter import Emitter
from pirn.emitters.emitter_error_policy import EmitterErrorPolicy
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage
    from pirn.core.result import Result
    from pirn.core.run_result import RunResult


class _Recorder(Emitter):
    """Captures every hook call in the order it arrives."""

    def __init__(self) -> None:
        self.settled: list[tuple[str, Result[Any], KnotLineage]] = []
        self.hooks: list[str] = []

    async def on_knot_result(self, knot_id: str, result: Result[Any], lineage: KnotLineage) -> None:
        self.settled.append((knot_id, result, lineage))
        self.hooks.append(f"result:{knot_id}")

    async def on_lineage(self, record: KnotLineage) -> None:
        self.hooks.append(f"lineage:{record.knot_id}")

    async def on_run_result(self, result: RunResult) -> None:
        self.hooks.append("run")

    @property
    def settled_ids(self) -> list[str]:
        return [knot_id for knot_id, _, _ in self.settled]


class _Item(Knot):
    def __init__(self, *, value: int, fail: bool = False, **kwargs: Any) -> None:
        self._value = value
        self._fail = fail
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        if self._fail:
            raise ValueError(f"item {self._value} failed")
        return self._value


class _Snapshot(Knot):
    """Copies the recorder's settled ids at the moment it starts."""

    def __init__(self, *, recorder: _Recorder, seen_on_entry: list[str], **kwargs: Any) -> None:
        self._recorder = recorder
        self._seen_on_entry = seen_on_entry
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> int:
        self._seen_on_entry[:] = self._recorder.settled_ids
        return len(self._seen_on_entry)


class _Sub(SubTapestry):
    async def process(self, **_: Any) -> Knot:
        return _Item(value=9, _config=KnotConfig(id="inner"))


class TestOutcomesStreamAsKnotsSettle(unittest.IsolatedAsyncioTestCase):
    async def test_every_item_of_a_fan_out_arrives_before_the_join_starts(self) -> None:
        # Arrange: three items joined by an aggregator that snapshots what the
        # recorder has seen the moment it starts.
        recorder = _Recorder()
        seen_on_entry: list[str] = []
        with Tapestry(emitters=[recorder]) as t:
            items = {f"p{i}": _Item(value=i, _config=KnotConfig(id=f"item{i}")) for i in range(3)}
            _Snapshot(
                recorder=recorder,
                seen_on_entry=seen_on_entry,
                _config=KnotConfig(id="join"),
                **items,
            )

        # Act
        result = await t.run(RunRequest())

        # Assert: all three items had settled through the hook before the join ran.
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(set(seen_on_entry), {"item0", "item1", "item2"})
        self.assertEqual(recorder.settled_ids[-1], "join")

    async def test_an_ok_carries_the_produced_value(self) -> None:
        recorder = _Recorder()
        with Tapestry(emitters=[recorder]) as t:
            _Item(value=42, _config=KnotConfig(id="item"))
        await t.run(RunRequest())
        (knot_id, outcome, row) = recorder.settled[0]
        self.assertEqual(knot_id, "item")
        assert isinstance(outcome, Ok)
        self.assertEqual(outcome.value, 42)
        self.assertEqual(row.outcome, "ok")
        self.assertEqual(row.knot_id, "item")

    async def test_an_err_carries_the_rebound_exception_record(self) -> None:
        recorder = _Recorder()
        with Tapestry(emitters=[recorder]) as t:
            _Item(value=1, fail=True, _config=KnotConfig(id="bad"))
        result = await t.run(RunRequest())

        (_, outcome, row) = next(entry for entry in recorder.settled if entry[0] == "bad")
        assert isinstance(outcome, Err)
        self.assertEqual(outcome.record.run_id, result.run_id)
        self.assertEqual(outcome.record.exc_type, "ValueError")
        self.assertIn("item 1 failed", outcome.record.message)
        self.assertEqual(row.outcome, "err")
        self.assertEqual(row.error_record_id, outcome.record.id)
        self.assertIn(outcome.record.id, {rec.id for rec in result.exceptions})

    async def test_a_skipped_decision_is_streamed_too(self) -> None:
        # Arrange: a child of a failing parent is skipped without dispatch.
        recorder = _Recorder()
        with Tapestry(emitters=[recorder]) as t:
            bad = _Item(value=1, fail=True, _config=KnotConfig(id="bad"))
            _Item(value=2, x=bad, _config=KnotConfig(id="child"))
        await t.run(RunRequest())

        (_, outcome, row) = next(entry for entry in recorder.settled if entry[0] == "child")
        assert isinstance(outcome, Skipped)
        self.assertEqual(outcome.reason, "parent_failed_or_skipped")
        self.assertEqual(row.outcome, "skipped")

    async def test_receive_errors_items_stream_their_result_before_the_combine(self) -> None:
        # Arrange: the MapAgent shape -- a RECEIVE_ERRORS aggregator over
        # items that may fail.
        recorder = _Recorder()
        with Tapestry(emitters=[recorder]) as t:
            good = _Item(value=1, _config=KnotConfig(id="good"))
            bad = _Item(value=2, fail=True, _config=KnotConfig(id="bad"))
            Aggregator(
                combine=lambda **inputs: sorted(inputs),
                good=good,
                bad=bad,
                _config=KnotConfig(id="agg", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            )
        result = await t.run(RunRequest())

        # The run reports the item's failure (``succeeded`` is False) while the
        # RECEIVE_ERRORS join still produced its combined value.
        self.assertEqual(result.outputs["agg"], ["bad", "good"])
        by_id = {knot_id: outcome for knot_id, outcome, _ in recorder.settled}
        self.assertIsInstance(by_id["good"], Ok)
        self.assertIsInstance(by_id["bad"], Err)
        self.assertLess(recorder.settled_ids.index("bad"), recorder.settled_ids.index("agg"))

    async def test_it_fires_before_the_parent_s_children_are_dispatched(self) -> None:
        recorder = _Recorder()
        seen_on_entry: list[str] = []
        with Tapestry(emitters=[recorder]) as t:
            parent = _Item(value=1, _config=KnotConfig(id="parent"))
            _Snapshot(
                recorder=recorder,
                seen_on_entry=seen_on_entry,
                x=parent,
                _config=KnotConfig(id="child"),
            )
        await t.run(RunRequest())
        self.assertEqual(seen_on_entry, ["parent"])

    async def test_it_fires_before_lineage_and_run_result(self) -> None:
        recorder = _Recorder()
        with Tapestry(emitters=[recorder]) as t:
            _Item(value=1, _config=KnotConfig(id="item"))
        await t.run(RunRequest())
        self.assertEqual(recorder.hooks, ["result:item", "lineage:item", "run"])

    async def test_inner_run_outcomes_reach_the_outer_emitter(self) -> None:
        recorder = _Recorder()
        with Tapestry(emitters=[recorder]) as t:
            _Sub(_config=KnotConfig(id="sub"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        inner = next(entry for entry in recorder.settled if entry[0] == "inner")
        self.assertNotEqual(inner[2].run_id, result.run_id)
        self.assertEqual(recorder.settled_ids[-1], "sub")

    async def test_the_default_hook_is_a_no_op(self) -> None:
        with Tapestry(emitters=[Emitter()]) as t:
            _Item(value=1, _config=KnotConfig(id="item"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)


class _Broken(Emitter):
    async def on_knot_result(self, knot_id: str, result: Result[Any], lineage: KnotLineage) -> None:
        raise RuntimeError(f"broken on {knot_id}")


class TestOnKnotResultHonoursTheEmitterErrorPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_ignore_keeps_the_run_and_the_other_emitters(self) -> None:
        recorder = _Recorder()
        with Tapestry(
            emitters=[_Broken(), recorder], emitter_error_policy=EmitterErrorPolicy.IGNORE
        ) as t:
            _Item(value=1, _config=KnotConfig(id="item"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertEqual(recorder.settled_ids, ["item"])

    async def test_warn_logs_and_continues(self) -> None:
        recorder = _Recorder()
        with Tapestry(
            emitters=[_Broken(), recorder], emitter_error_policy=EmitterErrorPolicy.WARN
        ) as t:
            _Item(value=1, _config=KnotConfig(id="item"))
        with self.assertLogs("pirn.engine.emitter_fanout", level=logging.WARNING) as logs:
            result = await t.run(RunRequest())
        self.assertTrue(result.succeeded, result.exceptions)
        self.assertTrue(any("on_knot_result" in line for line in logs.output), logs.output)
        self.assertEqual(recorder.settled_ids, ["item"])

    async def test_raise_aborts_the_run_with_the_emitter_s_exception(self) -> None:
        with Tapestry(emitters=[_Broken()], emitter_error_policy=EmitterErrorPolicy.RAISE) as t:
            _Item(value=1, _config=KnotConfig(id="item"))
        with self.assertRaises(RuntimeError) as caught:
            await t.run(RunRequest())
        self.assertIn("broken on item", str(caught.exception))
