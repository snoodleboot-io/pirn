"""``KFoldCrossValidator`` — plain K-fold cross-validation.

Splits the upstream :class:`DatasetManifest` into K folds, trains and evaluates
on each fold, and returns a single :class:`EvalMetadata` whose metrics are
the mean and standard deviation across all folds.

Algorithm:
    1. Receive ``dataset`` (DatasetManifest), ``algorithm``, ``metrics``, and ``k`` via process().
    2. Validate all inputs.
    3. Extract k logical folds via
       :meth:`~pirn_ml.specializations.experiments._kfold_validator_base._KFoldValidatorBase._extract_folds_via_cross_validator`.
    4. Wire Trainer + Evaluator per fold (shared wiring in
       :class:`~pirn_ml.specializations.experiments._kfold_validator_base._KFoldValidatorBase`).
    5. Aggregate per-fold metrics (mean ± std) and return an EvalMetadata.

Math:
    mean = sum(fold_metric) / k
    std = sqrt(sum((fold_metric - mean)^2) / k)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import math
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


@KnotFactory.knot
async def _aggregate_kfold_reports(
    reports: list[EvalReportPayload],
    algorithm: str,
    dataset_name: str,
    k: int,
) -> EvalReportPayload:
    per_fold = [
        {name: float(value) for name, value in report.metrics.scores.items()} for report in reports
    ]
    if not per_fold:
        aggregated: dict[str, float] = {}
    else:
        names = per_fold[0].keys()
        result: dict[str, float] = {}
        for name in names:
            values = [fold[name] for fold in per_fold]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            result[f"{name}_mean"] = mean
            result[f"{name}_std"] = math.sqrt(variance)
        aggregated = result
    return EvalReportPayload(
        metadata=EvalMetadata(
            model_id=f"{algorithm}:kfold-{k}",
            dataset_name=dataset_name,
            evaluated_at=datetime.now(UTC),
        ),
        data=EvalMetrics(
            scores=MappingProxyType(aggregated),
            details=MappingProxyType(
                {"k": k, "algorithm": algorithm, "per_fold_metrics": per_fold}
            ),
        ),
    )


class KFoldCrossValidator(_KFoldValidatorBase):
    """K-fold cross-validation that returns mean ± std metrics across folds."""

    def __init__(
        self,
        *,
        dataset: Knot,
        algorithm: Knot | str,
        metrics: Knot | Sequence[str],
        k: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            algorithm=algorithm,
            metrics=metrics,
            k=k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest,
        algorithm: str = "",
        metrics: Sequence[str] = (),
        k: int = 5,
        **_: Any,
    ) -> Any:
        """Run K-fold cross-validation and return an EvalReportPayload with mean and std metrics.

        Args:
            dataset: DatasetManifest to partition into k folds.
            algorithm: Non-empty algorithm name string.
            metrics: Non-empty sequence of metric name strings.
            k: Number of folds; must be an int >= 2.

        Returns:
            EvalReportPayload with ``<metric>_mean`` and ``<metric>_std`` keys plus
            per-fold details.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If any fold evaluator does not return an EvalReportPayload.
        """
        if not isinstance(k, int):
            raise TypeError("KFoldCrossValidator: k must be an int")
        if k < 2:
            raise ValueError("KFoldCrossValidator: k must be >= 2")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("KFoldCrossValidator: algorithm must be a non-empty string")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("KFoldCrossValidator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "KFoldCrossValidator: every metric name must be a non-empty string"
                )
        dataset_node = Parameter(
            "dataset", DatasetManifest, default=dataset, _config=KnotConfig(id="dataset")
        )
        fold_nodes = self._extract_folds_via_cross_validator(dataset_node, k)
        eval_nodes = self._wire_folds(fold_nodes, algorithm, metric_tuple)
        algorithm_node = Parameter(
            "algorithm", str, default=algorithm, _config=KnotConfig(id="algorithm")
        )
        dataset_name_node = Parameter(
            "dataset_name", str, default=dataset.name, _config=KnotConfig(id="dataset_name")
        )
        k_node = Parameter("k", int, default=k, _config=KnotConfig(id="k"))
        collected = self._collect(eval_nodes, collect_id="collect")
        return _aggregate_kfold_reports(
            reports=collected,
            algorithm=algorithm_node,
            dataset_name=dataset_name_node,
            k=k_node,
            _config=KnotConfig(id="aggregate"),
        )
