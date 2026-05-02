"""Tests for :class:`PolynomialFeatures`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.polynomial_features import PolynomialFeatures
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a", "b"), row_count=10)
    test = MLDataset(name="d:test", feature_names=("a", "b"), row_count=5)
    return DataSplit(train=train, test=test)


class TestPolynomialFeaturesHappyPath:
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
        out: DataSplit = result.outputs["poly"]
        # Original "a", "b" plus a*a, a*b, b*b derived features.
        assert "a*a" in out.train.feature_names
        assert "a*b" in out.train.feature_names
        assert "b*b" in out.train.feature_names


class TestPolynomialFeaturesConstruction:
    def test_rejects_degree_below_two(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="degree must be >= 2"):
                PolynomialFeatures(
                    split=split,
                    columns=("a",),
                    degree=1,
                    _config=KnotConfig(id="bad"),
                )
