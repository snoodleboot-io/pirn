"""Unit tests for :class:`SnappyCodec`. Skipped if ``snappy`` is missing."""

from __future__ import annotations
import unittest


try:
    import snappy
except ImportError as _e:
    raise unittest.SkipTest("snappy not installed") from _e

from pirn.domains.connectors.file_formats.codecs.snappy_codec import SnappyCodec  # noqa: E402
from tests.unit.domains.connectors.file_formats.codecs._codec_round_trip import (  # noqa: E402
    CodecRoundTrip,
)


class TestSnappyCodecBasics(unittest.TestCase):
    def test_default_construction(self) -> None:
        assert SnappyCodec().name == "snappy"


class TestSnappyCodecRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_bytes(self) -> None:
        payload = b"hello world " * 100
        await CodecRoundTrip.round_trip(SnappyCodec(), payload)

    async def test_compresses_smaller(self) -> None:
        # Snappy is a fast, low-ratio codec — heavier repetition needed
        # to clear the framing overhead on small payloads.
        payload = b"hello world " * 1000
        compressed = await CodecRoundTrip.compress(SnappyCodec(), payload)
        assert len(compressed) < len(payload), (
            f"snappy should shrink heavily repetitive input; "
            f"got {len(compressed)} >= {len(payload)}"
        )

    async def test_empty_input(self) -> None:
        await CodecRoundTrip.round_trip(SnappyCodec(), b"")
