"""Unit tests for :class:`Lz4Codec`. Skipped if ``lz4`` is missing."""

from __future__ import annotations
import unittest


try:
    import lz4
except ImportError as _e:
    raise unittest.SkipTest("lz4 not installed") from _e

from pirn.domains.connectors.file_formats.codecs.lz4_codec import Lz4Codec  # noqa: E402
from tests.unit.domains.connectors.file_formats.codecs._codec_round_trip import (  # noqa: E402
    CodecRoundTrip,
)


class TestLz4CodecBasics(unittest.TestCase):
    def test_default_construction(self) -> None:
        assert Lz4Codec().name == "lz4"


class TestLz4CodecRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_bytes(self) -> None:
        payload = b"hello world " * 100
        await CodecRoundTrip.round_trip(Lz4Codec(), payload)

    async def test_compresses_smaller(self) -> None:
        payload = b"hello world " * 100
        compressed = await CodecRoundTrip.compress(Lz4Codec(), payload)
        assert len(compressed) < len(payload), (
            f"lz4 should shrink repetitive input; "
            f"got {len(compressed)} >= {len(payload)}"
        )

    async def test_empty_input(self) -> None:
        await CodecRoundTrip.round_trip(Lz4Codec(), b"")
