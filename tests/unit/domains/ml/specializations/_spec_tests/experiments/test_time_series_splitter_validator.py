"""Tests for :class:`TimeSeriesSplitterValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.time_series_splitter_validator import (
    TimeSeriesSplitterValidator,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> DatasetManifest:
    return DatasetManifest(
        name="ts",
        feature_names=("a", "b"),
        target_name="y",
        row_count=120,
    )


def _make_validator() -> TimeSeriesSplitterValidator:
    with Tapestry():
        dataset = emit_dataset(_config=KnotConfig(id="dataset"))
        validator = TimeSeriesSplitterValidator(
            dataset=dataset,
            time_column="t",
            algorithm="rf",
            metrics=("rmse",),
            n_splits=3,
            _config=KnotConfig(id="tscv"),
        )
    return validator


def _dataset_fixture() -> DatasetManifest:
    return DatasetManifest(
        name="ts", feature_names=("a", "b"), target_name="y", row_count=120
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_splits_below_two(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                time_column="t",
                algorithm="rf",
                metrics=("rmse",),
                n_splits=1,
            )

    async def test_rejects_empty_time_column(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                time_column="",
                algorithm="rf",
                metrics=("rmse",),
                n_splits=3,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_aggregates_metrics_across_walk_forward_splits(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            TimeSeriesSplitterValidator(
                dataset=dataset,
                time_column="t",
                algorithm="rf",
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
        per_split = report.metrics.details["per_split_metrics"]
        assert isinstance(per_split, list) and len(per_split) == 3
