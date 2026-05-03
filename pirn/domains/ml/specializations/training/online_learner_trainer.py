"""``OnlineLearnerTrainer`` — update a model incrementally via
``partial_fit`` on mini-batches.

Tracks a running metric across all mini-batches and returns the
final :class:`TrainedModel` with the last evaluation report.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

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
        algorithm: str,
        monitor_metric: str,
        n_batches: int = 10,
        hyperparameters: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("OnlineLearnerTrainer: split must be a Knot")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "OnlineLearnerTrainer: algorithm must be a non-empty string"
            )
        if not isinstance(monitor_metric, str) or not monitor_metric:
            raise ValueError(
                "OnlineLearnerTrainer: monitor_metric must be a non-empty "
                "string"
            )
        if not isinstance(n_batches, int):
            raise TypeError("OnlineLearnerTrainer: n_batches must be an int")
        if n_batches < 1:
            raise ValueError(
                "OnlineLearnerTrainer: n_batches must be >= 1"
            )
        if hyperparameters is not None and not isinstance(
            hyperparameters, Mapping
        ):
            raise TypeError(
                "OnlineLearnerTrainer: hyperparameters must be a Mapping"
            )
        self._algorithm = algorithm
        self._monitor_metric = monitor_metric
        self._n_batches = n_batches
        self._hyperparameters = (
            dict(hyperparameters) if hyperparameters is not None else {}
        )
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Incrementally train on mini-batches and return the final model and running metric history.

        Args:
            split: DataSplit whose training partition is divided into n_batches
                mini-batches for incremental partial_fit updates.

        Returns:
            Dict with ``model`` (TrainedModel), ``eval_report`` (EvalReport),
            and ``n_batches`` (int number of mini-batches processed).

        Raises:
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        rows_per_batch = max(1, split.train.row_count // self._n_batches)

        with Tapestry() as inner:
            for batch_idx in range(self._n_batches):
                batch_ds = MLDataset(
                    name=f"{split.train.name}:batch_{batch_idx}",
                    feature_names=split.train.feature_names,
                    target_name=split.train.target_name,
                    row_count=rows_per_batch,
                    source_uri=split.train.source_uri,
                )
                batch_split = DataSplit(
                    train=batch_ds, test=split.test
                )
                batch_node = _emit_value(
                    value=batch_split,
                    _config=KnotConfig(id=f"batch_{batch_idx}"),
                )
                model = Trainer(
                    split=batch_node,
                    algorithm=self._algorithm,
                    hyperparameters={
                        **self._hyperparameters,
                        "partial_fit": True,
                        "batch_idx": batch_idx,
                    },
                    _config=KnotConfig(id=f"train_{batch_idx}"),
                )
                Evaluator(
                    model=model,
                    split=batch_node,
                    metrics=(self._monitor_metric,),
                    _config=KnotConfig(id=f"evaluate_{batch_idx}"),
                )
        result = await self._run_inner(inner)

        last_idx = self._n_batches - 1
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
            "n_batches": self._n_batches,
        }
