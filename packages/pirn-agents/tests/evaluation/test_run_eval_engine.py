"""``RunEval.run`` on the engine: per-item knots, a concurrency group, core replay (PIR-872).

Each dataset item is one knot bounded by a ``ConcurrencyLimits`` group cap; the
report keeps dataset order however items finish; a recorded eval replays through
core ``ReplaySession`` without calling the target, and a replay that does not
describe the evaluation refuses rather than serving stale results.
"""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Mapping
from typing import Any

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession

from pirn_agents.evaluation.eval_dataset import EvalDataset
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.exact_match import ExactMatch
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.metric_threshold import MetricThreshold
from pirn_agents.evaluation.run_eval import RunEval
from pirn_agents.evaluation.threshold_config import ThresholdConfig
from pirn_agents.exceptions.eval_run_error import EvalRunError


def _dataset(count: int = 2) -> EvalDataset:
    answers = ("Paris", "Tokyo", "Rome", "Lima", "Oslo", "Bern")
    return EvalDataset(
        items=tuple(
            EvalItem(item_id=f"q{i}", input={"q": answers[i]}, expected={"answer": answers[i]})
            for i in range(count)
        )
    )


class _CountingTarget:
    """Echoes the question as the answer; counts live calls and peak concurrency.

    With ``hold`` set, each call waits inside its critical section until
    ``hold`` calls are in flight with it (or every expected call has started),
    so a cap that admits too few times out and one that admits too many shows
    in ``peak`` -- the measurement does not depend on scheduling luck.
    """

    def __init__(
        self,
        *,
        delays: Mapping[str, float] | None = None,
        hold: int | None = None,
        total: int = 0,
    ) -> None:
        self.calls = 0
        self.in_flight = 0
        self.peak = 0
        self._delays = dict(delays or {})
        self._hold = hold
        self._total = total
        self._cond: asyncio.Condition | None = None

    def _may_leave(self) -> bool:
        assert self._hold is not None
        return self.in_flight >= self._hold or self.calls >= self._total

    async def __call__(self, item_input: Mapping[str, Any]) -> Mapping[str, Any]:
        if self._cond is None:
            self._cond = asyncio.Condition()
        async with self._cond:
            self.calls += 1
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            self._cond.notify_all()
            if self._hold is not None:
                await asyncio.wait_for(self._cond.wait_for(self._may_leave), timeout=10)
        await asyncio.sleep(self._delays.get(str(item_input["q"]), 0))
        async with self._cond:
            self.in_flight -= 1
            self._cond.notify_all()
        return {"answer": item_input["q"]}


class _Metrics:
    @staticmethod
    def exact(item: EvalItem, output: Mapping[str, Any]) -> MetricResult:
        return ExactMatch().score(str(output["answer"]), str(item.expected["answer"]))

    @staticmethod
    def length(item: EvalItem, output: Mapping[str, Any]) -> MetricResult:
        return MetricResult(name="length", score=float(len(str(output["answer"]))))


class _FailingTarget:
    async def __call__(self, item_input: Mapping[str, Any]) -> Mapping[str, Any]:
        raise RuntimeError(f"target down for {item_input['q']}")


class TestItemsRunOnTheEngine(unittest.IsolatedAsyncioTestCase):
    async def test_the_concurrency_cap_bounds_in_flight_items(self) -> None:
        target = _CountingTarget(hold=2, total=6)
        report = await RunEval.run(
            dataset=_dataset(6), target=target, metrics={"em": _Metrics.exact}, concurrency=2
        )
        assert target.calls == 6
        assert target.peak == 2
        assert report.metric("em") == 1.0

    async def test_dataset_order_survives_out_of_order_completion(self) -> None:
        target = _CountingTarget(delays={"Paris": 0.05, "Tokyo": 0.0, "Rome": 0.02})
        report = await RunEval.run(
            dataset=_dataset(3), target=target, metrics={"em": _Metrics.exact}
        )
        assert [r.item_id for r in report.results] == ["q0", "q1", "q2"]

    async def test_every_item_has_its_own_lineage_row(self) -> None:
        history = InMemoryHistory()
        await RunEval.run(
            dataset=_dataset(3),
            target=_CountingTarget(),
            metrics={"em": _Metrics.exact},
            history=history,
            run_id="eval-1",
        )
        run = await history.get_run("eval-1")
        assert run is not None
        ids = {row.knot_id for row in run.lineage}
        assert {"eval_item_0", "eval_item_1", "eval_item_2", "eval_report"} <= ids

    async def test_an_empty_dataset_is_an_empty_report(self) -> None:
        target = _CountingTarget()
        report = await RunEval.run(dataset=EvalDataset(), target=target, metrics={})
        assert report.results == ()
        assert target.calls == 0

    async def test_a_failing_item_raises_naming_it(self) -> None:
        with self.assertRaises(EvalRunError) as caught:
            await RunEval.run(
                dataset=_dataset(2), target=_FailingTarget(), metrics={"em": _Metrics.exact}
            )
        assert "eval_item_0" in str(caught.exception)
        assert "target down" in str(caught.exception)

    async def test_concurrency_below_one_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            await RunEval.run(
                dataset=_dataset(1), target=_CountingTarget(), metrics={}, concurrency=0
            )


class TestARecordedEvalReplays(unittest.IsolatedAsyncioTestCase):
    async def _record(self) -> tuple[InMemoryHistory, InMemoryDataStore, Any]:
        history = InMemoryHistory()
        store = InMemoryDataStore()
        target = _CountingTarget()
        report = await RunEval.run(
            dataset=_dataset(2),
            target=target,
            metrics={"em": _Metrics.exact},
            history=history,
            data_store=store,
            run_id="recorded",
        )
        assert target.calls == 2
        return history, store, report

    async def test_replay_serves_every_item_without_calling_the_target(self) -> None:
        # Arrange
        history, store, recorded = await self._record()
        session = await ReplaySession.from_history(history=history, run_id="recorded")
        fresh_target = _CountingTarget()

        # Act
        replayed = await RunEval.run(
            dataset=_dataset(2),
            target=fresh_target,
            metrics={"em": _Metrics.exact},
            history=history,
            data_store=store,
            replay=session,
        )

        # Assert
        assert fresh_target.calls == 0
        assert replayed.to_json() == recorded.to_json()

    async def test_a_replay_with_different_metrics_is_refused(self) -> None:
        history, store, _ = await self._record()
        session = await ReplaySession.from_history(history=history, run_id="recorded")
        with self.assertRaises(ReplayMismatchError):
            await RunEval.run(
                dataset=_dataset(2),
                target=_CountingTarget(),
                metrics={"em": _Metrics.exact, "length": _Metrics.length},
                history=history,
                data_store=store,
                replay=session,
            )

    async def test_a_replay_with_different_thresholds_is_refused(self) -> None:
        history, store, _ = await self._record()
        session = await ReplaySession.from_history(history=history, run_id="recorded")
        floors = ThresholdConfig(thresholds=[MetricThreshold(metric="em", min_score=1.0)])
        with self.assertRaises(ReplayMismatchError):
            await RunEval.run(
                dataset=_dataset(2),
                target=_CountingTarget(),
                metrics={"em": _Metrics.exact},
                thresholds=floors,
                history=history,
                data_store=store,
                replay=session,
            )

    async def test_a_replay_of_a_changed_item_is_refused(self) -> None:
        history, store, _ = await self._record()
        session = await ReplaySession.from_history(history=history, run_id="recorded")
        changed = EvalDataset(
            items=(
                EvalItem(item_id="q0", input={"q": "Lyon"}, expected={"answer": "Paris"}),
                _dataset(2).items[1],
            )
        )
        with self.assertRaises(ReplayMismatchError):
            await RunEval.run(
                dataset=changed,
                target=_CountingTarget(),
                metrics={"em": _Metrics.exact},
                history=history,
                data_store=store,
                replay=session,
            )


if __name__ == "__main__":
    unittest.main()
