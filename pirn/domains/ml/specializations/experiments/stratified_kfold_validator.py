"""``StratifiedKFoldValidator`` — K-fold cross-validation with target
stratification.

Composition:

1. :class:`CrossValidator` produces ``k`` logical :class:`SplitManifest`
   folds from the upstream :class:`DatasetManifest`.
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
    3. Wire CrossValidator in an inner Tapestry to produce k folds.
    4. Wire Trainer + Evaluator per fold in a second inner Tapestry.
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


class StratifiedKFoldValidator(SubTapestry):
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
    ) -> EvalReportPayload:
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
        with Tapestry() as inner:
            dataset_node = _emit_value(value=dataset, _config=KnotConfig(id="dataset"))
            CrossValidator(
                dataset=dataset_node,
                k=k,
                _config=KnotConfig(id="folds"),
            )
        folds_result = await self._run_inner(inner)
        folds: tuple[SplitManifest, ...] = folds_result.outputs["folds"]
        per_fold_metrics: list[dict[str, float]] = []
        with Tapestry() as inner_eval:
            for fold_index, fold in enumerate(folds):
                split_node = _emit_value(
                    value=fold,
                    _config=KnotConfig(id=f"split_{fold_index}"),
                )
                model = Trainer(
                    split=split_node,
                    algorithm=algorithm,
                    hyperparameters={"fold_index": fold_index},
                    _config=KnotConfig(id=f"train_{fold_index}"),
                )
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=metric_tuple,
                    _config=KnotConfig(id=f"evaluate_{fold_index}"),
                )
        eval_result = await self._run_inner(inner_eval)
        for fold_index in range(len(folds)):
            report = eval_result.outputs[f"evaluate_{fold_index}"]
            if not isinstance(report, EvalReportPayload):
                raise TypeError(
                    f"StratifiedKFoldValidator: fold {fold_index} did not produce an EvalMetadata"
                )
            per_fold_metrics.append(
                {name: float(value) for name, value in report.metrics.scores.items()}
            )
        aggregated = self._aggregate(per_fold_metrics)
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
                        "stratify_column": stratify_column,
                        "algorithm": algorithm,
                        "per_fold_metrics": per_fold_metrics,
                    }
                ),
            ),
        )

    def _aggregate(self, per_fold_metrics: list[dict[str, float]]) -> dict[str, float]:
        if not per_fold_metrics:
            return {}
        names = per_fold_metrics[0].keys()
        return {
            name: sum(fold[name] for fold in per_fold_metrics) / float(len(per_fold_metrics))
            for name in names
        }
