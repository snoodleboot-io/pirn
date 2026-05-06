"""Tests for :class:`GroupKFoldCrossValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.group_kfold_cross_validator import (
    GroupKFoldCrossValidator,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="g", feature_names=("x",), target_name="y", row_count=80
    )


def _make_validator() -> GroupKFoldCrossValidator:
    with Tapestry():
        dataset = emit_dataset(_config=KnotConfig(id="dataset"))
        validator = GroupKFoldCrossValidator(
            dataset=dataset,
            algorithm="rf",
            metrics=("accuracy",),
            group_column="user_id",
            k=3,
            _config=KnotConfig(id="gcv"),
        )
    return validator


def _dataset_fixture() -> MLDataset:
    return MLDataset(name="g", feature_names=("x",), target_name="y", row_count=80)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_k_below_two(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                algorithm="rf",
                metrics=("accuracy",),
                group_column="user_id",
                k=1,
            )

    async def test_rejects_empty_group_column(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                algorithm="rf",
                metrics=("accuracy",),
                group_column="",
                k=3,
            )

    async def test_rejects_empty_algorithm(self) -> None:
        validator = _make_validator()
        dataset = _dataset_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                algorithm="",
                metrics=("accuracy",),
                group_column="group",
                k=3,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_records_group_column_in_details(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            GroupKFoldCrossValidator(
                dataset=dataset,
                algorithm="rf",
                metrics=("accuracy",),
                group_column="patient_id",
                k=3,
                _config=KnotConfig(id="gcv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["gcv"]
        assert isinstance(report, EvalReport)
        assert report.details["group_column"] == "patient_id"
        assert report.details["k"] == 3
        assert len(report.details["per_fold_metrics"]) == 3
