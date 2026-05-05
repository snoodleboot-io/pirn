"""Tests for :class:`EmbeddingProvider`."""

from __future__ import annotations
import unittest


from pirn.domains.ml.embedding_provider import EmbeddingProvider


class TestEmbeddingProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_embed_raises_not_implemented(self) -> None:
        provider = EmbeddingProvider()
        with self.assertRaisesRegex(NotImplementedError, "embed"):
            await provider.embed(["hello"])

    async def test_close_raises_not_implemented(self) -> None:
        provider = EmbeddingProvider()
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await provider.close()
