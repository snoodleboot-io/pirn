"""Unit tests for pirn-ml's :class:`MLEmbeddingProvider` (PIR-735: domain-owned)."""

from __future__ import annotations

import unittest

from pirn_ml.ml_embedding_provider import MLEmbeddingProvider


class _StubProvider(MLEmbeddingProvider):
    async def embed(self, texts, *, model=None):
        return [[0.1, 0.2] for _ in texts]

    async def close(self) -> None:
        pass


class TestEmbeddingProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_base_embed_raises_not_implemented(self) -> None:
        provider = MLEmbeddingProvider()
        with self.assertRaisesRegex(NotImplementedError, "embed"):
            await provider.embed(["text"])

    async def test_base_close_raises_not_implemented(self) -> None:
        provider = MLEmbeddingProvider()
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await provider.close()

    def test_clear_credentials_nullifies_config(self) -> None:
        provider = MLEmbeddingProvider()
        provider._config = {"api_key": "secret"}  # type: ignore[assignment]
        provider._clear_credentials()
        self.assertIsNone(provider._config)

    async def test_subclass_embed_returns_vectors(self) -> None:
        provider = _StubProvider()
        result = await provider.embed(["hello", "world"])
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 2)

    def test_subclass_is_instance_of_provider(self) -> None:
        self.assertIsInstance(_StubProvider(), MLEmbeddingProvider)
