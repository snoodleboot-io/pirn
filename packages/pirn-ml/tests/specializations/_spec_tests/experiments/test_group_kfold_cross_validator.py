"""Tests for :class:`GroupKFoldCrossValidator`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_ml.specializations.experiments.group_kfold_cross_validator import (
    GroupKFoldCrossValidator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.ml_features import MLFeatures


def _patients() -> list[int]:
    # 16 patients, 5 visits each, interleaved so position-based folds split patients.
    return [row % 16 for row in range(80)]


@KnotFactory.knot
async def emit_dataset() -> DatasetPayload:
    return _dataset_fixture()


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


def _dataset_fixture() -> DatasetPayload:
    patients = _patients()
    return DatasetPayload(
        metadata=DatasetManifest(
            name="g", feature_names=("x", "patient_id"), target_name="y", row_count=len(patients)
        ),
        data=MLFeatures(
            feature_matrix=np.column_stack(
                [np.zeros(len(patients)), np.array(patients, dtype=float)]
            ),
            target_vector=np.zeros(len(patients)),
        ),
    )


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
        assert isinstance(report, EvalReportPayload)
        assert report.data.details["group_column"] == "patient_id"
        assert report.data.details["k"] == 3
        assert len(report.data.details["per_fold_metrics"]) == 3

    async def test_no_patient_is_in_both_train_and_test_of_a_fold(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            GroupKFoldCrossValidator(
                dataset=dataset,
                algorithm="rf",
                metrics=("accuracy",),
                group_column="patient_id",
                k=4,
                _config=KnotConfig(id="gcv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        patients = _patients()
        fold_rows = result.outputs["gcv"].data.details["fold_test_row_indices"]
        assert len(fold_rows) == 4
        assert sorted(row for rows in fold_rows for row in rows) == list(range(80))
        for rows in fold_rows:
            test_patients = {patients[row] for row in rows}
            train_patients = {patients[row] for row in set(range(80)) - set(rows)}
            assert test_patients
            assert test_patients.isdisjoint(train_patients)
