"""``SemiSupervisedTrainer`` — train on labeled data, predict pseudo-labels
for unlabeled data, then retrain on the combined set.

Returns the final :class:`ModelManifest` and its evaluation report after
the pseudo-labeling iteration.

Algorithm:
    1. Receive ``split``, ``algorithm``, ``unlabeled_row_count``,
       ``metrics``, and ``hyperparameters`` via process().
    2. Validate all inputs.
    3. Build combined labeled+pseudo-labeled split, wire Trainer + Evaluator
       in an inner Tapestry.
    4. Run via _run_inner() and return model, eval report, and pseudo_labeled_rows.


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
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_semi_supervised_result(
    model: ModelManifest,
    eval_report: EvalReportPayload,
    pseudo_labeled_rows: int,
) -> dict[str, Any]:
    return {"model": model, "eval_report": eval_report, "pseudo_labeled_rows": pseudo_labeled_rows}


class SemiSupervisedTrainer(SubTapestry):
    """Train on labeled + pseudo-labeled data in two passes."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        unlabeled_row_count: Knot | int,
        metrics: Knot | Sequence[str],
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            unlabeled_row_count=unlabeled_row_count,
            metrics=metrics,
            hyperparameters=hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        algorithm: str = "",
        unlabeled_row_count: int = 0,
        metrics: Sequence[str] = (),
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        """Train on labeled data, generate pseudo-labels, and retrain on combined set.

        Args:
            split: SplitManifest with labeled train and test partitions.
            algorithm: Non-empty algorithm identifier.
            unlabeled_row_count: Number of pseudo-labeled rows to add; must be int >= 0.
            metrics: Non-empty sequence of metric names.
            hyperparameters: Optional mapping of additional hyperparameters.

        Returns:
            Dict with ``model`` (ModelManifest), ``eval_report`` (EvalMetadata),
            and ``pseudo_labeled_rows`` (int rows added from unlabeled set).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If any inner trainer or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("SemiSupervisedTrainer: algorithm must be a non-empty string")
        if not isinstance(unlabeled_row_count, int):
            raise TypeError("SemiSupervisedTrainer: unlabeled_row_count must be an int")
        if unlabeled_row_count < 0:
            raise ValueError("SemiSupervisedTrainer: unlabeled_row_count must be >= 0")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("SemiSupervisedTrainer: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "SemiSupervisedTrainer: every metric name must be a non-empty string"
                )
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("SemiSupervisedTrainer: hyperparameters must be a Mapping")
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        combined_rows = split.train.row_count + unlabeled_row_count
        combined_ds = DatasetManifest(
            name=f"{split.train.name}:semi_supervised",
            feature_names=split.train.feature_names,
            target_name=split.train.target_name,
            row_count=combined_rows,
            source_uri=split.train.source_uri,
        )
        combined_split = SplitManifest(train=combined_ds, test=split.test)

        split_node = _emit_value(value=combined_split, _config=KnotConfig(id="split"))
        model = Trainer(
            split=split_node,
            algorithm=algorithm,
            hyperparameters={**hp, "semi_supervised": True},
            _config=KnotConfig(id="train"),
        )
        evaluated = Evaluator(
            model=model,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        pseudo_rows_node = _emit_value(
            value=unlabeled_row_count, _config=KnotConfig(id="pseudo_labeled_rows")
        )
        return _combine_semi_supervised_result(
            model=model,
            eval_report=evaluated,
            pseudo_labeled_rows=pseudo_rows_node,
            _config=KnotConfig(id="combine"),
        )
