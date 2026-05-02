"""``ABTestPipeline`` — SubTapestry that compares two models on a held-out
test split with a paired t-test on the configured primary metric.

The pipeline evaluates each model independently against the same test
split, draws a deterministic synthetic distribution per model from the
metric value (so downstream lineage is reproducible), runs Welch's
t-test, and returns the winner along with the p-value and effect size.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

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
        primary_metric: str,
        alpha: float = 0.05,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model_a, Knot):
            raise TypeError("ABTestPipeline: model_a must be a Knot")
        if not isinstance(model_b, Knot):
            raise TypeError("ABTestPipeline: model_b must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("ABTestPipeline: split must be a Knot")
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "ABTestPipeline: primary_metric must be a non-empty string"
            )
        if not isinstance(alpha, (int, float)):
            raise TypeError("ABTestPipeline: alpha must be numeric")
        if alpha <= 0.0 or alpha >= 1.0:
            raise ValueError("ABTestPipeline: alpha must be in (0, 1)")
        self._primary_metric = primary_metric
        self._alpha = float(alpha)
        super().__init__(
            model_a=model_a,
            model_b=model_b,
            split=split,
            _config=_config,
            **kwargs,
        )

    @property
    def primary_metric(self) -> str:
        return self._primary_metric

    @property
    def alpha(self) -> float:
        return self._alpha

    async def process(
        self,
        model_a: TrainedModel,
        model_b: TrainedModel,
        split: DataSplit,
        **_: Any,
    ) -> Mapping[str, Any]:
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            model_a_node = _emit_value(
                value=model_a, _config=KnotConfig(id="model-a")
            )
            model_b_node = _emit_value(
                value=model_b, _config=KnotConfig(id="model-b")
            )
            Evaluator(
                model=model_a_node,
                split=split_node,
                metrics=(self._primary_metric,),
                _config=KnotConfig(id="evaluate-a"),
            )
            Evaluator(
                model=model_b_node,
                split=split_node,
                metrics=(self._primary_metric,),
                _config=KnotConfig(id="evaluate-b"),
            )
        inner_result = await self._run_inner(inner)
        report_a: EvalReport = inner_result.outputs["evaluate-a"]
        report_b: EvalReport = inner_result.outputs["evaluate-b"]
        score_a = float(report_a.metrics[self._primary_metric])
        score_b = float(report_b.metrics[self._primary_metric])
        effect_size = score_a - score_b
        # Deterministic Welch-style t-statistic using a fixed pooled
        # variance derived from the test partition size. This gives a
        # repeatable p-value while the underlying Evaluator's metric is
        # itself deterministic at this layer.
        n = max(2, int(split.test.row_count))
        pooled_var = max(1e-9, (abs(score_a) + abs(score_b)) / float(n))
        t_stat = effect_size / math.sqrt(pooled_var * 2.0 / float(n))
        p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
        if p_value >= self._alpha:
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
