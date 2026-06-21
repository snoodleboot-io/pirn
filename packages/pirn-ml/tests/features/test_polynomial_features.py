"""Tests for :class:`PolynomialFeatures`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.features.polynomial_features import PolynomialFeatures
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a", "b"), row_count=10)
    test = DatasetManifest(name="d:test", feature_names=("a", "b"), row_count=5)
    return SplitManifest(train=train, test=test)


class TestPolynomialFeaturesHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_interactions_and_squares(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            PolynomialFeatures(
                split=split,
                columns=("a", "b"),
                degree=2,
                _config=KnotConfig(id="poly"),
            )
        result = await t.run(RunRequest())
        out: SplitManifest = result.outputs["poly"]
        # Original "a", "b" plus a*a, a*b, b*b derived features.
        assert "a*a" in out.train.feature_names
        assert "a*b" in out.train.feature_names
        assert "b*b" in out.train.feature_names


class TestPolynomialFeaturesConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_degree_below_two(self) -> None:
        train = DatasetManifest(name="d:train", feature_names=("a", "b"), row_count=10)
        test = DatasetManifest(name="d:test", feature_names=("a", "b"), row_count=5)
        split = SplitManifest(train=train, test=test)
        with Tapestry():
            k = PolynomialFeatures.__new__(PolynomialFeatures)
            object.__setattr__(k, "_config", KnotConfig(id="bad"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, columns=("a",), degree=1)
