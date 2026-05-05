"""Tests for :class:`StratifiedKFoldValidator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.stratified_kfold_validator import (
    StratifiedKFoldValidator,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="d", feature_names=("a", "b"), target_name="y", row_count=100
    )


class TestConstruction(unittest.TestCase):
    def test_rejects_k_below_two(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with self.assertRaisesRegex(ValueError, "k must be >= 2"):
                StratifiedKFoldValidator(
                    dataset=dataset,
                    stratify_column="y",
                    algorithm="rf",
                    metrics=("accuracy",),
                    k=1,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_stratify_column(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with self.assertRaisesRegex(ValueError, "stratify_column"):
                StratifiedKFoldValidator(
                    dataset=dataset,
                    stratify_column="",
                    algorithm="rf",
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
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
        assert isinstance(report, EvalReport)
        assert "accuracy" in report.metrics
        assert report.details["k"] == 3
        per_fold = report.details["per_fold_metrics"]
        assert isinstance(per_fold, list) and len(per_fold) == 3
