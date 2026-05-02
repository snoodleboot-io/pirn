"""Tests for :class:`WalkForwardValidator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.walk_forward_validator import (
    WalkForwardValidator,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="ts-data",
        feature_names=("a",),
        target_name="y",
        row_count=100,
    )


class TestConstruction:
    def test_rejects_zero_train_window(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="ds"))
            with pytest.raises(ValueError, match="train_window must be >= 1"):
                WalkForwardValidator(
                    dataset=dataset,
                    time_column="ts",
                    train_window=0,
                    test_window=10,
                    algorithm="arima",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="ds"))
            with pytest.raises(ValueError, match="algorithm"):
                WalkForwardValidator(
                    dataset=dataset,
                    time_column="ts",
                    train_window=20,
                    test_window=5,
                    algorithm="",
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_one_report_per_step(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="ds"))
            WalkForwardValidator(
                dataset=dataset,
                time_column="ts",
                train_window=20,
                test_window=5,
                n_steps=3,
                algorithm="arima",
                _config=KnotConfig(id="walk"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        reports = result.outputs["walk"]
        assert isinstance(reports, tuple)
        assert len(reports) == 3
        for report in reports:
            assert isinstance(report, EvalReport)
            assert set(report.metrics.keys()) == {"mape", "smape", "mase"}
