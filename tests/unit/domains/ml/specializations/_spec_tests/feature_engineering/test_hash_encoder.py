"""Tests for :class:`HashEncoder`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.hash_encoder import (
    HashEncoder,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train",
        feature_names=("category", "value"),
        target_name="y",
        row_count=80,
    )
    test = DatasetManifest(
        name="d:test",
        feature_names=("category", "value"),
        target_name="y",
        row_count=20,
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="d:train", feature_names=("category", "value"), target_name="y", row_count=80
        )
        test = DatasetManifest(
            name="d:test", feature_names=("category", "value"), target_name="y", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_categorical_column(self) -> None:
        with Tapestry():
            k = HashEncoder.__new__(HashEncoder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), categorical_column="")

    async def test_rejects_n_components_below_one(self) -> None:
        with Tapestry():
            k = HashEncoder.__new__(HashEncoder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(), categorical_column="category", n_components=0
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
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
        assert isinstance(out, SplitManifest)
        train_features = out.train.feature_names
        assert "category" not in train_features
        for i in range(4):
            assert f"category_hash_{i}" in train_features
        assert "value" in train_features
        assert "hash_encoded" in out.train.name
