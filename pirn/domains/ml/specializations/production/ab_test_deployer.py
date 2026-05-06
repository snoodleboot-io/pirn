"""``ABTestDeployer`` — SubTapestry that splits traffic 50/50 between two
model versions, collects metrics, runs a statistical significance test,
and returns the comparison result.

Algorithm:
    1. Receive ``model_a``, ``model_b``, ``split``, ``primary_metric``,
       and ``alpha`` via process().
    2. Validate all inputs.
    3. Wire two Evaluator knots (one per model) in an inner Tapestry.
    4. Run via _run_inner() and return winner, scores, p_value, significant.

Math:
    Pooled t-test approximation using erfc for p-value.

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


class ABTestDeployer(SubTapestry):
    """50/50 A/B traffic split with statistical significance testing."""

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
        """Evaluate both models on equal 50/50 traffic, run a significance test, and return the winner.

        Args:
            model_a: First TrainedModel in the A/B experiment.
            model_b: Second TrainedModel in the A/B experiment.
            split: DataSplit used to simulate traffic and evaluate both variants.
            primary_metric: Non-empty metric name to compare.
            alpha: Significance level; must be in (0, 1).

        Returns:
            Mapping with ``winner`` (``"a"``, ``"b"``, or ``"tie"``),
            ``score_a``, ``score_b``, ``p_value``, ``significant`` (bool),
            and ``primary_metric``.

        Raises:
            ValueError: If primary_metric is empty or alpha is out of range.
        """
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError("ABTestDeployer: primary_metric must be a non-empty string")
        if not isinstance(alpha, (int, float)) or alpha <= 0.0 or alpha >= 1.0:
            raise ValueError("ABTestDeployer: alpha must be in (0, 1)")
        alpha_f = float(alpha)
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            model_a_node = _emit_value(value=model_a, _config=KnotConfig(id="model-a"))
            model_b_node = _emit_value(value=model_b, _config=KnotConfig(id="model-b"))
            Evaluator(
                model=model_a_node,
                split=split_node,
                metrics=(primary_metric,),
                _config=KnotConfig(id="eval-a"),
            )
            Evaluator(
                model=model_b_node,
                split=split_node,
                metrics=(primary_metric,),
                _config=KnotConfig(id="eval-b"),
            )
        inner_result = await self._run_inner(inner)
        report_a: EvalReport = inner_result.outputs["eval-a"]
        report_b: EvalReport = inner_result.outputs["eval-b"]
        score_a = float(report_a.metrics[primary_metric])
        score_b = float(report_b.metrics[primary_metric])
        effect = score_a - score_b
        n = max(2, int(split.test.row_count))
        pooled_var = max(1e-9, (abs(score_a) + abs(score_b)) / float(n))
        t_stat = effect / math.sqrt(pooled_var * 2.0 / float(n))
        p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
        significant = p_value < alpha_f
        if not significant:
            winner = "tie"
        elif effect > 0.0:
            winner = "a"
        else:
            winner = "b"
        return {
            "winner": winner,
            "score_a": score_a,
            "score_b": score_b,
            "p_value": p_value,
            "significant": significant,
            "primary_metric": primary_metric,
        }
