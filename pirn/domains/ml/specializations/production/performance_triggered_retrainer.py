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
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _build_retrainer_result(
    eval_report: EvalReportPayload,
    retrained_model: ModelManifest,
    metric: str,
    threshold: float,
) -> Mapping[str, Any]:
    current_score = float(eval_report.metrics.scores[metric])
    triggered = current_score < threshold
    return {
        "triggered": triggered,
        "current_score": current_score,
        "threshold": threshold,
        "metric": metric,
        "new_model_id": retrained_model.model_id if triggered else None,
    }


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
        model: ModelManifest,
        split: SplitManifest,
        metric: str = "",
        threshold: float = 0.0,
        algorithm: str = "random_forest",
        **_: Any,
    ) -> Any:
        """Evaluate the live metric and retrain if it falls below the threshold.

        Args:
            model: Current ModelManifest to evaluate.
            split: SplitManifest used for evaluation and retraining.
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
            raise ValueError("PerformanceTriggeredRetrainer: algorithm must be a non-empty string")
        threshold_f = float(threshold)
        model_node = _emit_value(value=model, _config=KnotConfig(id="model"))
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        evaluated = Evaluator(
            model=model_node,
            split=split_node,
            metrics=(metric,),
            _config=KnotConfig(id="evaluate"),
        )
        retrained = Trainer(
            split=split_node,
            algorithm=algorithm,
            _config=KnotConfig(id="retrain"),
        )
        metric_node = _emit_value(value=metric, _config=KnotConfig(id="metric"))
        threshold_node = _emit_value(value=threshold_f, _config=KnotConfig(id="threshold"))
        return _build_retrainer_result(
            eval_report=evaluated,
            retrained_model=retrained,
            metric=metric_node,
            threshold=threshold_node,
            _config=KnotConfig(id="combine"),
        )
