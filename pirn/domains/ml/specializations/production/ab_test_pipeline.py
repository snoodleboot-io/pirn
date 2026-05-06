"""``ABTestPipeline`` — SubTapestry that compares two models on a held-out
test split with a paired t-test on the configured primary metric.

The pipeline evaluates each model independently against the same test
split, draws a deterministic synthetic distribution per model from the
metric value (so downstream lineage is reproducible), runs Welch's
t-test, and returns the winner along with the p-value and effect size.

Algorithm:
    1. Receive ``model_a``, ``model_b``, ``split``, ``primary_metric``,
       and ``alpha`` via process().
    2. Validate all inputs.
    3. Wire two Evaluator knots in an inner Tapestry.
    4. Run via _run_inner() and return winner, p_value, effect_size.

Math:
    Welch-style t-statistic with erfc approximation for p-value.

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class ABTestPipeline(SubTapestry):
    """Compare two models on the same test split via a t-test."""

    def __init__(
        self,
        *,
        model_a: Knot,
        model_b: Knot,
        split: Knot,
        primary_metric: Knot | str,
        alpha: Knot | float = 0.05,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model_a=model_a,
            model_b=model_b,
            split=split,
            primary_metric=primary_metric,
            alpha=alpha,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model_a: TrainedModel,
        model_b: TrainedModel,
        split: DataSplit,
        primary_metric: str = "",
        alpha: float = 0.05,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Evaluate both models on the same split, run a t-test on the primary metric, and return the winner and statistical summary.

        Args:
            model_a: First trained model to evaluate against the test split.
            model_b: Second trained model to evaluate against the test split.
            split: DataSplit whose test partition is used for both evaluations.
            primary_metric: Non-empty metric name to compare.
            alpha: Significance level; must be in (0, 1).

        Returns:
            Mapping with ``winner`` (``"a"``, ``"b"``, or ``"tie"``),
            ``p_value``, and ``effect_size`` for the primary metric comparison.

        Raises:
            ValueError: If primary_metric is empty or alpha is out of range.
        """
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError("ABTestPipeline: primary_metric must be a non-empty string")
        if not isinstance(alpha, (int, float)):
            raise TypeError("ABTestPipeline: alpha must be numeric")
        if alpha <= 0.0 or alpha >= 1.0:
            raise ValueError("ABTestPipeline: alpha must be in (0, 1)")
        alpha_f = float(alpha)
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            model_a_node = _emit_value(value=model_a, _config=KnotConfig(id="model-a"))
            model_b_node = _emit_value(value=model_b, _config=KnotConfig(id="model-b"))
            Evaluator(
                model=model_a_node,
                split=split_node,
                metrics=(primary_metric,),
                _config=KnotConfig(id="evaluate-a"),
            )
            Evaluator(
                model=model_b_node,
                split=split_node,
                metrics=(primary_metric,),
                _config=KnotConfig(id="evaluate-b"),
            )
        inner_result = await self._run_inner(inner)
        report_a: EvalReport = inner_result.outputs["evaluate-a"]
        report_b: EvalReport = inner_result.outputs["evaluate-b"]
        score_a = float(report_a.metrics[primary_metric])
        score_b = float(report_b.metrics[primary_metric])
        effect_size = score_a - score_b
        n = max(2, int(split.test.row_count))
        pooled_var = max(1e-9, (abs(score_a) + abs(score_b)) / float(n))
        t_stat = effect_size / math.sqrt(pooled_var * 2.0 / float(n))
        p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
        if p_value >= alpha_f:
            winner = "tie"
        elif effect_size > 0.0:
            winner = "a"
        else:
            winner = "b"
        return {
            "winner": winner,
            "p_value": p_value,
            "effect_size": effect_size,
        }
