"""Tests for :class:`ImageEncoderProvider`."""

from __future__ import annotations

import unittest

from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider


class TestImageEncoderProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_encode_raises_not_implemented(self) -> None:
        provider = ImageEncoderProvider()
        with self.assertRaisesRegex(NotImplementedError, "encode"):
            await provider.encode([b"\x00\x01"])

    async def test_close_raises_not_implemented(self) -> None:
        provider = ImageEncoderProvider()
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await provider.close()
