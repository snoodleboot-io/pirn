"""Tests for :class:`JudgeCalibration` and its value types (S4)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.calibration_report import CalibrationReport
from pirn_agents.evaluation.evaluation_judge import EvaluationJudge
from pirn_agents.evaluation.gold_label import GoldLabel
from pirn_agents.evaluation.judge_calibration import JudgeCalibration
from pirn_agents.evaluation.rubric_criterion import RubricCriterion
from tests.evaluation.evaluation_doubles import ScriptedJudgeProvider


class GoldLabelTests(unittest.TestCase):
    def test_validates_and_normalizes_criteria(self) -> None:
        label = GoldLabel(
            prompt="q",
            response="r",
            criteria=[RubricCriterion(name="c")],
            expected_score=0.5,
        )
        assert isinstance(label.criteria, tuple)
        assert label.expected_score == 0.5

    def test_non_criterion_raises(self) -> None:
        with self.assertRaises(TypeError):
            GoldLabel(prompt="q", response="r", criteria=["x"], expected_score=0.5)  # type: ignore[list-item]


class JudgeCalibrationTests(unittest.IsolatedAsyncioTestCase):
    def _gold(self, expected: float) -> GoldLabel:
        return GoldLabel(
            prompt="q",
            response="r",
            criteria=[RubricCriterion(name="c")],
            expected_score=expected,
        )

    async def test_perfect_agreement_when_judge_matches_gold(self) -> None:
        # judge returns 1.0 for both items; expected 1.0 => zero error, full agreement
        judge = EvaluationJudge(judge=ScriptedJudgeProvider(["1.0", "1.0"]))
        report = await JudgeCalibration(judge=judge).calibrate([self._gold(1.0), self._gold(1.0)])
        assert isinstance(report, CalibrationReport)
        assert report.agreement == 1.0
        assert report.mean_abs_error == 0.0
        assert report.n == 2

    async def test_disagreement_lowers_agreement_and_raises_error(self) -> None:
        # judge says 0.0 but gold expects 1.0 => error 1.0, outside default tolerance
        judge = EvaluationJudge(judge=ScriptedJudgeProvider(["0.0"]))
        report = await JudgeCalibration(judge=judge, tolerance=0.1).calibrate([self._gold(1.0)])
        assert report.agreement == 0.0
        assert report.mean_abs_error == 1.0

    async def test_tolerance_controls_agreement(self) -> None:
        judge = EvaluationJudge(judge=ScriptedJudgeProvider(["0.85"]))
        report = await JudgeCalibration(judge=judge, tolerance=0.2).calibrate([self._gold(1.0)])
        assert report.agreement == 1.0

    async def test_empty_gold_set_is_vacuously_calibrated(self) -> None:
        judge = EvaluationJudge(judge=ScriptedJudgeProvider(["1.0"]))
        report = await JudgeCalibration(judge=judge).calibrate([])
        assert report.agreement == 1.0
        assert report.n == 0

    async def test_report_to_json_roundtrips_fields(self) -> None:
        judge = EvaluationJudge(judge=ScriptedJudgeProvider(["1.0"]))
        report = await JudgeCalibration(judge=judge).calibrate([self._gold(1.0)])
        import json

        loaded = json.loads(report.to_json())
        assert loaded["agreement"] == 1.0
        assert loaded["n"] == 1

    async def test_non_judge_raises(self) -> None:
        with self.assertRaises(TypeError):
            JudgeCalibration(judge=object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
