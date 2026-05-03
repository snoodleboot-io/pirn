"""Tests for :class:`HashEncoder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.hash_encoder import (
    HashEncoder,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train",
        feature_names=("category", "value"),
        target_name="y",
        row_count=80,
    )
    test = MLDataset(
        name="d:test",
        feature_names=("category", "value"),
        target_name="y",
        row_count=20,
    )
    return DataSplit(train=train, test=test)


class TestConstruction:
    def test_rejects_empty_categorical_column(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="categorical_column"):
                HashEncoder(
                    split=split,
                    categorical_column="",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_n_components_below_one(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="n_components must be >= 1"):
                HashEncoder(
                    split=split,
                    categorical_column="category",
                    n_components=0,
                    _config=KnotConfig(id="bad"),
                )

    def test_stores_n_components(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            enc = HashEncoder(
                split=split,
                categorical_column="category",
                n_components=16,
                _config=KnotConfig(id="he"),
            )
        assert enc.n_components == 16


class TestHappyPath:
    async def test_appends_hash_features_and_removes_original(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            HashEncoder(
                split=split,
                categorical_column="category",
                n_components=4,
                _config=KnotConfig(id="he"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["he"]
        assert isinstance(out, DataSplit)
        train_features = out.train.feature_names
        assert "category" not in train_features
        for i in range(4):
            assert f"category_hash_{i}" in train_features
        assert "value" in train_features
        assert "hash_encoded" in out.train.name
