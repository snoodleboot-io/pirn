"""Tests for :class:`StratifiedKFoldValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.stratified_kfold_validator import (
    StratifiedKFoldValidator,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> DatasetManifest:
    return DatasetManifest(
        name="d", feature_names=("a", "b"), target_name="y", row_count=100
    )


def _make_validator() -> StratifiedKFoldValidator:
    with Tapestry():
        dataset = emit_dataset(_config=KnotConfig(id="dataset"))
        validator = StratifiedKFoldValidator(
            dataset=dataset,
            stratify_column="y",
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
            await validator.process(
                dataset=dataset,
                stratify_column="y",
                algorithm="rf",
                metrics=("accuracy",),
                k=1,
            )

    async def test_rejects_empty_stratify_column(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                stratify_column="",
                algorithm="rf",
                metrics=("accuracy",),
                k=3,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_aggregates_metrics_across_folds(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            StratifiedKFoldValidator(
                dataset=dataset,
                stratify_column="y",
                algorithm="rf",
                metrics=("accuracy",),
                k=3,
                _config=KnotConfig(id="cv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["cv"]
        assert isinstance(report, EvalReportPayload)
        assert "accuracy" in report.metrics.scores
        assert report.metrics.details["k"] == 3
        per_fold = report.metrics.details["per_fold_metrics"]
        assert isinstance(per_fold, list) and len(per_fold) == 3
