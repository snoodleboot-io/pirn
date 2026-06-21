"""``TimeSeriesSplitterValidator`` — walk-forward time-series CV.

Splits the upstream :class:`DatasetManifest` chronologically: each split's
train partition contains rows up to a cut point, the test partition
contains the next chunk. The cut points are evenly distributed across
the row range so consecutive splits expand the train window forward
in time.

The orchestration layer's logical splitting computes row counts only;
concrete subclasses must consult the actual ``time_column`` for ordering
the rows on a real dataset.

Algorithm:
    1. Receive ``dataset`` (DatasetManifest), ``time_column``, ``algorithm``,
       ``metrics``, and ``n_splits`` via process().
    2. Validate all inputs.
    3. Build chronological train/test splits via row-count partitioning.
    4. Wire Trainer + Evaluator per split in an inner Tapestry.
    5. Aggregate per-split metrics and return an EvalMetadata.

Math:
    chunk = row_count // (n_splits + 1)
    train_rows[i] = chunk * (i + 1)
    test_rows = chunk
    mean_metric = sum(split_metric) / n_splits

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
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

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
async def _aggregate_tscv_reports(
    reports: list[EvalReportPayload],
    algorithm: str,
    dataset_name: str,
    n_splits: int,
    time_column: str,
) -> EvalReportPayload:
    per_split = [
        {name: float(value) for name, value in report.metrics.scores.items()} for report in reports
    ]
    if not per_split:
        aggregated: dict[str, float] = {}
    else:
        names = per_split[0].keys()
        aggregated = {
            name: sum(s[name] for s in per_split) / float(len(per_split)) for name in names
        }
    return EvalReportPayload(
        metadata=EvalMetadata(
            model_id=f"{algorithm}:tscv-{n_splits}",
            dataset_name=dataset_name,
            evaluated_at=datetime.now(UTC),
        ),
        data=EvalMetrics(
            scores=MappingProxyType(aggregated),
            details=MappingProxyType(
                {
                    "n_splits": n_splits,
                    "time_column": time_column,
                    "algorithm": algorithm,
                    "per_split_metrics": per_split,
                }
            ),
        ),
    )


class TimeSeriesSplitterValidator(SubTapestry):
    """Walk-forward time-series cross-validation."""

    def __init__(
        self,
        *,
        dataset: Knot,
        time_column: Knot | str,
        algorithm: Knot | str,
        metrics: Knot | Sequence[str],
        n_splits: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            time_column=time_column,
            algorithm=algorithm,
            metrics=metrics,
            n_splits=n_splits,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest,
        time_column: str = "",
        algorithm: str = "",
        metrics: Sequence[str] = (),
        n_splits: int = 5,
        **_: Any,
    ) -> Any:
        """Partition the dataset into chronological expanding-window splits, train and evaluate each, and return an aggregate EvalMetadata.

        Args:
            dataset: DatasetManifest reference to partition into chronological splits.
            time_column: Non-empty name of the time ordering column.
            algorithm: Non-empty algorithm name string.
            metrics: Non-empty sequence of metric name strings.
            n_splits: Number of walk-forward splits; must be an int >= 2.

        Returns:
            EvalReportPayload with averaged per-split metrics and split details in the details dict.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If any inner split evaluator does not return an EvalReportPayload.
        """
        if not isinstance(time_column, str) or not time_column:
            raise ValueError("TimeSeriesSplitterValidator: time_column must be a non-empty string")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("TimeSeriesSplitterValidator: algorithm must be a non-empty string")
        if not isinstance(n_splits, int):
            raise TypeError("TimeSeriesSplitterValidator: n_splits must be an int")
        if n_splits < 2:
            raise ValueError("TimeSeriesSplitterValidator: n_splits must be >= 2")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("TimeSeriesSplitterValidator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "TimeSeriesSplitterValidator: every metric name must be a non-empty string"
                )
        splits = self._build_splits(dataset, n_splits)
        eval_nodes = []
        for split_index, split in enumerate(splits):
            split_node = _emit_value(
                value=split,
                _config=KnotConfig(id=f"split_{split_index}"),
            )
            model = Trainer(
                split=split_node,
                algorithm=algorithm,
                hyperparameters={"split_index": split_index},
                _config=KnotConfig(id=f"train_{split_index}"),
            )
            eval_nodes.append(
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=metric_tuple,
                    _config=KnotConfig(id=f"evaluate_{split_index}"),
                )
            )
        algorithm_node = _emit_value(value=algorithm, _config=KnotConfig(id="algorithm"))
        dataset_name_node = _emit_value(value=dataset.name, _config=KnotConfig(id="dataset_name"))
        n_splits_node = _emit_value(value=n_splits, _config=KnotConfig(id="n_splits"))
        time_column_node = _emit_value(value=time_column, _config=KnotConfig(id="time_column"))
        collected = Aggregator(
            combine=lambda **kw: list(kw.values()),
            _config=KnotConfig(id="collect-reports"),
            **{f"r{i}": eval_nodes[i] for i in range(n_splits)},
        )
        return _aggregate_tscv_reports(
            reports=collected,
            algorithm=algorithm_node,
            dataset_name=dataset_name_node,
            n_splits=n_splits_node,
            time_column=time_column_node,
            _config=KnotConfig(id="aggregate"),
        )

    def _build_splits(self, dataset: DatasetManifest, n_splits: int) -> list[SplitManifest]:
        total = int(dataset.row_count)
        if total < n_splits + 1:
            raise ValueError(
                "TimeSeriesSplitterValidator: dataset.row_count must be at least n_splits + 1"
            )
        chunk = total // (n_splits + 1)
        splits: list[SplitManifest] = []
        now = datetime.now(UTC)
        for split_index in range(n_splits):
            train_count = chunk * (split_index + 1)
            test_count = chunk
            train = DatasetManifest(
                name=f"{dataset.name}:tscv{split_index}:train",
                feature_names=dataset.feature_names,
                target_name=dataset.target_name,
                row_count=train_count,
                source_uri=dataset.source_uri,
                fetched_at=now,
            )
            test = DatasetManifest(
                name=f"{dataset.name}:tscv{split_index}:test",
                feature_names=dataset.feature_names,
                target_name=dataset.target_name,
                row_count=test_count,
                source_uri=dataset.source_uri,
                fetched_at=now,
            )
            splits.append(SplitManifest(train=train, test=test, validation=None))
        return splits
