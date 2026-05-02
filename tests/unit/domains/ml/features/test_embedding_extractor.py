"""Tests for :class:`EmbeddingExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.embedding_extractor import EmbeddingExtractor
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_embedding_provider import (
    RecordingEmbeddingProvider,
)


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("a",), row_count=10
    )
    test = MLDataset(
        name="d:test", feature_names=("a",), row_count=5
    )
    return DataSplit(train=train, test=test)


class TestEmbeddingExtractorHappyPath:
    async def test_appends_embedding_feature(self) -> None:
        provider = RecordingEmbeddingProvider()
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            EmbeddingExtractor(
                split=split,
                text_column="review",
                embedding_provider=provider,
                _config=KnotConfig(id="emb"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: DataSplit = result.outputs["emb"]
        assert "review_embedding" in out.train.feature_names
        assert "review_embedding" in out.test.feature_names
        assert provider.calls and provider.calls[0][0] == ["review"]


class TestEmbeddingExtractorConstruction:
    def test_rejects_non_provider(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(TypeError, match="EmbeddingProvider"):
                EmbeddingExtractor(
                    split=split,
                    text_column="review",
                    embedding_provider="not a provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )
