# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``StratifiedKFoldValidator`` — K-fold cross-validation with target
stratification.

Composition:

1. k logical :class:`SplitManifest` folds are extracted via
   :meth:`~pirn_ml.specializations.experiments.kfold_validator_base.KFoldValidatorBase._extract_folds_via_cross_validator`
   from the upstream :class:`DatasetManifest`.
2. For each fold, :class:`Trainer` fits the configured algorithm and
   :class:`Evaluator` scores it on the fold's test partition.
3. Per-fold metric values are averaged into a single aggregate
   :class:`EvalMetadata`.

The stratification column is recorded in the aggregate report's
``details`` for audit; the orchestration layer's :class:`CrossValidator`
emits logical fold metadata only — concrete subclasses are responsible
for the actual stratified row partitioning.

Algorithm:
    1. Receive ``dataset`` (DatasetManifest), ``stratify_column``, ``algorithm``,
       ``metrics``, and ``k`` via process().
    2. Validate all inputs.
    3. Extract k logical folds (shared strategy in
       :class:`~pirn_ml.specializations.experiments.kfold_validator_base.KFoldValidatorBase`).
    4. Wire Trainer + Evaluator per fold (shared wiring, same base class).
    5. Aggregate per-fold metrics (mean) and return an EvalMetadata.

Math:
    mean_metric = sum(fold_metric) / k

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.parameter import Parameter

from pirn_ml.specializations.experiments.kfold_validator_base import (
    KFoldValidatorBase,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics
from pirn_ml.types.eval_report_payload import EvalReportPayload


@KnotFactory.knot
async def _aggregate_stratified_kfold_reports(
    reports: list[EvalReportPayload],
    algorithm: str,
    dataset_name: str,
    k: int,
    stratify_column: str,
) -> EvalReportPayload:
    per_fold = [
        {name: float(value) for name, value in report.metrics.scores.items()} for report in reports
    ]
    if not per_fold:
        aggregated: dict[str, float] = {}
    else:
        names = per_fold[0].keys()
        aggregated = {
            name: sum(fold[name] for fold in per_fold) / float(len(per_fold)) for name in names
        }
    return EvalReportPayload(
        metadata=EvalMetadata(
            model_id=f"{algorithm}:kfold-{k}",
            dataset_name=dataset_name,
            evaluated_at=datetime.now(UTC),
        ),
        data=EvalMetrics(
            scores=MappingProxyType(aggregated),
            details=MappingProxyType(
                {
                    "k": k,
                    "stratify_column": stratify_column,
                    "algorithm": algorithm,
                    "per_fold_metrics": per_fold,
                }
            ),
        ),
    )


class StratifiedKFoldValidator(KFoldValidatorBase):
    """K-fold cross-validation with target stratification."""

    def __init__(
        self,
        *,
        dataset: Knot,
        stratify_column: Knot | str,
        algorithm: Knot | str,
        metrics: Knot | Sequence[str],
        k: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            stratify_column=stratify_column,
            algorithm=algorithm,
            metrics=metrics,
            k=k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest,
        stratify_column: str = "",
        algorithm: str = "",
        metrics: Sequence[str] = (),
        k: int = 5,
        **_: Any,
    ) -> Any:
        """Run stratified K-fold cross-validation and return an aggregate EvalReportPayload with per-fold mean metrics.

        Args:
            dataset: DatasetManifest reference to partition into k folds.
            stratify_column: Non-empty column name used for stratification.
            algorithm: Non-empty algorithm name string.
            metrics: Non-empty sequence of metric name strings.
            k: Number of folds; must be an int >= 2.

        Returns:
            EvalReportPayload with averaged per-fold metrics and per-fold details in the details dict.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If any inner fold evaluator does not return an EvalReportPayload.
        """
        if not isinstance(k, int):
            raise TypeError("StratifiedKFoldValidator: k must be an int")
        if k < 2:
            raise ValueError("StratifiedKFoldValidator: k must be >= 2")
        if not isinstance(stratify_column, str) or not stratify_column:
            raise ValueError("StratifiedKFoldValidator: stratify_column must be a non-empty string")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("StratifiedKFoldValidator: algorithm must be a non-empty string")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("StratifiedKFoldValidator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "StratifiedKFoldValidator: every metric name must be a non-empty string"
                )
        dataset_node = Parameter(
            "dataset", DatasetManifest, default=dataset, _config=KnotConfig(id="dataset")
        )
        fold_nodes = self._extract_folds_via_cross_validator(dataset_node, k)
        eval_nodes = self._wire_folds(
            fold_nodes,
            algorithm,
            metric_tuple,
            hyperparameters_for_fold=lambda fold_index: {"fold_index": fold_index},
        )
        algorithm_node = Parameter(
            "algorithm", str, default=algorithm, _config=KnotConfig(id="algorithm")
        )
        dataset_name_node = Parameter(
            "dataset_name", str, default=dataset.name, _config=KnotConfig(id="dataset_name")
        )
        k_node = Parameter("k", int, default=k, _config=KnotConfig(id="k"))
        stratify_col_node = Parameter(
            "stratify_column",
            str,
            default=stratify_column,
            _config=KnotConfig(id="stratify_column"),
        )
        collected = self._collect(eval_nodes, collect_id="collect-reports")
        return _aggregate_stratified_kfold_reports(
            reports=collected,
            algorithm=algorithm_node,
            dataset_name=dataset_name_node,
            k=k_node,
            stratify_column=stratify_col_node,
            _config=KnotConfig(id="aggregate"),
        )
