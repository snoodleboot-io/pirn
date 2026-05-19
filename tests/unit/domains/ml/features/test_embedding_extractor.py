"""Tests for :class:`EmbeddingExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.embedding_extractor import EmbeddingExtractor
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_embedding_provider import (
    RecordingEmbeddingProvider,
)


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train", feature_names=("a",), row_count=10
    )
    test = DatasetManifest(
        name="d:test", feature_names=("a",), row_count=5
    )
    return SplitManifest(train=train, test=test)


class TestEmbeddingExtractorHappyPath(unittest.IsolatedAsyncioTestCase):
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
        out: SplitManifest = result.outputs["emb"]
        assert "review_embedding" in out.train.feature_names
        assert "review_embedding" in out.test.feature_names
        assert provider.calls and provider.calls[0][0] == ["review"]


class TestEmbeddingExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_provider(self) -> None:
        extractor = EmbeddingExtractor.__new__(EmbeddingExtractor)
        object.__setattr__(extractor, "_config", KnotConfig(id="x"))
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=10)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=5)
        split = SplitManifest(train=train, test=test)
        with self.assertRaisesRegex(TypeError, "EmbeddingProvider"):
            await extractor.process(
                split=split,
                text_column="review",
                embedding_provider="not a provider",  # type: ignore[arg-type]
            )
