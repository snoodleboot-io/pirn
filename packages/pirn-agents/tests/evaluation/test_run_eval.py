"""End-to-end mirrored test for :func:`run_eval` over a small fixture dataset.

Drives the runner with a target backed by a :class:`ScriptedJudgeProvider` stub
(no real model I/O), core + judge metrics, and thresholds, asserting the emitted
report, aggregates, and per-item pass/fail.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn_agents.evaluation.eval_dataset import EvalDataset
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.exact_match import ExactMatch
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.metric_threshold import MetricThreshold
from pirn_agents.evaluation.null_run_recorder import NullRunRecorder
from pirn_agents.evaluation.run_eval import run_eval
from pirn_agents.evaluation.threshold_config import ThresholdConfig
from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from tests.evaluation.evaluation_doubles import ScriptedJudgeProvider


def _dataset() -> EvalDataset:
    return EvalDataset(
        items=[
            EvalItem(item_id="q1", input={"q": "capital of france"}, expected={"answer": "Paris"}),
            EvalItem(item_id="q2", input={"q": "2+2"}, expected={"answer": "4"}),
        ]
    )


class RunEvalTests(unittest.IsolatedAsyncioTestCase):
    async def test_end_to_end_scores_and_aggregates(self) -> None:
        # A target backed by a stub provider: it returns the scripted content
        # as the produced answer, so there is no real model I/O.
        provider = ScriptedJudgeProvider(["Paris", "5"])

        async def target(item_input: Mapping[str, Any]) -> Mapping[str, Any]:
            reply = await provider.chat([{"role": "user", "content": str(item_input["q"])}])
            return {"answer": str(reply.get("content", ""))}

        def em(item: EvalItem, output: Mapping[str, Any]) -> MetricResult:
            return ExactMatch().score(str(output["answer"]), str(item.expected["answer"]))

        report = await run_eval(dataset=_dataset(), target=target, metrics={"exact_match": em})

        assert [r.item_id for r in report.results] == ["q1", "q2"]
        # q1 answered "Paris" (correct), q2 answered "5" (wrong "4")
        assert report.results[0].metrics["exact_match"] == 1.0
        assert report.results[1].metrics["exact_match"] == 0.0
        assert report.metric("exact_match") == 0.5

    async def test_thresholds_set_per_item_pass_fail(self) -> None:
        provider = ScriptedJudgeProvider(["Paris", "5"])

        async def target(item_input: Mapping[str, Any]) -> Mapping[str, Any]:
            reply = await provider.chat([{"role": "user", "content": str(item_input["q"])}])
            return {"answer": str(reply.get("content", ""))}

        def em(item: EvalItem, output: Mapping[str, Any]) -> MetricResult:
            return ExactMatch().score(str(output["answer"]), str(item.expected["answer"]))

        thresholds = ThresholdConfig(
            thresholds=[MetricThreshold(metric="exact_match", min_score=1.0)]
        )
        report = await run_eval(
            dataset=_dataset(),
            target=target,
            metrics={"exact_match": em},
            thresholds=thresholds,
        )
        assert report.results[0].passed is True
        assert report.results[1].passed is False
        assert report.results[1].detail["breaches"][0]["metric"] == "exact_match"
        assert report.passed is False

    async def test_async_metric_and_custom_concurrency_and_recorder(self) -> None:
        async def target(item_input: Mapping[str, Any]) -> Mapping[str, Any]:
            return {"answer": str(item_input["q"])}

        async def async_metric(item: EvalItem, output: Mapping[str, Any]) -> MetricResult:
            return MetricResult(name="len", score=float(len(output["answer"])))

        report = await run_eval(
            dataset=EvalDataset(items=[EvalItem(item_id="x", input={"q": "abcd"})]),
            target=target,
            metrics={"len": async_metric},
            concurrency=ConcurrencyConfig(max_concurrency=2),
            recorder=NullRunRecorder(),
        )
        assert report.results[0].metrics["len"] == 4.0
        assert report.results[0].passed is None

    async def test_non_dataset_raises(self) -> None:
        async def target(_: Mapping[str, Any]) -> Mapping[str, Any]:
            return {}

        with self.assertRaises(TypeError):
            await run_eval(dataset=[], target=target, metrics={})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
