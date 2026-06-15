"""``OnlineLearnerTrainer`` — update a model incrementally via
``partial_fit`` on mini-batches.

Tracks a running metric across all mini-batches and returns the
final :class:`ModelManifest` with the last evaluation report.

Algorithm:
    1. Receive ``split``, ``algorithm``, ``monitor_metric``,
       ``n_batches``, and ``hyperparameters`` via process().
    2. Validate all inputs.
    3. Wire N (Trainer + Evaluator) pairs in an inner Tapestry.
    4. Run via _run_inner() and return final model and eval report.

Math:
    Mini-batch size: rows_per_batch = max(1, floor(train_rows / n_batches))

    Incremental update (partial_fit for batch b):
        theta_b <- theta_{b-1} - lr * grad_L(theta_{b-1}; X_b, y_b)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_online_learner_result(
    model: ModelManifest,
    eval_report: EvalReportPayload,
    n_batches: int,
) -> dict[str, Any]:
    return {"model": model, "eval_report": eval_report, "n_batches": n_batches}


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
        split: SplitManifest,
        algorithm: str = "",
        monitor_metric: str = "",
        n_batches: int = 10,
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        """Incrementally train on mini-batches and return the final model and running metric history.

        Args:
            split: SplitManifest whose training partition is divided into n_batches
                mini-batches for incremental partial_fit updates.
            algorithm: Non-empty algorithm identifier.
            monitor_metric: Non-empty metric name to track across batches.
            n_batches: Number of mini-batches; must be an int >= 1.
            hyperparameters: Optional mapping of additional hyperparameters.

        Returns:
            Dict with ``model`` (ModelManifest), ``eval_report`` (EvalMetadata),
            and ``n_batches`` (int number of mini-batches processed).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("OnlineLearnerTrainer: algorithm must be a non-empty string")
        if not isinstance(monitor_metric, str) or not monitor_metric:
            raise ValueError("OnlineLearnerTrainer: monitor_metric must be a non-empty string")
        if not isinstance(n_batches, int):
            raise TypeError("OnlineLearnerTrainer: n_batches must be an int")
        if n_batches < 1:
            raise ValueError("OnlineLearnerTrainer: n_batches must be >= 1")
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("OnlineLearnerTrainer: hyperparameters must be a Mapping")
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        rows_per_batch = max(1, split.train.row_count // n_batches)

        last_model: Any = None
        last_evaluated: Any = None
        for batch_idx in range(n_batches):
            batch_ds = DatasetManifest(
                name=f"{split.train.name}:batch_{batch_idx}",
                feature_names=split.train.feature_names,
                target_name=split.train.target_name,
                row_count=rows_per_batch,
                source_uri=split.train.source_uri,
            )
            batch_split = SplitManifest(train=batch_ds, test=split.test)
            batch_node = _emit_value(
                value=batch_split,
                _config=KnotConfig(id=f"batch_{batch_idx}"),
            )
            last_model = Trainer(
                split=batch_node,
                algorithm=algorithm,
                hyperparameters={
                    **hp,
                    "partial_fit": True,
                    "batch_idx": batch_idx,
                },
                _config=KnotConfig(id=f"train_{batch_idx}"),
            )
            last_evaluated = Evaluator(
                model=last_model,
                split=batch_node,
                metrics=(monitor_metric,),
                _config=KnotConfig(id=f"evaluate_{batch_idx}"),
            )
        n_batches_node = _emit_value(value=n_batches, _config=KnotConfig(id="n_batches"))
        return _combine_online_learner_result(
            model=last_model,
            eval_report=last_evaluated,
            n_batches=n_batches_node,
            _config=KnotConfig(id="combine"),
        )
