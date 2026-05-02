"""Tests for :class:`EmbeddingProvider`."""

from __future__ import annotations

import pytest

from pirn.domains.ml.embedding_provider import EmbeddingProvider


class TestEmbeddingProviderInterface:
    async def test_embed_raises_not_implemented(self) -> None:
        provider = EmbeddingProvider()
        with pytest.raises(NotImplementedError, match="embed"):
            await provider.embed(["hello"])

    async def test_close_raises_not_implemented(self) -> None:
        provider = EmbeddingProvider()
        with pytest.raises(NotImplementedError, match="close"):
            await provider.close()
