"""Tests for :class:`TimeSeriesCrossValidator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.time_series_cross_validator import (
    TimeSeriesCrossValidator,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="ts", feature_names=("t", "v"), target_name="y", row_count=120
    )


class TestConstruction:
    def test_rejects_n_splits_below_two(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with pytest.raises(ValueError, match="n_splits must be >= 2"):
                TimeSeriesCrossValidator(
                    dataset=dataset,
                    algorithm="rf",
                    metrics=("rmse",),
                    n_splits=1,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with pytest.raises(ValueError, match="algorithm"):
                TimeSeriesCrossValidator(
                    dataset=dataset,
                    algorithm="",
                    metrics=("rmse",),
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath:
    async def test_returns_eval_report_with_correct_n_splits(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            TimeSeriesCrossValidator(
                dataset=dataset,
                algorithm="ridge",
                metrics=("rmse",),
                n_splits=3,
                _config=KnotConfig(id="tscv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["tscv"]
        assert isinstance(report, EvalReport)
        assert "rmse" in report.metrics
        assert report.details["n_splits"] == 3
        per_fold = report.details["per_fold_metrics"]
        assert isinstance(per_fold, list) and len(per_fold) == 3

    async def test_model_id_contains_algorithm(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            TimeSeriesCrossValidator(
                dataset=dataset,
                algorithm="xgb",
                metrics=("mae",),
                n_splits=2,
                _config=KnotConfig(id="tscv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["tscv"]
        assert "xgb" in report.model_id
