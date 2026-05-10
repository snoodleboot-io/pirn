"""Tests for :class:`BaselineEstablisher`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.baseline_establisher import (
    BaselineEstablisher,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train", feature_names=("a", "b"), target_name="y", row_count=80
    )
    test = DatasetManifest(
        name="d:test", feature_names=("a", "b"), target_name="y", row_count=20
    )
    return SplitManifest(train=train, test=test)


def _make_establisher() -> BaselineEstablisher:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        establisher = BaselineEstablisher(
            split=split,
            algorithm="linear",
            metrics=("accuracy",),
            _config=KnotConfig(id="baseline"),
        )
    return establisher


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(
        name="d:train", feature_names=("a", "b"), target_name="y", row_count=80
    )
    test = DatasetManifest(
        name="d:test", feature_names=("a", "b"), target_name="y", row_count=20
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_algorithm(self) -> None:
        establisher = _make_establisher()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await establisher.process(split=split, algorithm="", metrics=("accuracy",))

    async def test_rejects_empty_metrics(self) -> None:
        establisher = _make_establisher()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await establisher.process(split=split, algorithm="linear", metrics=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_baseline_eval_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            BaselineEstablisher(
                split=split,
                algorithm="linear",
                metrics=("accuracy",),
                _config=KnotConfig(id="baseline"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["baseline"]
        assert isinstance(report, EvalReportPayload)
        assert "accuracy" in report.metrics.scores
        assert report.report.dataset_name == "d:test"
