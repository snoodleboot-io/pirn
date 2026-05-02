"""``TimeSeriesSplitterValidator`` — walk-forward time-series CV.

Splits the upstream :class:`MLDataset` chronologically: each split's
train partition contains rows up to a cut point, the test partition
contains the next chunk. The cut points are evenly distributed across
the row range so consecutive splits expand the train window forward
in time.

The orchestration layer's logical splitting computes row counts only;
concrete subclasses must consult the actual ``time_column`` for ordering
the rows on a real dataset.
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


class TimeSeriesSplitterValidator(SubTapestry):
    """Walk-forward time-series cross-validation."""

    def __init__(
        self,
        *,
        dataset: Knot,
        time_column: str,
        algorithm: str,
        metrics: Sequence[str],
        n_splits: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(dataset, Knot):
            raise TypeError(
                "TimeSeriesSplitterValidator: dataset must be a Knot"
            )
        if not isinstance(time_column, str) or not time_column:
            raise ValueError(
                "TimeSeriesSplitterValidator: time_column must be a "
                "non-empty string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "TimeSeriesSplitterValidator: algorithm must be a non-empty "
                "string"
            )
        if not isinstance(n_splits, int):
            raise TypeError(
                "TimeSeriesSplitterValidator: n_splits must be an int"
            )
        if n_splits < 2:
            raise ValueError(
                "TimeSeriesSplitterValidator: n_splits must be >= 2"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "TimeSeriesSplitterValidator: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "TimeSeriesSplitterValidator: every metric name must "
                    "be a non-empty string"
                )
        self._time_column = time_column
        self._algorithm = algorithm
        self._metrics = metric_tuple
        self._n_splits = n_splits
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> EvalReport:
        splits = self._build_splits(dataset)
        per_split_metrics: list[dict[str, float]] = []
        with Tapestry() as inner:
            for split_index, split in enumerate(splits):
                split_node = _emit_value(
                    value=split,
                    _config=KnotConfig(id=f"split_{split_index}"),
                )
                model = Trainer(
                    split=split_node,
                    algorithm=self._algorithm,
                    hyperparameters={"split_index": split_index},
                    _config=KnotConfig(id=f"train_{split_index}"),
                )
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=self._metrics,
                    _config=KnotConfig(id=f"evaluate_{split_index}"),
                )
        result = await self._run_inner(inner)
        for split_index in range(len(splits)):
            report = result.outputs[f"evaluate_{split_index}"]
            if not isinstance(report, EvalReport):
                raise TypeError(
                    f"TimeSeriesSplitterValidator: split {split_index} did "
                    "not produce an EvalReport"
                )
            per_split_metrics.append(
                {name: float(value) for name, value in report.metrics.items()}
            )
        aggregated = self._aggregate(per_split_metrics)
        return EvalReport(
            model_id=f"{self._algorithm}:tscv-{self._n_splits}",
            dataset_name=dataset.name,
            metrics=MappingProxyType(aggregated),
            details=MappingProxyType(
                {
                    "n_splits": self._n_splits,
                    "time_column": self._time_column,
                    "algorithm": self._algorithm,
                    "per_split_metrics": per_split_metrics,
                }
            ),
            evaluated_at=datetime.now(timezone.utc),
        )

    def _build_splits(self, dataset: MLDataset) -> list[DataSplit]:
        total = int(dataset.row_count)
        if total < self._n_splits + 1:
            raise ValueError(
                "TimeSeriesSplitterValidator: dataset.row_count must be at "
                "least n_splits + 1"
            )
        chunk = total // (self._n_splits + 1)
        splits: list[DataSplit] = []
        now = datetime.now(timezone.utc)
        for split_index in range(self._n_splits):
            train_count = chunk * (split_index + 1)
            test_count = chunk
            train = MLDataset(
                name=f"{dataset.name}:tscv{split_index}:train",
                feature_names=dataset.feature_names,
                target_name=dataset.target_name,
                row_count=train_count,
                source_uri=dataset.source_uri,
                fetched_at=now,
            )
            test = MLDataset(
                name=f"{dataset.name}:tscv{split_index}:test",
                feature_names=dataset.feature_names,
                target_name=dataset.target_name,
                row_count=test_count,
                source_uri=dataset.source_uri,
                fetched_at=now,
            )
            splits.append(DataSplit(train=train, test=test, validation=None))
        return splits

    def _aggregate(
        self, per_split_metrics: list[dict[str, float]]
    ) -> dict[str, float]:
        if not per_split_metrics:
            return {}
        names = per_split_metrics[0].keys()
        return {
            name: sum(split[name] for split in per_split_metrics)
            / float(len(per_split_metrics))
            for name in names
        }
