"""``OnlineLearnerTrainer`` — update a model incrementally via
``partial_fit`` on mini-batches.

Tracks a running metric across all mini-batches and returns the
final :class:`TrainedModel` with the last evaluation report.

Algorithm:
    1. Receive ``split``, ``algorithm``, ``monitor_metric``,
       ``n_batches``, and ``hyperparameters`` via process().
    2. Validate all inputs.
    3. Wire N (Trainer + Evaluator) pairs in an inner Tapestry.
    4. Run via _run_inner() and return final model and eval report.


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
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class OnlineLearnerTrainer(SubTapestry):
    """Incrementally update a model on mini-batches via partial_fit."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        monitor_metric: Knot | str,
        n_batches: Knot | int = 10,
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            monitor_metric=monitor_metric,
            n_batches=n_batches,
            hyperparameters=hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        algorithm: str = "",
        monitor_metric: str = "",
        n_batches: int = 10,
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Incrementally train on mini-batches and return the final model and running metric history.

        Args:
            split: DataSplit whose training partition is divided into n_batches
                mini-batches for incremental partial_fit updates.
            algorithm: Non-empty algorithm identifier.
            monitor_metric: Non-empty metric name to track across batches.
            n_batches: Number of mini-batches; must be an int >= 1.
            hyperparameters: Optional mapping of additional hyperparameters.

        Returns:
            Dict with ``model`` (TrainedModel), ``eval_report`` (EvalReport),
            and ``n_batches`` (int number of mini-batches processed).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("OnlineLearnerTrainer: algorithm must be a non-empty string")
        if not isinstance(monitor_metric, str) or not monitor_metric:
            raise ValueError(
                "OnlineLearnerTrainer: monitor_metric must be a non-empty string"
            )
        if not isinstance(n_batches, int):
            raise TypeError("OnlineLearnerTrainer: n_batches must be an int")
        if n_batches < 1:
            raise ValueError("OnlineLearnerTrainer: n_batches must be >= 1")
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("OnlineLearnerTrainer: hyperparameters must be a Mapping")
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        rows_per_batch = max(1, split.train.row_count // n_batches)

        with Tapestry() as inner:
            for batch_idx in range(n_batches):
                batch_ds = MLDataset(
                    name=f"{split.train.name}:batch_{batch_idx}",
                    feature_names=split.train.feature_names,
                    target_name=split.train.target_name,
                    row_count=rows_per_batch,
                    source_uri=split.train.source_uri,
                )
                batch_split = DataSplit(train=batch_ds, test=split.test)
                batch_node = _emit_value(
                    value=batch_split,
                    _config=KnotConfig(id=f"batch_{batch_idx}"),
                )
                model = Trainer(
                    split=batch_node,
                    algorithm=algorithm,
                    hyperparameters={
                        **hp,
                        "partial_fit": True,
                        "batch_idx": batch_idx,
                    },
                    _config=KnotConfig(id=f"train_{batch_idx}"),
                )
                Evaluator(
                    model=model,
                    split=batch_node,
                    metrics=(monitor_metric,),
                    _config=KnotConfig(id=f"evaluate_{batch_idx}"),
                )
        result = await self._run_inner(inner)

        last_idx = n_batches - 1
        trained_model = result.outputs[f"train_{last_idx}"]
        report = result.outputs[f"evaluate_{last_idx}"]
        if not isinstance(trained_model, TrainedModel):
            raise TypeError(
                "OnlineLearnerTrainer: trainer did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "OnlineLearnerTrainer: evaluator did not return an EvalReport"
            )
        return {
            "model": trained_model,
            "eval_report": report,
            "n_batches": n_batches,
        }
