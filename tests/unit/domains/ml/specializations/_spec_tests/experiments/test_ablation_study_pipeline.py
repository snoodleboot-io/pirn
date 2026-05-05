"""Tests for :class:`AblationStudyPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.ablation_study_pipeline import (
    AblationStudyPipeline,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train",
        feature_names=("a", "b", "c"),
        target_name="y",
        row_count=80,
    )
    test = MLDataset(
        name="d:test",
        feature_names=("a", "b", "c"),
        target_name="y",
        row_count=20,
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_split(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "split must be a Knot"):
                AblationStudyPipeline(
                    split="not-a-knot",  # type: ignore[arg-type]
                    algorithm="rf",
                    feature_groups={"g1": ("a",)},
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_feature_groups(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "feature_groups"):
                AblationStudyPipeline(
                    split=split,
                    algorithm="rf",
                    feature_groups={},
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_full_arm_name(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "reserved"):
                AblationStudyPipeline(
                    split=split,
                    algorithm="rf",
                    feature_groups={"full": ("a",)},
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_one_report_per_arm(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            AblationStudyPipeline(
                split=split,
                algorithm="rf",
                feature_groups={"g1": ("a",), "g2": ("b", "c")},
                metrics=("accuracy",),
                _config=KnotConfig(id="ablation"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        reports = result.outputs["ablation"]
        assert isinstance(reports, dict)
        assert set(reports.keys()) == {"full", "g1", "g2"}
        for arm, report in reports.items():
            assert isinstance(report, EvalReport)
            assert "accuracy" in report.metrics
