"""``TimeSeriesCrossValidator`` — expanding-window time series cross-validation.

Each fold adds one period of training data and evaluates on the next
period. Returns a single :class:`EvalReport` with mean metrics across folds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
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


class TimeSeriesCrossValidator(SubTapestry):
    """Expanding-window time series CV with configurable number of folds."""

    def __init__(
        self,
        *,
        dataset: Knot,
        algorithm: str,
        metrics: Sequence[str],
        n_splits: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(dataset, Knot):
            raise TypeError(
                "TimeSeriesCrossValidator: dataset must be a Knot"
            )
        if not isinstance(n_splits, int):
            raise TypeError(
                "TimeSeriesCrossValidator: n_splits must be an int"
            )
        if n_splits < 2:
            raise ValueError(
                "TimeSeriesCrossValidator: n_splits must be >= 2"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "TimeSeriesCrossValidator: algorithm must be a non-empty "
                "string"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "TimeSeriesCrossValidator: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "TimeSeriesCrossValidator: every metric name must be a "
                    "non-empty string"
                )
        self._n_splits = n_splits
        self._algorithm = algorithm
        self._metrics = metric_tuple
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> EvalReport:
        """Run expanding-window time series CV and return an EvalReport with mean metrics.

        Args:
            dataset: MLDataset representing the full time series dataset.

        Returns:
            EvalReport with averaged metrics and per-fold details.

        Raises:
            TypeError: If any fold evaluator does not return an EvalReport.
        """
        per_fold: list[dict[str, float]] = []

        with Tapestry() as inner_eval:
            for fold_index in range(self._n_splits):
                train_rows = (fold_index + 1) * max(
                    1, dataset.row_count // (self._n_splits + 1)
                )
                test_rows = max(
                    1, dataset.row_count // (self._n_splits + 1)
                )
                train_ds = MLDataset(
                    name=f"{dataset.name}:ts_train_{fold_index}",
                    feature_names=dataset.feature_names,
                    target_name=dataset.target_name,
                    row_count=train_rows,
                    source_uri=dataset.source_uri,
                )
                test_ds = MLDataset(
                    name=f"{dataset.name}:ts_test_{fold_index}",
                    feature_names=dataset.feature_names,
                    target_name=dataset.target_name,
                    row_count=test_rows,
                    source_uri=dataset.source_uri,
                )
                fold = DataSplit(train=train_ds, test=test_ds)
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

        for fold_index in range(self._n_splits):
            report = eval_result.outputs[f"evaluate_{fold_index}"]
            if not isinstance(report, EvalReport):
                raise TypeError(
                    f"TimeSeriesCrossValidator: fold {fold_index} did not "
                    "produce an EvalReport"
                )
            per_fold.append(
                {name: float(value) for name, value in report.metrics.items()}
            )

        aggregated = self._aggregate(per_fold)
        return EvalReport(
            model_id=f"{self._algorithm}:ts_cv-{self._n_splits}",
            dataset_name=dataset.name,
            metrics=MappingProxyType(aggregated),
            details=MappingProxyType(
                {
                    "n_splits": self._n_splits,
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
