"""``StratifiedKFoldValidator`` — K-fold cross-validation with target
stratification.

Algorithm:
    1. Receive ``dataset`` (DatasetPayload), ``stratify_column``, ``algorithm``,
       ``metrics``, and ``k`` via process().
    2. Validate all inputs.
    3. Partition the rows with
       :class:`~pirn_ml.data_prep.stratified_cross_validator.StratifiedCrossValidator`:
       each fold's test partition holds every class of ``stratify_column`` in
       (to within one row) its whole-dataset proportion. Index the folds via
       :meth:`~pirn_ml.specializations.experiments.kfold_validator_base.KFoldValidatorBase._extract_folds`.
    4. Wire Trainer + Evaluator per fold (shared wiring in
       :class:`~pirn_ml.specializations.experiments.kfold_validator_base.KFoldValidatorBase`).
    5. Aggregate per-fold metrics (mean) and return an EvalReportPayload.

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

from pirn_ml.data_prep.stratified_cross_validator import StratifiedCrossValidator
from pirn_ml.specializations.experiments.kfold_validator_base import (
    KFoldValidatorBase,
)
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.split_manifest import SplitManifest


@KnotFactory.knot
async def _aggregate_stratified_kfold_reports(
    reports: list[EvalReportPayload],
    folds: tuple[SplitManifest, ...],
    algorithm: str,
    dataset_name: str,
    k: int,
    stratify_column: str,
) -> EvalReportPayload:
    per_fold = [
        {name: float(value) for name, value in report.data.scores.items()} for report in reports
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
                    "fold_test_row_indices": [list(fold.test.row_indices) for fold in folds],
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
        dataset: DatasetPayload,
        stratify_column: str = "",
        algorithm: str = "",
        metrics: Sequence[str] = (),
        k: int = 5,
        **_: Any,
    ) -> Any:
        """Run stratified K-fold cross-validation and return an aggregate EvalReportPayload with per-fold mean metrics.

        Args:
            dataset: DatasetPayload whose ``stratify_column`` labels drive stratification.
            stratify_column: Non-empty column name used for stratification.
            algorithm: Non-empty algorithm name string.
            metrics: Non-empty sequence of metric name strings.
            k: Number of folds; must be an int >= 2.

        Returns:
            EvalReportPayload with averaged per-fold metrics and per-fold details in the details dict.

        Raises:
            TypeError: If dataset is not a DatasetPayload.
            ValueError: If any input fails validation.
            TypeError: If any inner fold evaluator does not return an EvalReportPayload.
        """
        if not isinstance(dataset, DatasetPayload):
            raise TypeError("StratifiedKFoldValidator: dataset must be a DatasetPayload")
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
            "dataset", DatasetPayload, default=dataset, _config=KnotConfig(id="dataset")
        )
        folds_node = StratifiedCrossValidator(
            dataset=dataset_node,
            stratify_column=stratify_column,
            k=k,
            _config=KnotConfig(id="folds"),
        )
        fold_nodes = self._extract_folds(folds_node, k)
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
            "dataset_name",
            str,
            default=dataset.metadata.name,
            _config=KnotConfig(id="dataset_name"),
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
            folds=folds_node,
            algorithm=algorithm_node,
            dataset_name=dataset_name_node,
            k=k_node,
            stratify_column=stratify_col_node,
            _config=KnotConfig(id="aggregate"),
        )
