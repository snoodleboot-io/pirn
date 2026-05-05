"""Tests for :class:`KFoldCrossValidator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.kfold_cross_validator import (
    KFoldCrossValidator,
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
                KFoldCrossValidator(
                    dataset=dataset,
                    algorithm="rf",
                    metrics=("accuracy",),
                    k=1,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with self.assertRaisesRegex(ValueError, "algorithm"):
                KFoldCrossValidator(
                    dataset=dataset,
                    algorithm="",
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with self.assertRaisesRegex(ValueError, "metrics must be non-empty"):
                KFoldCrossValidator(
                    dataset=dataset,
                    algorithm="rf",
                    metrics=(),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_non_knot_dataset(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "dataset must be a Knot"):
                KFoldCrossValidator(
                    dataset="not_a_knot",  # type: ignore[arg-type]
                    algorithm="rf",
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )


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
        assert isinstance(report, EvalReport)
        assert "accuracy_mean" in report.metrics
        assert "accuracy_std" in report.metrics
        assert report.details["k"] == 3
        per_fold = report.details["per_fold_metrics"]
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
        assert report.details["k"] == 5
        assert len(report.details["per_fold_metrics"]) == 5
