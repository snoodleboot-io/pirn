"""Tests for :class:`GroupKFoldCrossValidator`."""

from __future__ import annotations

import pytest

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


class TestConstruction:
    def test_rejects_k_below_two(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with pytest.raises(ValueError, match="k must be >= 2"):
                GroupKFoldCrossValidator(
                    dataset=dataset,
                    algorithm="rf",
                    metrics=("accuracy",),
                    group_column="user_id",
                    k=1,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_group_column(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with pytest.raises(ValueError, match="group_column"):
                GroupKFoldCrossValidator(
                    dataset=dataset,
                    algorithm="rf",
                    metrics=("accuracy",),
                    group_column="",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with pytest.raises(ValueError, match="algorithm"):
                GroupKFoldCrossValidator(
                    dataset=dataset,
                    algorithm="",
                    metrics=("accuracy",),
                    group_column="group",
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath:
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
