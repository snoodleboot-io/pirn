"""Tests for :class:`TFIDFExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.tfidf_extractor import (
    TFIDFExtractor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train",
        feature_names=("text", "label"),
        target_name="y",
        row_count=80,
    )
    test = MLDataset(
        name="d:test",
        feature_names=("text", "label"),
        target_name="y",
        row_count=20,
    )
    return DataSplit(train=train, test=test)


class TestConstruction:
    def test_rejects_empty_text_column(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="text_column"):
                TFIDFExtractor(
                    split=split,
                    text_column="",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_max_features_below_one(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="max_features must be >= 1"):
                TFIDFExtractor(
                    split=split,
                    text_column="text",
                    max_features=0,
                    _config=KnotConfig(id="bad"),
                )

    def test_stores_max_features(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            ext = TFIDFExtractor(
                split=split,
                text_column="text",
                max_features=50,
                _config=KnotConfig(id="te"),
            )
        assert ext.max_features == 50


class TestHappyPath:
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
        assert isinstance(out, DataSplit)
        features = out.train.feature_names
        assert "text" not in features
        assert "label" in features
        for i in range(5):
            assert f"tfidf_{i}" in features
        assert "tfidf" in out.train.name
