"""Tests for :class:`KFoldCrossValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.kfold_cross_validator import (
    KFoldCrossValidator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload


@knot
async def emit_dataset() -> DatasetManifest:
    return DatasetManifest(
        name="d", feature_names=("a", "b"), target_name="y", row_count=100
    )


def _make_validator() -> KFoldCrossValidator:
    with Tapestry():
        dataset = emit_dataset(_config=KnotConfig(id="dataset"))
        validator = KFoldCrossValidator(
            dataset=dataset,
            algorithm="rf",
            metrics=("accuracy",),
            k=3,
            _config=KnotConfig(id="cv"),
        )
    return validator


def _dataset_fixture() -> DatasetManifest:
    return DatasetManifest(
        name="d", feature_names=("a", "b"), target_name="y", row_count=100
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_k_below_two(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(dataset=dataset, algorithm="rf", metrics=("accuracy",), k=1)

    async def test_rejects_empty_algorithm(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(dataset=dataset, algorithm="", metrics=("accuracy",), k=3)

    async def test_rejects_empty_metrics(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(dataset=dataset, algorithm="rf", metrics=(), k=3)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_aggregates_mean_and_std_metrics(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            KFoldCrossValidator(
                dataset=dataset,
                algorithm="rf",
                metrics=("accuracy",),
                k=3,
                _config=KnotConfig(id="cv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["cv"]
        assert isinstance(report, EvalReportPayload)
        assert "accuracy_mean" in report.metrics.scores
        assert "accuracy_std" in report.metrics.scores
        assert report.metrics.details["k"] == 3
        per_fold = report.metrics.details["per_fold_metrics"]
        assert isinstance(per_fold, list) and len(per_fold) == 3

    async def test_default_k_is_five(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            KFoldCrossValidator(
                dataset=dataset,
                algorithm="lr",
                metrics=("f1",),
                _config=KnotConfig(id="cv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["cv"]
        assert report.metrics.details["k"] == 5
        assert len(report.metrics.details["per_fold_metrics"]) == 5
