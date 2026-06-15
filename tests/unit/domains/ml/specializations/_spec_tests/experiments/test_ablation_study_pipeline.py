"""Tests for :class:`AblationStudyPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.ablation_study_pipeline import (
    AblationStudyPipeline,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train",
        feature_names=("a", "b", "c"),
        target_name="y",
        row_count=80,
    )
    test = DatasetManifest(
        name="d:test",
        feature_names=("a", "b", "c"),
        target_name="y",
        row_count=20,
    )
    return SplitManifest(train=train, test=test)


def _make_pipeline() -> AblationStudyPipeline:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        pipeline = AblationStudyPipeline(
            split=split,
            algorithm="rf",
            feature_groups={"g1": ("a",)},
            metrics=("accuracy",),
            _config=KnotConfig(id="ablation"),
        )
    return pipeline


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(
        name="d:train", feature_names=("a", "b", "c"), target_name="y", row_count=80
    )
    test = DatasetManifest(
        name="d:test", feature_names=("a", "b", "c"), target_name="y", row_count=20
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_feature_groups(self) -> None:
        pipeline = _make_pipeline()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await pipeline.process(
                split=split,
                algorithm="rf",
                feature_groups={},
                metrics=("accuracy",),
            )

    async def test_rejects_full_arm_name(self) -> None:
        pipeline = _make_pipeline()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await pipeline.process(
                split=split,
                algorithm="rf",
                feature_groups={"full": ("a",)},
                metrics=("accuracy",),
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
        for _arm, report in reports.items():
            assert isinstance(report, EvalReportPayload)
            assert "accuracy" in report.metrics.scores
