"""Unit tests for :class:`GzipCodec`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats.codecs.gzip_codec import GzipCodec
from tests.unit.domains.connectors.file_formats.codecs._codec_round_trip import (
    CodecRoundTrip,
)


class TestGzipCodecConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        codec = GzipCodec()
        assert codec.name == "gzip"

    def test_compresslevel_must_be_int(self) -> None:
        with self.assertRaises(TypeError):
            GzipCodec(compresslevel="9")  # type: ignore[arg-type]

    def test_compresslevel_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            GzipCodec(compresslevel=10)


class TestGzipCodecRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_bytes(self) -> None:
        payload = b"hello world " * 100
        await CodecRoundTrip.round_trip(GzipCodec(), payload)

    async def test_compresses_smaller(self) -> None:
        payload = b"hello world " * 100
        compressed = await CodecRoundTrip.compress(GzipCodec(), payload)
        assert len(compressed) < len(payload), (
            f"gzip should shrink repetitive input; "
            f"got {len(compressed)} >= {len(payload)}"
        )

    async def test_empty_input(self) -> None:
        await CodecRoundTrip.round_trip(GzipCodec(), b"")

    async def test_compresslevel_round_trip(self) -> None:
        payload = b"abc" * 50
        await CodecRoundTrip.round_trip(GzipCodec(compresslevel=1), payload)
