"""``JudgeCalibration`` — score an :class:`LLMJudge` against a gold set."""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.evaluation.calibration_report import CalibrationReport
from pirn_agents.evaluation.gold_label import GoldLabel
from pirn_agents.evaluation.llm_judge import LLMJudge


class JudgeCalibration:
    """Compare an :class:`LLMJudge`'s rubric scores against human gold labels.

    Runs the judge over each :class:`GoldLabel` and reports how well it tracks
    the reference: the fraction of items within ``tolerance`` (agreement) and the
    mean absolute error. A poorly calibrated judge surfaces as low agreement /
    high error before it is trusted to gate anything.
    """

    def __init__(self, *, judge: LLMJudge, tolerance: float = 0.1) -> None:
        """Store the judge under test and the agreement tolerance.

        Args:
            judge: The configured :class:`LLMJudge` to calibrate.
            tolerance: Maximum absolute score difference still counted as
                agreement.

        Raises:
            TypeError: If ``judge`` is not an :class:`LLMJudge` or ``tolerance``
                is not a real number.
            ValueError: If ``tolerance`` is negative.
        """
        if not isinstance(judge, LLMJudge):
            raise TypeError(
                f"JudgeCalibration: judge must be an LLMJudge, got {type(judge).__name__}"
            )
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
            raise TypeError(
                f"JudgeCalibration: tolerance must be a real number, got {type(tolerance).__name__}"
            )
        if tolerance < 0:
            raise ValueError(f"JudgeCalibration: tolerance must be >= 0, got {tolerance}")
        self._judge = judge
        self._tolerance = float(tolerance)

    async def calibrate(self, gold: Sequence[GoldLabel]) -> CalibrationReport:
        """Judge every gold item and summarise agreement and error.

        An empty gold set yields perfect agreement (1.0) and zero error by
        convention.

        Raises:
            TypeError: If any element of ``gold`` is not a :class:`GoldLabel`.
        """
        items = list(gold)
        for index, label in enumerate(items):
            if not isinstance(label, GoldLabel):
                raise TypeError(
                    f"JudgeCalibration.calibrate: gold[{index}] must be a GoldLabel, "
                    f"got {type(label).__name__}"
                )
        records: list[dict[str, float]] = []
        errors: list[float] = []
        agreed = 0
        for label in items:
            score = await self._judge.score_rubric(
                prompt=label.prompt,
                response=label.response,
                criteria=label.criteria,
            )
            error = abs(score.overall - label.expected_score)
            errors.append(error)
            if error <= self._tolerance:
                agreed += 1
            records.append(
                {"judged": score.overall, "expected": label.expected_score, "error": error}
            )
        n = len(items)
        agreement = agreed / n if n else 1.0
        mean_abs_error = sum(errors) / n if n else 0.0
        return CalibrationReport(
            agreement=agreement,
            mean_abs_error=mean_abs_error,
            n=n,
            detail={"items": records, "tolerance": self._tolerance},
        )
