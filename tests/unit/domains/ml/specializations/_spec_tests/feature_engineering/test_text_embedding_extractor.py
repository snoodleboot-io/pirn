"""Tests for :class:`TextEmbeddingExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.feature_engineering.text_embedding_extractor import (
    TextEmbeddingExtractor,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest

from tests.unit.domains.ml._stubs.recording_embedding_provider import (
    RecordingEmbeddingProvider,
)


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train", feature_names=("body",), target_name="y", row_count=80
    )
    test = DatasetManifest(
        name="d:test", feature_names=("body",), target_name="y", row_count=20
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="d:train", feature_names=("body",), target_name="y", row_count=80
        )
        test = DatasetManifest(
            name="d:test", feature_names=("body",), target_name="y", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_text_column(self) -> None:
        with Tapestry():
            k = TextEmbeddingExtractor.__new__(TextEmbeddingExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="",
                embedding_provider=RecordingEmbeddingProvider(),
            )

    async def test_rejects_non_provider(self) -> None:
        with Tapestry():
            k = TextEmbeddingExtractor.__new__(TextEmbeddingExtractor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="body",
                embedding_provider="not-a-provider",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
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
        assert isinstance(out, SplitManifest)
        assert "body_embedding" in out.train.feature_names
        assert "body_embedding" in out.test.feature_names
        assert provider.calls
