"""``TimeSeriesCrossValidator`` — expanding-window time series cross-validation.

Each fold adds one period of training data and evaluates on the next
period. Returns a single :class:`EvalMetadata` with mean metrics across folds.

Algorithm:
    1. Receive ``dataset`` (DatasetManifest), ``algorithm``, ``metrics``, and
       ``n_splits`` via process().
    2. Validate all inputs.
    3. For each fold, compute expanding train/test row counts and emit split partitions.
    4. Wire Trainer + Evaluator per fold (shared wiring in
       :class:`~pirn_ml.specializations.experiments._kfold_validator_base._KFoldValidatorBase`).
    5. Aggregate per-fold metrics and return an EvalMetadata.

Math:
    train_rows[i] = (i + 1) * (row_count // (n_splits + 1))
    test_rows = row_count // (n_splits + 1)
    mean_metric = sum(fold_metric) / n_splits

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

from pirn_ml.specializations.experiments._kfold_validator_base import (
    _KFoldValidatorBase,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.split_manifest import SplitManifest


@KnotFactory.knot
async def _aggregate_ts_cv_reports(
    reports: list[EvalReportPayload],
    algorithm: str,
    dataset_name: str,
    n_splits: int,
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
            model_id=f"{algorithm}:ts_cv-{n_splits}",
            dataset_name=dataset_name,
            evaluated_at=datetime.now(UTC),
        ),
        data=EvalMetrics(
            scores=MappingProxyType(aggregated),
            details=MappingProxyType(
                {"n_splits": n_splits, "algorithm": algorithm, "per_fold_metrics": per_fold}
            ),
        ),
    )


class TimeSeriesCrossValidator(_KFoldValidatorBase):
    """Expanding-window time series CV with configurable number of folds."""

    def __init__(
        self,
        *,
        dataset: Knot,
        algorithm: Knot | str,
        metrics: Knot | Sequence[str],
        n_splits: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            algorithm=algorithm,
            metrics=metrics,
            n_splits=n_splits,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest,
        algorithm: str = "",
        metrics: Sequence[str] = (),
        n_splits: int = 5,
        **_: Any,
    ) -> Any:
        """Run expanding-window time series CV and return an EvalMetadata with mean metrics.

        Args:
            dataset: DatasetManifest representing the full time series dataset.
            algorithm: Non-empty algorithm name string.
            metrics: Non-empty sequence of metric name strings.
            n_splits: Number of expanding-window folds; must be an int >= 2.

        Returns:
            EvalReportPayload with averaged metrics and per-fold details.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If any fold evaluator does not return an EvalReportPayload.
        """
        if not isinstance(n_splits, int):
            raise TypeError("TimeSeriesCrossValidator: n_splits must be an int")
        if n_splits < 2:
            raise ValueError("TimeSeriesCrossValidator: n_splits must be >= 2")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("TimeSeriesCrossValidator: algorithm must be a non-empty string")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("TimeSeriesCrossValidator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "TimeSeriesCrossValidator: every metric name must be a non-empty string"
                )
        fold_nodes = [
            self._expanding_window_fold(dataset, fold_index, n_splits)
            for fold_index in range(n_splits)
        ]
        eval_nodes = self._wire_folds(fold_nodes, algorithm, metric_tuple)
        algorithm_node = Parameter(
            "algorithm", str, default=algorithm, _config=KnotConfig(id="algorithm")
        )
        dataset_name_node = Parameter(
            "dataset_name", str, default=dataset.name, _config=KnotConfig(id="dataset_name")
        )
        n_splits_node = Parameter(
            "n_splits", int, default=n_splits, _config=KnotConfig(id="n_splits")
        )
        collected = self._collect(eval_nodes, collect_id="collect-reports")
        return _aggregate_ts_cv_reports(
            reports=collected,
            algorithm=algorithm_node,
            dataset_name=dataset_name_node,
            n_splits=n_splits_node,
            _config=KnotConfig(id="aggregate"),
        )

    @staticmethod
    def _expanding_window_fold(dataset: DatasetManifest, fold_index: int, n_splits: int) -> Knot:
        train_rows = (fold_index + 1) * max(1, dataset.row_count // (n_splits + 1))
        test_rows = max(1, dataset.row_count // (n_splits + 1))
        train_ds = DatasetManifest(
            name=f"{dataset.name}:ts_train_{fold_index}",
            feature_names=dataset.feature_names,
            target_name=dataset.target_name,
            row_count=train_rows,
            source_uri=dataset.source_uri,
        )
        test_ds = DatasetManifest(
            name=f"{dataset.name}:ts_test_{fold_index}",
            feature_names=dataset.feature_names,
            target_name=dataset.target_name,
            row_count=test_rows,
            source_uri=dataset.source_uri,
        )
        fold = SplitManifest(train=train_ds, test=test_ds)
        return Parameter(
            f"split_{fold_index}",
            SplitManifest,
            default=fold,
            _config=KnotConfig(id=f"split_{fold_index}"),
        )
