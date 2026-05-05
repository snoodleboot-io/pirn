"""Unit tests for :class:`ImageEmbeddingExtractor` (specializations/feature_engineering)."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.specializations.feature_engineering.image_embedding_extractor import (
    ImageEmbeddingExtractor,
)
from pirn.tapestry import Tapestry


class _StubEncoder(ImageEncoderProvider):
    async def encode(self, images, *, model=None):
        return [[0.1] for _ in images]

    async def close(self) -> None:
        pass


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_split(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ImageEmbeddingExtractor(
                    split="bad",  # type: ignore[arg-type]
                    image_column="img",
                    image_encoder=_StubEncoder(),
                    _config=KnotConfig(id="iee"),
                )

    def test_rejects_empty_image_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ImageEmbeddingExtractor(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    image_column="",
                    image_encoder=_StubEncoder(),
                    _config=KnotConfig(id="iee"),
                )

    def test_rejects_wrong_encoder_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ImageEmbeddingExtractor(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    image_column="img",
                    image_encoder="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="iee"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            ImageEmbeddingExtractor(
                split=_KnotStub(_config=KnotConfig(id="s")),
                image_column="img",
                image_encoder=_StubEncoder(),
                _config=KnotConfig(id="iee"),
            )
        self.assertIsNotNone(t._store.get("iee"))
