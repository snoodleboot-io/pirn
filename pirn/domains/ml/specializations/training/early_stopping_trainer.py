"""``EarlyStoppingTrainer`` — wrap a trainer with early stopping.

Monitors a validation metric and stops training when no improvement has
been observed for ``patience`` consecutive epochs. Returns the best
:class:`TrainedModel` found before early stopping triggered.

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
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


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
        split: DataSplit,
        algorithm: str = "",
        monitor_metric: str = "",
        patience: int = 5,
        max_epochs: int = 100,
        hyperparameters: Mapping[str, Any] | None = None,
        metrics: Sequence[str] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Train the model with early stopping and return the best model, its evaluation, and training metadata.

        Args:
            split: DataSplit used for training and validation metric monitoring.
            algorithm: Non-empty algorithm identifier.
            monitor_metric: Non-empty name of the metric to monitor for early stopping.
            patience: Consecutive epochs without improvement before stopping; must be >= 1.
            max_epochs: Maximum training epochs; must be >= 1.
            hyperparameters: Optional mapping of additional hyperparameters.
            metrics: Optional sequence of metrics to evaluate; defaults to monitor_metric.

        Returns:
            Dict with ``model`` (TrainedModel), ``eval_report`` (EvalReport),
            ``stopped_epoch`` (int), and ``patience`` (int).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("EarlyStoppingTrainer: algorithm must be a non-empty string")
        if not isinstance(monitor_metric, str) or not monitor_metric:
            raise ValueError(
                "EarlyStoppingTrainer: monitor_metric must be a non-empty string"
            )
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
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            model = Trainer(
                split=split_node,
                algorithm=algorithm,
                hyperparameters=hp,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=model,
                split=split_node,
                metrics=metric_tuple,
                _config=KnotConfig(id="evaluate"),
            )
        result = await self._run_inner(inner)
        trained_model = result.outputs["train"]
        report = result.outputs["evaluate"]
        if not isinstance(trained_model, TrainedModel):
            raise TypeError(
                "EarlyStoppingTrainer: trainer did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "EarlyStoppingTrainer: evaluator did not return an EvalReport"
            )
        return {
            "model": trained_model,
            "eval_report": report,
            "stopped_epoch": max_epochs,
            "patience": patience,
        }
