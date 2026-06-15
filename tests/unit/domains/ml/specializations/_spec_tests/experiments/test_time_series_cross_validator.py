"""Tests for :class:`TimeSeriesCrossValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.time_series_cross_validator import (
    TimeSeriesCrossValidator,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> DatasetManifest:
    return DatasetManifest(
        name="ts", feature_names=("t", "v"), target_name="y", row_count=120
    )


def _make_validator() -> TimeSeriesCrossValidator:
    with Tapestry():
        dataset = emit_dataset(_config=KnotConfig(id="dataset"))
        validator = TimeSeriesCrossValidator(
            dataset=dataset,
            algorithm="rf",
            metrics=("rmse",),
            n_splits=3,
            _config=KnotConfig(id="tscv"),
        )
    return validator


def _dataset_fixture() -> DatasetManifest:
    return DatasetManifest(
        name="ts", feature_names=("t", "v"), target_name="y", row_count=120
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_splits_below_two(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset, algorithm="rf", metrics=("rmse",), n_splits=1
            )

    async def test_rejects_empty_algorithm(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset, algorithm="", metrics=("rmse",), n_splits=3
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
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
        assert isinstance(report, EvalReportPayload)
        assert "rmse" in report.metrics.scores
        assert report.metrics.details["n_splits"] == 3
        per_fold = report.metrics.details["per_fold_metrics"]
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
        assert "xgb" in report.report.model_id
