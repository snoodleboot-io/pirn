"""Round-trip and validation tests for :class:`GeotiffFormat`.

Round-trip is intentionally lossy on the metadata side: rasterio
normalises CRS / transform on write. Tests assert pixel-data and shape
survival.
"""

from __future__ import annotations

import unittest

try:
    import rasterio  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("rasterio not installed") from _e
try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.geotiff_format import (
    GeotiffFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _band_records() -> list[dict[str, object]]:
    transform = {
        "a": 1.0,
        "b": 0.0,
        "c": 0.0,
        "d": 0.0,
        "e": -1.0,
        "f": 0.0,
    }
    return [
        {
            "band_number": 1,
            "data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            "transform": transform,
            "crs": "EPSG:4326",
            "width": 4,
            "height": 3,
            "dtype": "uint8",
        },
        {
            "band_number": 2,
            "data": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120],
            "transform": transform,
            "crs": "EPSG:4326",
            "width": 4,
            "height": 3,
            "dtype": "uint8",
        },
        {
            "band_number": 3,
            "data": [
                100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210
            ],
            "transform": transform,
            "crs": "EPSG:4326",
            "width": 4,
            "height": 3,
            "dtype": "uint8",
        },
    ]


class TestGeotiffFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert GeotiffFormat().name == "geotiff"

    def test_streaming_property(self) -> None:
        assert GeotiffFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(GeotiffFormat(), BatchFileFormat)


class TestGeotiffFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_pixel_data_survives(self) -> None:
        fmt = GeotiffFormat()
        records = _band_records()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for original, recovered in zip(records, decoded, strict=True):
            assert recovered["band_number"] == original["band_number"]
            assert recovered["data"] == original["data"]
            assert recovered["width"] == original["width"]
            assert recovered["height"] == original["height"]
            assert recovered["dtype"] == original["dtype"]

    async def test_round_trip_single_band(self) -> None:
        fmt = GeotiffFormat()
        records = _band_records()[:1]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["data"] == records[0]["data"]

    async def test_encode_rejects_empty_records(self) -> None:
        fmt = GeotiffFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_encode_rejects_record_missing_data(self) -> None:
        fmt = GeotiffFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt,
                [
                    {
                        "band_number": 1,
                        "width": 1,
                        "height": 1,
                        "dtype": "uint8",
                    }
                ],
            )

    async def test_encode_rejects_invalid_dimensions(self) -> None:
        fmt = GeotiffFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt,
                [
                    {
                        "band_number": 1,
                        "data": [],
                        "width": 0,
                        "height": 0,
                        "dtype": "uint8",
                    }
                ],
            )
