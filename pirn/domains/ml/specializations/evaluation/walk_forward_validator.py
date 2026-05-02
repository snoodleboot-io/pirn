"""``WalkForwardValidator`` — SubTapestry that performs walk-forward
cross-validation for time-series models.

The window slides forward in fixed-size steps. At each step the
validator carves an in-sample partition of ``train_window`` rows and an
out-of-sample partition of ``test_window`` rows from the upstream
:class:`MLDataset`, trains a model on the in-sample partition, and
evaluates on the out-of-sample partition.

The output is the per-step list of :class:`EvalReport`s, one per fold.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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


class WalkForwardValidator(SubTapestry):
    """Walk-forward CV for time-series models."""

    def __init__(
        self,
        *,
        dataset: Knot,
        time_column: str,
        train_window: int,
        test_window: int,
        algorithm: str,
        n_steps: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(dataset, Knot):
            raise TypeError("WalkForwardValidator: dataset must be a Knot")
        if not isinstance(time_column, str) or not time_column:
            raise ValueError(
                "WalkForwardValidator: time_column must be a non-empty string"
            )
        if not isinstance(train_window, int):
            raise TypeError(
                "WalkForwardValidator: train_window must be an int"
            )
        if train_window < 1:
            raise ValueError(
                "WalkForwardValidator: train_window must be >= 1"
            )
        if not isinstance(test_window, int):
            raise TypeError(
                "WalkForwardValidator: test_window must be an int"
            )
        if test_window < 1:
            raise ValueError(
                "WalkForwardValidator: test_window must be >= 1"
            )
        if not isinstance(n_steps, int):
            raise TypeError("WalkForwardValidator: n_steps must be an int")
        if n_steps < 1:
            raise ValueError("WalkForwardValidator: n_steps must be >= 1")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "WalkForwardValidator: algorithm must be a non-empty string"
            )
        self._time_column = time_column
        self._train_window = train_window
        self._test_window = test_window
        self._n_steps = n_steps
        self._algorithm = algorithm
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    @property
    def n_steps(self) -> int:
        return self._n_steps

    async def process(
        self, dataset: MLDataset, **_: Any
    ) -> tuple[EvalReport, ...]:
        required = self._train_window + self._test_window * self._n_steps
        if int(dataset.row_count) < required:
            raise ValueError(
                "WalkForwardValidator: dataset.row_count is too small for "
                f"{self._n_steps} steps with train_window={self._train_window}, "
                f"test_window={self._test_window}; need at least {required} rows"
            )
        reports: list[EvalReport] = []
        now = datetime.now(timezone.utc)
        for step in range(self._n_steps):
            train_partition = self._mk(
                dataset, step, "train", self._train_window, now
            )
            test_partition = self._mk(
                dataset, step, "test", self._test_window, now
            )
            split_value = DataSplit(
                train=train_partition,
                test=test_partition,
                validation=None,
            )
            with Tapestry() as inner:
                split_node = _emit_value(
                    value=split_value,
                    _config=KnotConfig(id=f"split-step-{step}"),
                )
                trainer = Trainer(
                    split=split_node,
                    algorithm=self._algorithm,
                    _config=KnotConfig(id=f"train-step-{step}"),
                )
                Evaluator(
                    model=trainer,
                    split=split_node,
                    metrics=("mape", "smape", "mase"),
                    _config=KnotConfig(id=f"evaluate-step-{step}"),
                )
            inner_result = await self._run_inner(inner)
            reports.append(inner_result.outputs[f"evaluate-step-{step}"])
        return tuple(reports)

    def _mk(
        self,
        source: MLDataset,
        step: int,
        partition: str,
        count: int,
        fetched_at: datetime,
    ) -> MLDataset:
        return MLDataset(
            name=f"{source.name}:walk{step}:{partition}",
            feature_names=source.feature_names,
            target_name=source.target_name,
            row_count=count,
            source_uri=source.source_uri,
            fetched_at=fetched_at,
        )
