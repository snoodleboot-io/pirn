"""Tests for :class:`StratifiedKFoldValidator`."""

from __future__ import annotations

import unittest
from collections import Counter

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_ml.specializations.experiments.stratified_kfold_validator import (
    StratifiedKFoldValidator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.ml_features import MLFeatures


def _labels() -> list[int]:
    # 20 positives first, then 80 negatives: an unstratified split skews badly.
    return [1] * 20 + [0] * 80


@KnotFactory.knot
async def emit_dataset() -> DatasetPayload:
    return _dataset_fixture()


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


def _dataset_fixture() -> DatasetPayload:
    labels = _labels()
    return DatasetPayload(
        metadata=DatasetManifest(
            name="d", feature_names=("a", "b"), target_name="y", row_count=len(labels)
        ),
        data=MLFeatures(feature_matrix=np.zeros((len(labels), 2)), target_vector=np.array(labels)),
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
        assert "accuracy" in report.data.scores
        assert report.data.details["k"] == 3
        per_fold = report.data.details["per_fold_metrics"]
        assert isinstance(per_fold, list) and len(per_fold) == 3

    async def test_each_fold_test_set_preserves_the_class_proportion(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            StratifiedKFoldValidator(
                dataset=dataset,
                stratify_column="y",
                algorithm="rf",
                metrics=("accuracy",),
                k=4,
                _config=KnotConfig(id="cv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        labels = _labels()
        fold_rows = result.outputs["cv"].data.details["fold_test_row_indices"]
        assert len(fold_rows) == 4
        assert sorted(row for rows in fold_rows for row in rows) == list(range(100))
        for rows in fold_rows:
            assert Counter(labels[row] for row in rows) == Counter({0: 20, 1: 5})
