"""``WalkForwardValidator`` — SubTapestry that performs walk-forward
cross-validation for time-series models.

The window slides forward in fixed-size steps. At each step the
validator carves an in-sample partition of ``train_window`` rows and an
out-of-sample partition of ``test_window`` rows from the upstream
:class:`DatasetManifest`, trains a model on the in-sample partition, and
evaluates on the out-of-sample partition.

The output is the per-step list of :class:`EvalMetadata`s, one per fold.

Algorithm:
    1. Receive ``dataset`` (DatasetManifest), ``time_column``, ``train_window``,
       ``test_window``, ``algorithm``, and ``n_steps`` via process().
    2. Validate all window parameters; verify dataset has enough rows.
    3. For each step, create train/test partitions as DatasetManifest slices.
    4. Wire an inner Tapestry with Trainer + Evaluator for each step.
    5. Run each inner Tapestry via _run_inner() and collect EvalReports.

Math:
    required_rows = train_window + test_window * n_steps

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _collect_walk_forward_reports(
    reports: list[EvalReportPayload],
) -> tuple[EvalReportPayload, ...]:
    return tuple(reports)


class WalkForwardValidator(SubTapestry):
    """Walk-forward CV for time-series models."""

    def __init__(
        self,
        *,
        dataset: Knot,
        time_column: Knot | str,
        train_window: Knot | int,
        test_window: Knot | int,
        algorithm: Knot | str,
        n_steps: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            time_column=time_column,
            train_window=train_window,
            test_window=test_window,
            algorithm=algorithm,
            n_steps=n_steps,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest,
        time_column: str = "",
        train_window: int = 1,
        test_window: int = 1,
        algorithm: str = "",
        n_steps: int = 5,
        **_: Any,
    ) -> Any:
        """Slide a training window across the dataset for each step and return a tuple of per-fold EvalReports.

        Args:
            dataset: DatasetManifest reference providing row_count for window partitioning.
            time_column: Non-empty time column name string.
            train_window: Number of rows in each training window; must be >= 1.
            test_window: Number of rows in each test window; must be >= 1.
            algorithm: Non-empty algorithm name string.
            n_steps: Number of walk-forward steps; must be >= 1.

        Returns:
            Tuple of EvalMetadata objects, one per walk-forward step.

        Raises:
            ValueError: If any window parameter is invalid or dataset has insufficient rows.
            TypeError: If train_window, test_window, or n_steps are not ints.
        """
        if not isinstance(time_column, str) or not time_column:
            raise ValueError("WalkForwardValidator: time_column must be a non-empty string")
        if not isinstance(train_window, int):
            raise TypeError("WalkForwardValidator: train_window must be an int")
        if train_window < 1:
            raise ValueError("WalkForwardValidator: train_window must be >= 1")
        if not isinstance(test_window, int):
            raise TypeError("WalkForwardValidator: test_window must be an int")
        if test_window < 1:
            raise ValueError("WalkForwardValidator: test_window must be >= 1")
        if not isinstance(n_steps, int):
            raise TypeError("WalkForwardValidator: n_steps must be an int")
        if n_steps < 1:
            raise ValueError("WalkForwardValidator: n_steps must be >= 1")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("WalkForwardValidator: algorithm must be a non-empty string")
        required = train_window + test_window * n_steps
        if int(dataset.row_count) < required:
            raise ValueError(
                "WalkForwardValidator: dataset.row_count is too small for "
                f"{n_steps} steps with train_window={train_window}, "
                f"test_window={test_window}; need at least {required} rows"
            )
        now = datetime.now(UTC)
        eval_nodes = []
        for step in range(n_steps):
            train_partition = self._mk(dataset, step, "train", train_window, now)
            test_partition = self._mk(dataset, step, "test", test_window, now)
            split_value = SplitManifest(
                train=train_partition,
                test=test_partition,
                validation=None,
            )
            split_node = _emit_value(
                value=split_value,
                _config=KnotConfig(id=f"split-step-{step}"),
            )
            trainer = Trainer(
                split=split_node,
                algorithm=algorithm,
                _config=KnotConfig(id=f"train-step-{step}"),
            )
            eval_nodes.append(
                Evaluator(
                    model=trainer,
                    split=split_node,
                    metrics=("mape", "smape", "mase"),
                    _config=KnotConfig(id=f"evaluate-step-{step}"),
                )
            )
        collected = Aggregator(
            combine=lambda **kw: list(kw.values()),
            _config=KnotConfig(id="collect-reports"),
            **{f"r{i}": eval_nodes[i] for i in range(n_steps)},
        )
        return _collect_walk_forward_reports(
            reports=collected,
            _config=KnotConfig(id="collect"),
        )

    def _mk(
        self,
        source: DatasetManifest,
        step: int,
        partition: str,
        count: int,
        fetched_at: datetime,
    ) -> DatasetManifest:
        return DatasetManifest(
            name=f"{source.name}:walk{step}:{partition}",
            feature_names=source.feature_names,
            target_name=source.target_name,
            row_count=count,
            source_uri=source.source_uri,
            fetched_at=fetched_at,
        )
