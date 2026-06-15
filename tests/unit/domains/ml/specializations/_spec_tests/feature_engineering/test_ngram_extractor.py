"""Tests for :class:`NGramExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.feature_engineering.ngram_extractor import (
    NGramExtractor,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train",
        feature_names=("review",),
        target_name="sentiment",
        row_count=80,
    )
    test = DatasetManifest(
        name="d:test",
        feature_names=("review",),
        target_name="sentiment",
        row_count=20,
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="d:train", feature_names=("review",), target_name="sentiment", row_count=80
        )
        test = DatasetManifest(
            name="d:test", feature_names=("review",), target_name="sentiment", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_text_column(self) -> None:
        with Tapestry():
            k = NGramExtractor.__new__(NGramExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), text_column="")

    async def test_rejects_invalid_analyzer(self) -> None:
        with Tapestry():
            k = NGramExtractor.__new__(NGramExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(), text_column="review", analyzer="sentence"
            )

    async def test_rejects_n_below_one(self) -> None:
        with Tapestry():
            k = NGramExtractor.__new__(NGramExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), text_column="review", n=0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_ngram_features_removes_text_column(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            NGramExtractor(
                split=split,
                text_column="review",
                n=2,
                analyzer="word",
                max_features=4,
                _config=KnotConfig(id="ng"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ng"]
        assert isinstance(out, SplitManifest)
        features = out.train.feature_names
        assert "review" not in features
        for i in range(4):
            assert f"ngram_word_2_{i}" in features
        assert "ngram_word_2" in out.train.name
