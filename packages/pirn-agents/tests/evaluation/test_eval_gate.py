"""Mirrored tests for the CI regression gate (:class:`EvalGate`, S6).

Simulates a passing run and a regressing run against fixture thresholds, plus a
baseline-regression and a missing-metric breach.
"""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.eval_case_result import EvalCaseResult
from pirn_agents.evaluation.eval_gate import EvalGate
from pirn_agents.evaluation.eval_report import EvalReport
from pirn_agents.evaluation.metric_threshold import MetricThreshold
from pirn_agents.evaluation.threshold_config import ThresholdConfig


def _report(*metric_maps: dict[str, float]) -> EvalReport:
    return EvalReport(
        results=tuple(
            EvalCaseResult(item_id=f"i{index}", metrics=metrics)
            for index, metrics in enumerate(metric_maps)
        )
    )


def _thresholds() -> ThresholdConfig:
    return ThresholdConfig(
        thresholds=[
            MetricThreshold(metric="faithfulness", min_score=0.8),
            MetricThreshold(metric="answer_relevance", min_score=0.7),
        ]
    )


class EvalGateTests(unittest.TestCase):
    def test_passing_run_clears_the_gate(self) -> None:
        report = _report(
            {"faithfulness": 0.9, "answer_relevance": 0.8},
            {"faithfulness": 0.85, "answer_relevance": 0.75},
        )
        result = EvalGate(thresholds=_thresholds()).check(report)
        assert result.passed is True
        assert result.breaches == ()
        assert "PASSED" in result.to_markdown()

    def test_regressing_run_fails_below_threshold(self) -> None:
        # answer_relevance mean = 0.5 < 0.7
        report = _report({"faithfulness": 0.9, "answer_relevance": 0.5})
        result = EvalGate(thresholds=_thresholds()).check(report)
        assert result.passed is False
        breach = next(b for b in result.breaches if b["metric"] == "answer_relevance")
        assert breach["kind"] == "threshold"
        assert breach["actual"] == 0.5
        assert breach["limit"] == 0.7
        assert "FAILED" in result.to_markdown()

    def test_missing_metric_is_a_breach(self) -> None:
        report = _report({"faithfulness": 0.9})
        result = EvalGate(thresholds=_thresholds()).check(report)
        assert result.passed is False
        assert any(b["kind"] == "missing" for b in result.breaches)

    def test_baseline_regression_detected_even_above_threshold(self) -> None:
        thresholds = ThresholdConfig(
            thresholds=[MetricThreshold(metric="faithfulness", min_score=0.5)]
        )
        baseline = _report({"faithfulness": 0.95})
        current = _report({"faithfulness": 0.8})  # above floor but below baseline
        result = EvalGate(thresholds=thresholds).check(current, baseline=baseline)
        assert result.passed is False
        breach = next(b for b in result.breaches if b["kind"] == "regression")
        assert breach["actual"] == 0.8
        assert breach["limit"] == 0.95

    def test_no_regression_when_current_meets_baseline(self) -> None:
        thresholds = ThresholdConfig(
            thresholds=[MetricThreshold(metric="faithfulness", min_score=0.5)]
        )
        baseline = _report({"faithfulness": 0.8})
        current = _report({"faithfulness": 0.85})
        result = EvalGate(thresholds=thresholds).check(current, baseline=baseline)
        assert result.passed is True

    def test_gate_result_json_has_breaches(self) -> None:
        report = _report({"faithfulness": 0.1, "answer_relevance": 0.1})
        result = EvalGate(thresholds=_thresholds()).check(report)
        import json

        loaded = json.loads(result.to_json())
        assert loaded["passed"] is False
        assert len(loaded["breaches"]) == 2

    def test_non_report_raises(self) -> None:
        with self.assertRaises(TypeError):
            EvalGate(thresholds=_thresholds()).check("not-a-report")  # type: ignore[arg-type]

    def test_non_threshold_config_raises(self) -> None:
        with self.assertRaises(TypeError):
            EvalGate(thresholds=object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
