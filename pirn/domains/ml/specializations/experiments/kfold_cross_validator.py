"""``KFoldCrossValidator`` — plain K-fold cross-validation.

Splits the upstream :class:`MLDataset` into K folds, trains and evaluates
on each fold, and returns a single :class:`EvalReport` whose metrics are
the mean and standard deviation across all folds.
"""

from __future__ import annotations

import math
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


class KFoldCrossValidator(SubTapestry):
    """K-fold cross-validation that returns mean ± std metrics across folds."""

    def __init__(
        self,
        *,
        dataset: Knot,
        algorithm: str,
        metrics: Sequence[str],
        k: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(dataset, Knot):
            raise TypeError("KFoldCrossValidator: dataset must be a Knot")
        if not isinstance(k, int):
            raise TypeError("KFoldCrossValidator: k must be an int")
        if k < 2:
            raise ValueError("KFoldCrossValidator: k must be >= 2")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "KFoldCrossValidator: algorithm must be a non-empty string"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("KFoldCrossValidator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "KFoldCrossValidator: every metric name must be a "
                    "non-empty string"
                )
        self._k = k
        self._algorithm = algorithm
        self._metrics = metric_tuple
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> EvalReport:
        """Run K-fold cross-validation and return an EvalReport with mean and std metrics.

        Args:
            dataset: MLDataset to partition into k folds.

        Returns:
            EvalReport with ``<metric>_mean`` and ``<metric>_std`` keys plus
            per-fold details.

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
                    f"KFoldCrossValidator: fold {fold_index} did not produce "
                    "an EvalReport"
                )
            per_fold.append(
                {name: float(value) for name, value in report.metrics.items()}
            )

        aggregated = self._aggregate(per_fold)
        return EvalReport(
            model_id=f"{self._algorithm}:kfold-{self._k}",
            dataset_name=dataset.name,
            metrics=MappingProxyType(aggregated),
            details=MappingProxyType(
                {
                    "k": self._k,
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
        result: dict[str, float] = {}
        for name in names:
            values = [fold[name] for fold in per_fold]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            result[f"{name}_mean"] = mean
            result[f"{name}_std"] = math.sqrt(variance)
        return result
