"""Tests for :class:`NGramExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.ngram_extractor import (
    NGramExtractor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train",
        feature_names=("review",),
        target_name="sentiment",
        row_count=80,
    )
    test = MLDataset(
        name="d:test",
        feature_names=("review",),
        target_name="sentiment",
        row_count=20,
    )
    return DataSplit(train=train, test=test)


class TestConstruction:
    def test_rejects_empty_text_column(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="text_column"):
                NGramExtractor(
                    split=split,
                    text_column="",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_invalid_analyzer(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="analyzer"):
                NGramExtractor(
                    split=split,
                    text_column="review",
                    analyzer="sentence",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_n_below_one(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="n must be >= 1"):
                NGramExtractor(
                    split=split,
                    text_column="review",
                    n=0,
                    _config=KnotConfig(id="bad"),
                )

    def test_stores_n_and_analyzer(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            ext = NGramExtractor(
                split=split,
                text_column="review",
                n=3,
                analyzer="char",
                _config=KnotConfig(id="ng"),
            )
        assert ext.n == 3
        assert ext.analyzer == "char"


class TestHappyPath:
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
        assert isinstance(out, DataSplit)
        features = out.train.feature_names
        assert "review" not in features
        for i in range(4):
            assert f"ngram_word_2_{i}" in features
        assert "ngram_word_2" in out.train.name
