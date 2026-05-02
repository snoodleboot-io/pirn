"""Tests for :class:`ImageEncoderProvider`."""

from __future__ import annotations

import pytest

from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider


class TestImageEncoderProviderInterface:
    async def test_encode_raises_not_implemented(self) -> None:
        provider = ImageEncoderProvider()
        with pytest.raises(NotImplementedError, match="encode"):
            await provider.encode([b"\x00\x01"])

    async def test_close_raises_not_implemented(self) -> None:
        provider = ImageEncoderProvider()
        with pytest.raises(NotImplementedError, match="close"):
            await provider.close()
