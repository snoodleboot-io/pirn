"""Tests for :class:`FeatureSelector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.feature_selector import FeatureSelector
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train",
        feature_names=("a", "b", "c", "d"),
        row_count=80,
    )
    test = MLDataset(
        name="d:test",
        feature_names=("a", "b", "c", "d"),
        row_count=20,
    )
    return DataSplit(train=train, test=test)


class TestFeatureSelectorHappyPath:
    async def test_truncates_features(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FeatureSelector(
                split=split,
                k=2,
                _config=KnotConfig(id="sel"),
            )
        result = await t.run(RunRequest())
        out: DataSplit = result.outputs["sel"]
        assert out.train.feature_names == ("a", "b")
        assert out.test.feature_names == ("a", "b")


class TestFeatureSelectorConstruction:
    def test_rejects_unknown_method(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="method must be"):
                FeatureSelector(
                    split=split,
                    k=2,
                    method="bogus",
                    _config=KnotConfig(id="bad"),
                )
