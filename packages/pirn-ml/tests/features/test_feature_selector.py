"""Tests for :class:`FeatureSelector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.features.feature_selector import FeatureSelector
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train",
        feature_names=("a", "b", "c", "d"),
        row_count=80,
    )
    test = DatasetManifest(
        name="d:test",
        feature_names=("a", "b", "c", "d"),
        row_count=20,
    )
    return SplitManifest(train=train, test=test)


class TestFeatureSelectorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_truncates_features(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FeatureSelector(
                split=split,
                k=2,
                _config=KnotConfig(id="sel"),
            )
        result = await t.run(RunRequest())
        out: SplitManifest = result.outputs["sel"]
        assert out.train.feature_names == ("a", "b")
        assert out.test.feature_names == ("a", "b")


class TestFeatureSelectorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_method(self) -> None:
        selector = FeatureSelector.__new__(FeatureSelector)
        object.__setattr__(selector, "_config", KnotConfig(id="x"))
        train = DatasetManifest(name="d:train", feature_names=("a", "b", "c", "d"), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a", "b", "c", "d"), row_count=20)
        split = SplitManifest(train=train, test=test)
        with self.assertRaisesRegex(ValueError, "method must be"):
            await selector.process(split=split, k=2, method="bogus")
