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
from pirn.domains.ml.data_prep.cross_validator import CrossValidator
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_metrics import EvalMetrics
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


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
    ) -> EvalReportPayload:
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
        with Tapestry() as inner:
            dataset_node = _emit_value(value=dataset, _config=KnotConfig(id="dataset"))
            CrossValidator(
                dataset=dataset_node,
                k=k,
                _config=KnotConfig(id="folds"),
            )
        folds_result = await self._run_inner(inner)
        folds: tuple[SplitManifest, ...] = folds_result.outputs["folds"]

        with Tapestry() as inner_eval:
            for fold_index, fold in enumerate(folds):
                split_node = _emit_value(
                    value=fold,
                    _config=KnotConfig(id=f"split_{fold_index}"),
                )
                model = Trainer(
                    split=split_node,
                    algorithm=algorithm,
                    _config=KnotConfig(id=f"train_{fold_index}"),
                )
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=metric_tuple,
                    _config=KnotConfig(id=f"evaluate_{fold_index}"),
                )
        eval_result = await self._run_inner(inner_eval)

        per_fold: list[dict[str, float]] = []
        for fold_index in range(len(folds)):
            report = eval_result.outputs[f"evaluate_{fold_index}"]
            if not isinstance(report, EvalReportPayload):
                raise TypeError(
                    f"KFoldCrossValidator: fold {fold_index} did not produce an EvalReportPayload"
                )
            per_fold.append({name: float(value) for name, value in report.metrics.scores.items()})

        aggregated = self._aggregate(per_fold)
        return EvalReportPayload(
            metadata=EvalMetadata(
                model_id=f"{algorithm}:kfold-{k}",
                dataset_name=dataset.name,
                evaluated_at=datetime.now(UTC),
            ),
            data=EvalMetrics(
                scores=MappingProxyType(aggregated),
                details=MappingProxyType(
                    {
                        "k": k,
                        "algorithm": algorithm,
                        "per_fold_metrics": per_fold,
                    }
                ),
            ),
        )

    def _aggregate(self, per_fold: list[dict[str, float]]) -> dict[str, float]:
        if not per_fold:
            return {}
        names = per_fold[0].keys()
        result: dict[str, float] = {}
        for name in names:
            values = [fold[name] for fold in per_fold]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            result[f"{name}_mean"] = mean
            result[f"{name}_std"] = math.sqrt(variance)
        return result
