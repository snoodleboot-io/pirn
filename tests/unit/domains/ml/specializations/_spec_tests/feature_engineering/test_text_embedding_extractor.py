"""Tests for :class:`TextEmbeddingExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.text_embedding_extractor import (
    TextEmbeddingExtractor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_embedding_provider import (
    RecordingEmbeddingProvider,
)


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("body",), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("body",), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


class TestConstruction:
    def test_rejects_empty_text_column(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            provider = RecordingEmbeddingProvider()
            with pytest.raises(ValueError, match="text_column"):
                TextEmbeddingExtractor(
                    split=split,
                    text_column="",
                    embedding_provider=provider,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_non_provider(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(TypeError, match="EmbeddingProvider"):
                TextEmbeddingExtractor(
                    split=split,
                    text_column="body",
                    embedding_provider="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath:
    async def test_appends_text_embedding_feature(self) -> None:
        provider = RecordingEmbeddingProvider()
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            TextEmbeddingExtractor(
                split=split,
                text_column="body",
                embedding_provider=provider,
                _config=KnotConfig(id="emb"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["emb"]
        assert isinstance(out, DataSplit)
        assert "body_embedding" in out.train.feature_names
        assert "body_embedding" in out.test.feature_names
        assert provider.calls
