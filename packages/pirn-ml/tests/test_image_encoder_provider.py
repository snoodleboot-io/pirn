"""Unit tests for :class:`ImageEncoderProvider`."""

from __future__ import annotations

import unittest

from pirn_ml.image_encoder_provider import ImageEncoderProvider


class _StubEncoder(ImageEncoderProvider):
    async def encode(self, images, *, model=None):
        return [[0.5, 0.5] for _ in images]

    async def close(self) -> None:
        pass


class TestImageEncoderProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_base_encode_raises_not_implemented(self) -> None:
        encoder = ImageEncoderProvider()
        with self.assertRaises(NotImplementedError):
            await encoder.encode([b"\x89PNG"])

    async def test_base_close_raises_not_implemented(self) -> None:
        encoder = ImageEncoderProvider()
        with self.assertRaises(NotImplementedError):
            await encoder.close()

    def test_clear_credentials_nullifies_config(self) -> None:
        encoder = ImageEncoderProvider()
        encoder._config = {"api_key": "key"}  # type: ignore[assignment]
        encoder._clear_credentials()
        self.assertIsNone(encoder._config)

    async def test_subclass_encode_returns_vectors(self) -> None:
        encoder = _StubEncoder()
        result = await encoder.encode([b"\x89PNG", b"\xff\xd8\xff"])
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 2)

    def test_subclass_is_instance_of_encoder(self) -> None:
        self.assertIsInstance(_StubEncoder(), ImageEncoderProvider)
