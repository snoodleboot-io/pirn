"""Unit tests for :class:`Bzip2Codec`."""

from __future__ import annotations

import unittest

from pirn.connectors.file_formats.codecs.bzip2_codec import Bzip2Codec
from tests.unit.domains.connectors.file_formats.codecs._codec_round_trip import (
    CodecRoundTrip,
)


class TestBzip2CodecConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        codec = Bzip2Codec()
        assert codec.name == "bzip2"

    def test_compresslevel_must_be_int(self) -> None:
        with self.assertRaises(TypeError):
            Bzip2Codec(compresslevel="9")  # type: ignore[arg-type]

    def test_compresslevel_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            Bzip2Codec(compresslevel=0)


class TestBzip2CodecRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_bytes(self) -> None:
        payload = b"hello world " * 100
        await CodecRoundTrip.round_trip(Bzip2Codec(), payload)

    async def test_compresses_smaller(self) -> None:
        payload = b"hello world " * 100
        compressed = await CodecRoundTrip.compress(Bzip2Codec(), payload)
        assert len(compressed) < len(payload), (
            f"bzip2 should shrink repetitive input; "
            f"got {len(compressed)} >= {len(payload)}"
        )

    async def test_empty_input(self) -> None:
        await CodecRoundTrip.round_trip(Bzip2Codec(), b"")
