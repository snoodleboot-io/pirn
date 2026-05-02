"""``StratifiedKFoldValidator`` — K-fold cross-validation with target
stratification.

Composition:

1. :class:`CrossValidator` produces ``k`` logical :class:`DataSplit`
   folds from the upstream :class:`MLDataset`.
2. For each fold, :class:`Trainer` fits the configured algorithm and
   :class:`Evaluator` scores it on the fold's test partition.
3. Per-fold metric values are averaged into a single aggregate
   :class:`EvalReport`.

The stratification column is recorded in the aggregate report's
``details`` for audit; the orchestration layer's :class:`CrossValidator`
emits logical fold metadata only — concrete subclasses are responsible
for the actual stratified row partitioning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.data_prep.cross_validator import CrossValidator
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class StratifiedKFoldValidator(SubTapestry):
    """K-fold cross-validation with target stratification."""

    def __init__(
        self,
        *,
        dataset: Knot,
        stratify_column: str,
        algorithm: str,
        metrics: Sequence[str],
        k: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(dataset, Knot):
            raise TypeError(
                "StratifiedKFoldValidator: dataset must be a Knot"
            )
        if not isinstance(k, int):
            raise TypeError("StratifiedKFoldValidator: k must be an int")
        if k < 2:
            raise ValueError("StratifiedKFoldValidator: k must be >= 2")
        if not isinstance(stratify_column, str) or not stratify_column:
            raise ValueError(
                "StratifiedKFoldValidator: stratify_column must be a "
                "non-empty string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "StratifiedKFoldValidator: algorithm must be a non-empty "
                "string"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "StratifiedKFoldValidator: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "StratifiedKFoldValidator: every metric name must be "
                    "a non-empty string"
                )
        self._k = k
        self._stratify_column = stratify_column
        self._algorithm = algorithm
        self._metrics = metric_tuple
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> EvalReport:
        with Tapestry() as inner:
            dataset_node = _emit_value(
                value=dataset, _config=KnotConfig(id="dataset")
            )
            CrossValidator(
                dataset=dataset_node,
                k=self._k,
                _config=KnotConfig(id="folds"),
            )
        folds_result = await self._run_inner(inner)
        folds: tuple[DataSplit, ...] = folds_result.outputs["folds"]
        per_fold_metrics: list[dict[str, float]] = []
        with Tapestry() as inner_eval:
            for fold_index, fold in enumerate(folds):
                split_node = _emit_value(
                    value=fold,
                    _config=KnotConfig(id=f"split_{fold_index}"),
                )
                model = Trainer(
                    split=split_node,
                    algorithm=self._algorithm,
                    hyperparameters={"fold_index": fold_index},
                    _config=KnotConfig(id=f"train_{fold_index}"),
                )
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=self._metrics,
                    _config=KnotConfig(id=f"evaluate_{fold_index}"),
                )
        eval_result = await self._run_inner(inner_eval)
        for fold_index in range(len(folds)):
            report = eval_result.outputs[f"evaluate_{fold_index}"]
            if not isinstance(report, EvalReport):
                raise TypeError(
                    f"StratifiedKFoldValidator: fold {fold_index} did not "
                    "produce an EvalReport"
                )
            per_fold_metrics.append(
                {name: float(value) for name, value in report.metrics.items()}
            )
        aggregated = self._aggregate(per_fold_metrics)
        return EvalReport(
            model_id=f"{self._algorithm}:kfold-{self._k}",
            dataset_name=dataset.name,
            metrics=MappingProxyType(aggregated),
            details=MappingProxyType(
                {
                    "k": self._k,
                    "stratify_column": self._stratify_column,
                    "algorithm": self._algorithm,
                    "per_fold_metrics": per_fold_metrics,
                }
            ),
            evaluated_at=datetime.now(timezone.utc),
        )

    def _aggregate(
        self, per_fold_metrics: list[dict[str, float]]
    ) -> dict[str, float]:
        if not per_fold_metrics:
            return {}
        names = per_fold_metrics[0].keys()
        return {
            name: sum(fold[name] for fold in per_fold_metrics)
            / float(len(per_fold_metrics))
            for name in names
        }
