"""Round-trip and validation tests for :class:`WebpFormat`.

Lossless mode preserves pixel data byte-for-byte. Lossy mode (the
default) only preserves ``width``, ``height`` and ``mode``.
"""

from __future__ import annotations
import unittest


try:
    import PIL
except ImportError as _e:
    raise unittest.SkipTest("PIL not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.webp_format import (
    WebpFormat,
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


class TestWebpFormatConstruction(unittest.TestCase):
    def test_defaults(self) -> None:
        fmt = WebpFormat()
        assert fmt.quality == 85
        assert fmt.lossless is False

    def test_custom_arguments(self) -> None:
        fmt = WebpFormat(quality=70, lossless=True)
        assert fmt.quality == 70
        assert fmt.lossless is True

    def test_quality_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            WebpFormat(quality=0)
        with self.assertRaises(ValueError):
            WebpFormat(quality=101)

    def test_quality_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            WebpFormat(quality="high")  # type: ignore[arg-type]

    def test_lossless_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            WebpFormat(lossless="yes")  # type: ignore[arg-type]


class TestWebpFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert WebpFormat().name == "webp"

    def test_streaming_property(self) -> None:
        assert WebpFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(WebpFormat(), BatchFileFormat)


class TestWebpFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic_lossy(self) -> None:
        record = _tiny_rgb_record()
        fmt = WebpFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        recovered = decoded[0]
        assert recovered["width"] == record["width"]
        assert recovered["height"] == record["height"]
        assert recovered["mode"] == record["mode"]
        assert isinstance(recovered["data"], bytes)
        assert len(recovered["data"]) == len(record["data"])

    async def test_round_trip_lossless_preserves_pixels(self) -> None:
        record = _tiny_rgb_record()
        fmt = WebpFormat(lossless=True)
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        recovered = decoded[0]
        assert recovered["data"] == record["data"]

    async def test_empty_records_rejected(self) -> None:
        fmt = WebpFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])
