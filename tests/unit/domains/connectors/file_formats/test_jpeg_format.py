"""Round-trip and validation tests for :class:`JpegFormat`.

JPEG is a lossy codec — round-trip pixel equality is **not** asserted.
Tests verify that ``width``, ``height`` and ``mode`` survive plus that
the decoded payload has the expected data length.
"""

from __future__ import annotations

import unittest

try:
    import PIL  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("PIL not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.jpeg_format import (
    JpegFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _tiny_rgb_record() -> dict[str, object]:
    pixels: list[int] = []
    for y in range(4):
        for x in range(4):
            pixels.extend([x * 32, y * 32, (x + y) * 16])
    return {
        "width": 4,
        "height": 4,
        "mode": "RGB",
        "data": bytes(pixels),
    }


class TestJpegFormatConstruction(unittest.TestCase):
    def test_default_quality(self) -> None:
        fmt = JpegFormat()
        assert fmt.quality == 95

    def test_custom_quality(self) -> None:
        assert JpegFormat(quality=80).quality == 80

    def test_quality_too_low(self) -> None:
        with self.assertRaises(ValueError):
            JpegFormat(quality=0)

    def test_quality_too_high(self) -> None:
        with self.assertRaises(ValueError):
            JpegFormat(quality=101)

    def test_quality_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            JpegFormat(quality="high")  # type: ignore[arg-type]


class TestJpegFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert JpegFormat().name == "jpeg"

    def test_streaming_property(self) -> None:
        assert JpegFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(JpegFormat(), BatchFileFormat)


class TestJpegFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        record = _tiny_rgb_record()
        fmt = JpegFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        recovered = decoded[0]
        # JPEG is lossy — only structural metadata survives verbatim.
        assert recovered["width"] == record["width"]
        assert recovered["height"] == record["height"]
        assert recovered["mode"] == record["mode"]
        assert isinstance(recovered["data"], bytes)
        assert len(recovered["data"]) == len(record["data"])

    async def test_round_trip_single_record(self) -> None:
        record = _tiny_rgb_record()
        fmt = JpegFormat(quality=85)
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1

    async def test_empty_records_rejected(self) -> None:
        fmt = JpegFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])
