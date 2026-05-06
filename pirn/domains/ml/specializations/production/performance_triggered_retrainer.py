"""``PerformanceTriggeredRetrainer`` — SubTapestry that monitors a live
metric and triggers a retraining run when it drops below a threshold,
returning the new model reference.

Algorithm:
    1. Receive ``model``, ``split``, ``metric``, ``threshold``, and
       ``algorithm`` via process().
    2. Validate all inputs.
    3. Evaluate live metric using inner Tapestry.
    4. If metric < threshold, retrain via a second inner Tapestry.
    5. Return triggered status and new_model_id.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class PerformanceTriggeredRetrainer(SubTapestry):
    """Monitor a live metric and trigger retraining when it drops below a threshold."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        metric: Knot | str,
        threshold: Knot | float,
        algorithm: Knot | str = "random_forest",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            metric=metric,
            threshold=threshold,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        metric: str = "",
        threshold: float = 0.0,
        algorithm: str = "random_forest",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Evaluate the live metric and retrain if it falls below the threshold.

        Args:
            model: Current TrainedModel to evaluate.
            split: DataSplit used for evaluation and retraining.
            metric: Non-empty metric name to monitor.
            threshold: Score threshold below which retraining is triggered.
            algorithm: Non-empty algorithm identifier for retraining.

        Returns:
            Mapping with ``triggered`` (bool), ``current_score`` (float),
            ``threshold`` (float), ``metric`` (str), and
            ``new_model_id`` (str or None if retraining was not triggered).

        Raises:
            ValueError: If metric or algorithm is empty.
        """
        if not isinstance(metric, str) or not metric:
            raise ValueError("PerformanceTriggeredRetrainer: metric must be a non-empty string")
        if not isinstance(threshold, (int, float)):
            raise TypeError("PerformanceTriggeredRetrainer: threshold must be numeric")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "PerformanceTriggeredRetrainer: algorithm must be a non-empty string"
            )
        threshold_f = float(threshold)
        with Tapestry() as inner:
            model_node = _emit_value(value=model, _config=KnotConfig(id="model"))
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            Evaluator(
                model=model_node,
                split=split_node,
                metrics=(metric,),
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        report: EvalReport = inner_result.outputs["evaluate"]
        current_score = float(report.metrics[metric])
        triggered = current_score < threshold_f
        if not triggered:
            return {
                "triggered": False,
                "current_score": current_score,
                "threshold": threshold_f,
                "metric": metric,
                "new_model_id": None,
            }
        with Tapestry() as retrain_inner:
            split_node2 = _emit_value(value=split, _config=KnotConfig(id="split"))
            Trainer(
                split=split_node2,
                algorithm=algorithm,
                _config=KnotConfig(id="retrain"),
            )
        retrain_result = await self._run_inner(retrain_inner)
        new_model: TrainedModel = retrain_result.outputs["retrain"]
        return {
            "triggered": True,
            "current_score": current_score,
            "threshold": threshold_f,
            "metric": metric,
            "new_model_id": new_model.model_id,
        }
