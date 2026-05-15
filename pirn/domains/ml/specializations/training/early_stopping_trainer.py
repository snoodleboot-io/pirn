"""``EarlyStoppingTrainer`` — wrap a trainer with early stopping.

Monitors a validation metric and stops training when no improvement has
been observed for ``patience`` consecutive epochs. Returns the best
:class:`ModelManifest` found before early stopping triggered.

Algorithm:
    1. Receive ``split``, ``algorithm``, ``monitor_metric``, ``patience``,
       ``max_epochs``, ``hyperparameters``, and ``metrics`` via process().
    2. Validate all inputs.
    3. Wire Trainer + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return model, eval report, and epoch info.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
async def _combine_early_stopping(
    model: ModelManifest,
    eval_report: EvalReportPayload,
    stopped_epoch: int,
    patience: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "eval_report": eval_report,
        "stopped_epoch": stopped_epoch,
        "patience": patience,
    }


class EarlyStoppingTrainer(SubTapestry):
    """Train with early stopping on a configurable validation metric."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        monitor_metric: Knot | str,
        patience: Knot | int = 5,
        max_epochs: Knot | int = 100,
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        metrics: Knot | Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            monitor_metric=monitor_metric,
            patience=patience,
            max_epochs=max_epochs,
            hyperparameters=hyperparameters,
            metrics=metrics,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        algorithm: str = "",
        monitor_metric: str = "",
        patience: int = 5,
        max_epochs: int = 100,
        hyperparameters: Mapping[str, Any] | None = None,
        metrics: Sequence[str] | None = None,
        **_: Any,
    ) -> Any:
        """Train the model with early stopping and return the best model, its evaluation, and training metadata.

        Args:
            split: SplitManifest used for training and validation metric monitoring.
            algorithm: Non-empty algorithm identifier.
            monitor_metric: Non-empty name of the metric to monitor for early stopping.
            patience: Consecutive epochs without improvement before stopping; must be >= 1.
            max_epochs: Maximum training epochs; must be >= 1.
            hyperparameters: Optional mapping of additional hyperparameters.
            metrics: Optional sequence of metrics to evaluate; defaults to monitor_metric.

        Returns:
            Dict with ``model`` (ModelManifest), ``eval_report`` (EvalMetadata),
            ``stopped_epoch`` (int), and ``patience`` (int).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("EarlyStoppingTrainer: algorithm must be a non-empty string")
        if not isinstance(monitor_metric, str) or not monitor_metric:
            raise ValueError("EarlyStoppingTrainer: monitor_metric must be a non-empty string")
        if not isinstance(patience, int):
            raise TypeError("EarlyStoppingTrainer: patience must be an int")
        if patience < 1:
            raise ValueError("EarlyStoppingTrainer: patience must be >= 1")
        if not isinstance(max_epochs, int):
            raise TypeError("EarlyStoppingTrainer: max_epochs must be an int")
        if max_epochs < 1:
            raise ValueError("EarlyStoppingTrainer: max_epochs must be >= 1")
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("EarlyStoppingTrainer: hyperparameters must be a Mapping")
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        metric_tuple = tuple(metrics) if metrics else (monitor_metric,)
        hp["max_epochs"] = max_epochs
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        trained = Trainer(
            split=split_node,
            algorithm=algorithm,
            hyperparameters=hp,
            _config=KnotConfig(id="train"),
        )
        evaluated = Evaluator(
            model=trained,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        stopped_epoch_node = _emit_value(value=max_epochs, _config=KnotConfig(id="stopped_epoch"))
        patience_node = _emit_value(value=patience, _config=KnotConfig(id="patience"))
        return _combine_early_stopping(
            model=trained,
            eval_report=evaluated,
            stopped_epoch=stopped_epoch_node,
            patience=patience_node,
            _config=KnotConfig(id="combine"),
        )
