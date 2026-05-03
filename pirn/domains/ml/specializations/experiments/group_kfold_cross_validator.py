"""``GroupKFoldCrossValidator`` — K-fold cross-validation that keeps all
samples from the same group in the same fold.

Prevents data leakage when samples within a group are correlated (e.g.
multiple records for the same patient or user).
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


class GroupKFoldCrossValidator(SubTapestry):
    """K-fold CV that preserves group integrity across folds."""

    def __init__(
        self,
        *,
        dataset: Knot,
        algorithm: str,
        metrics: Sequence[str],
        group_column: str,
        k: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(dataset, Knot):
            raise TypeError(
                "GroupKFoldCrossValidator: dataset must be a Knot"
            )
        if not isinstance(k, int):
            raise TypeError("GroupKFoldCrossValidator: k must be an int")
        if k < 2:
            raise ValueError("GroupKFoldCrossValidator: k must be >= 2")
        if not isinstance(group_column, str) or not group_column:
            raise ValueError(
                "GroupKFoldCrossValidator: group_column must be a non-empty "
                "string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "GroupKFoldCrossValidator: algorithm must be a non-empty "
                "string"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "GroupKFoldCrossValidator: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "GroupKFoldCrossValidator: every metric name must be a "
                    "non-empty string"
                )
        self._k = k
        self._group_column = group_column
        self._algorithm = algorithm
        self._metrics = metric_tuple
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> EvalReport:
        """Run group K-fold cross-validation and return an EvalReport with mean metrics.

        Args:
            dataset: MLDataset to partition into k group-aware folds.

        Returns:
            EvalReport with averaged per-fold metrics and group_column recorded
            in details.

        Raises:
            TypeError: If any fold evaluator does not return an EvalReport.
        """
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

        with Tapestry() as inner_eval:
            for fold_index, fold in enumerate(folds):
                split_node = _emit_value(
                    value=fold,
                    _config=KnotConfig(id=f"split_{fold_index}"),
                )
                model = Trainer(
                    split=split_node,
                    algorithm=self._algorithm,
                    _config=KnotConfig(id=f"train_{fold_index}"),
                )
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=self._metrics,
                    _config=KnotConfig(id=f"evaluate_{fold_index}"),
                )
        eval_result = await self._run_inner(inner_eval)

        per_fold: list[dict[str, float]] = []
        for fold_index in range(len(folds)):
            report = eval_result.outputs[f"evaluate_{fold_index}"]
            if not isinstance(report, EvalReport):
                raise TypeError(
                    f"GroupKFoldCrossValidator: fold {fold_index} did not "
                    "produce an EvalReport"
                )
            per_fold.append(
                {name: float(value) for name, value in report.metrics.items()}
            )

        aggregated = self._aggregate(per_fold)
        return EvalReport(
            model_id=f"{self._algorithm}:group_kfold-{self._k}",
            dataset_name=dataset.name,
            metrics=MappingProxyType(aggregated),
            details=MappingProxyType(
                {
                    "k": self._k,
                    "group_column": self._group_column,
                    "algorithm": self._algorithm,
                    "per_fold_metrics": per_fold,
                }
            ),
            evaluated_at=datetime.now(timezone.utc),
        )

    def _aggregate(
        self, per_fold: list[dict[str, float]]
    ) -> dict[str, float]:
        if not per_fold:
            return {}
        names = per_fold[0].keys()
        return {
            name: sum(fold[name] for fold in per_fold) / float(len(per_fold))
            for name in names
        }
