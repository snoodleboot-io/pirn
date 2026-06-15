"""Tests for :class:`TFIDFExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.feature_engineering.tfidf_extractor import (
    TFIDFExtractor,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train",
        feature_names=("text", "label"),
        target_name="y",
        row_count=80,
    )
    test = DatasetManifest(
        name="d:test",
        feature_names=("text", "label"),
        target_name="y",
        row_count=20,
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="d:train", feature_names=("text", "label"), target_name="y", row_count=80
        )
        test = DatasetManifest(
            name="d:test", feature_names=("text", "label"), target_name="y", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_text_column(self) -> None:
        with Tapestry():
            k = TFIDFExtractor.__new__(TFIDFExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), text_column="")

    async def test_rejects_max_features_below_one(self) -> None:
        with Tapestry():
            k = TFIDFExtractor.__new__(TFIDFExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), text_column="text", max_features=0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_tfidf_features_removes_text_column(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            TFIDFExtractor(
                split=split,
                text_column="text",
                max_features=5,
                _config=KnotConfig(id="te"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["te"]
        assert isinstance(out, SplitManifest)
        features = out.train.feature_names
        assert "text" not in features
        assert "label" in features
        for i in range(5):
            assert f"tfidf_{i}" in features
        assert "tfidf" in out.train.name
