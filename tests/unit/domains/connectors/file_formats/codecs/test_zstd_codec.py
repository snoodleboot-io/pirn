"""Unit tests for :class:`ZstdCodec`. Skipped if ``zstandard`` is missing."""

from __future__ import annotations

import pytest

pytest.importorskip("zstandard")

from pirn.domains.connectors.file_formats.codecs.zstd_codec import ZstdCodec  # noqa: E402
from tests.unit.domains.connectors.file_formats.codecs._codec_round_trip import (  # noqa: E402
    CodecRoundTrip,
)


class TestZstdCodecConstruction:
    def test_default_construction(self) -> None:
        codec = ZstdCodec()
        assert codec.name == "zstd"

    def test_level_must_be_int(self) -> None:
        with pytest.raises(TypeError):
            ZstdCodec(level="3")  # type: ignore[arg-type]


class TestZstdCodecRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_bytes(self) -> None:
        payload = b"hello world " * 100
        await CodecRoundTrip.round_trip(ZstdCodec(), payload)

    @pytest.mark.asyncio
    async def test_compresses_smaller(self) -> None:
        payload = b"hello world " * 100
        compressed = await CodecRoundTrip.compress(ZstdCodec(), payload)
        assert len(compressed) < len(payload), (
            f"zstd should shrink repetitive input; "
            f"got {len(compressed)} >= {len(payload)}"
        )

    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        await CodecRoundTrip.round_trip(ZstdCodec(), b"")

    @pytest.mark.asyncio
    async def test_custom_level_round_trip(self) -> None:
        payload = b"abcdef" * 200
        await CodecRoundTrip.round_trip(ZstdCodec(level=1), payload)
