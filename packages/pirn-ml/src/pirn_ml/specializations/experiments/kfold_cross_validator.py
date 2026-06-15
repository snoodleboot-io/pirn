"""``KFoldCrossValidator`` — plain K-fold cross-validation.

Splits the upstream :class:`DatasetManifest` into K folds, trains and evaluates
on each fold, and returns a single :class:`EvalMetadata` whose metrics are
the mean and standard deviation across all folds.

Algorithm:
    1. Receive ``dataset`` (DatasetManifest), ``algorithm``, ``metrics``, and ``k`` via process().
    2. Validate all inputs.
    3. Wire CrossValidator in an inner Tapestry to produce k folds.
    4. Wire Trainer + Evaluator per fold in a second inner Tapestry.
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
from pirn.core.knot_factory import knot
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.data_prep.cross_validator import CrossValidator
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _extract_fold(folds: tuple[SplitManifest, ...], index: int) -> SplitManifest:
    return folds[index]


@knot
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


class KFoldCrossValidator(SubTapestry):
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
        dataset_node = _emit_value(value=dataset, _config=KnotConfig(id="dataset"))
        folds_node = CrossValidator(
            dataset=dataset_node,
            k=k,
            _config=KnotConfig(id="folds"),
        )
        eval_nodes = []
        for fold_index in range(k):
            fold_index_node = _emit_value(
                value=fold_index, _config=KnotConfig(id=f"fold_index_{fold_index}")
            )
            split_node = _extract_fold(
                folds=folds_node,
                index=fold_index_node,
                _config=KnotConfig(id=f"split_{fold_index}"),
            )
            model = Trainer(
                split=split_node,
                algorithm=algorithm,
                _config=KnotConfig(id=f"train_{fold_index}"),
            )
            eval_nodes.append(
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=metric_tuple,
                    _config=KnotConfig(id=f"evaluate_{fold_index}"),
                )
            )
        algorithm_node = _emit_value(value=algorithm, _config=KnotConfig(id="algorithm"))
        dataset_name_node = _emit_value(value=dataset.name, _config=KnotConfig(id="dataset_name"))
        k_node = _emit_value(value=k, _config=KnotConfig(id="k"))
        collected = Aggregator(
            combine=lambda **kw: list(kw.values()),
            _config=KnotConfig(id="collect"),
            **{f"r{i}": eval_nodes[i] for i in range(k)},
        )
        return _aggregate_kfold_reports(
            reports=collected,
            algorithm=algorithm_node,
            dataset_name=dataset_name_node,
            k=k_node,
            _config=KnotConfig(id="aggregate"),
        )
