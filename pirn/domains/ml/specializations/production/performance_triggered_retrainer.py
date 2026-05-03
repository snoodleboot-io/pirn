"""``PerformanceTriggeredRetrainer`` — SubTapestry that monitors a live
metric and triggers a retraining run when it drops below a threshold,
returning the new model reference.
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping

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
        metric: str,
        threshold: float,
        algorithm: str = "random_forest",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("PerformanceTriggeredRetrainer: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("PerformanceTriggeredRetrainer: split must be a Knot")
        if not isinstance(metric, str) or not metric:
            raise ValueError(
                "PerformanceTriggeredRetrainer: metric must be a non-empty string"
            )
        if not isinstance(threshold, (int, float)):
            raise TypeError("PerformanceTriggeredRetrainer: threshold must be numeric")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "PerformanceTriggeredRetrainer: algorithm must be a non-empty string"
            )
        self._metric = metric
        self._threshold = float(threshold)
        self._algorithm = algorithm
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def metric(self) -> str:
        return self._metric

    @property
    def threshold(self) -> float:
        return self._threshold

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Evaluate the live metric and retrain if it falls below the threshold.

        Args:
            model: Current TrainedModel to evaluate.
            split: DataSplit used for evaluation and retraining.

        Returns:
            Mapping with ``triggered`` (bool), ``current_score`` (float),
            ``threshold`` (float), ``metric`` (str), and
            ``new_model_id`` (str or None if retraining was not triggered).
        """
        with Tapestry() as inner:
            model_node = _emit_value(value=model, _config=KnotConfig(id="model"))
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            Evaluator(
                model=model_node,
                split=split_node,
                metrics=(self._metric,),
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        report: EvalReport = inner_result.outputs["evaluate"]
        current_score = float(report.metrics[self._metric])
        triggered = current_score < self._threshold
        if not triggered:
            return {
                "triggered": False,
                "current_score": current_score,
                "threshold": self._threshold,
                "metric": self._metric,
                "new_model_id": None,
            }
        with Tapestry() as retrain_inner:
            split_node2 = _emit_value(value=split, _config=KnotConfig(id="split"))
            Trainer(
                split=split_node2,
                algorithm=self._algorithm,
                _config=KnotConfig(id="retrain"),
            )
        retrain_result = await self._run_inner(retrain_inner)
        new_model: TrainedModel = retrain_result.outputs["retrain"]
        return {
            "triggered": True,
            "current_score": current_score,
            "threshold": self._threshold,
            "metric": self._metric,
            "new_model_id": new_model.model_id,
        }
