"""Round-trip and validation tests for :class:`TiffFormat`.

TIFF supports multiple pages. With a lossless compression (the default
``"lzw"``) round-trip preserves pixel data byte-for-byte.
"""

from __future__ import annotations

import unittest

try:
    import tifffile  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("tifffile not installed") from _e
try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.tiff_format import (
    TiffFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _tiny_rgb_record(page_number: int = 0) -> dict[str, object]:
    pixels: list[int] = []
    for y in range(4):
        for x in range(4):
            pixels.extend([x * 32, y * 32, (x + y) * 16])
    return {
        "page_number": page_number,
        "width": 4,
        "height": 4,
        "mode": "RGB",
        "data": bytes(pixels),
        "dtype": "uint8",
    }


class TestTiffFormatConstruction(unittest.TestCase):
    def test_default_compression(self) -> None:
        fmt = TiffFormat()
        assert fmt.compression == "lzw"

    def test_custom_compression(self) -> None:
        assert TiffFormat(compression="zlib").compression == "zlib"

    def test_empty_compression_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TiffFormat(compression="")

    def test_non_string_compression_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TiffFormat(compression=0)  # type: ignore[arg-type]


class TestTiffFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert TiffFormat().name == "tiff"

    def test_streaming_property(self) -> None:
        assert TiffFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(TiffFormat(), BatchFileFormat)


class TestTiffFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic_single_page(self) -> None:
        record = _tiny_rgb_record()
        fmt = TiffFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        recovered = decoded[0]
        assert recovered["page_number"] == 0
        assert recovered["width"] == record["width"]
        assert recovered["height"] == record["height"]
        assert recovered["mode"] == record["mode"]
        assert recovered["dtype"] == record["dtype"]
        # LZW is lossless.
        assert recovered["data"] == record["data"]

    async def test_round_trip_multi_page(self) -> None:
        records = [
            _tiny_rgb_record(page_number=0),
            _tiny_rgb_record(page_number=1),
            _tiny_rgb_record(page_number=2),
        ]
        fmt = TiffFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 3
        for index, recovered in enumerate(decoded):
            assert recovered["page_number"] == index
            assert recovered["width"] == 4
            assert recovered["height"] == 4
            assert recovered["mode"] == "RGB"
            assert recovered["data"] == records[index]["data"]

    async def test_empty_records_rejected(self) -> None:
        fmt = TiffFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_missing_field_rejected(self) -> None:
        fmt = TiffFormat()
        bad = {
            "page_number": 0,
            "width": 4,
            "height": 4,
            "mode": "RGB",
            "data": b"\x00" * 48,
            # missing dtype
        }
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [bad])
