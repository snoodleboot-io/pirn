"""Round-trip and validation tests for :class:`KmlFormat`."""

from __future__ import annotations

import unittest

try:
    import simplekml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("simplekml not installed") from _e
try:
    import lxml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lxml not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.kml_format import KmlFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _point_records() -> list[dict[str, object]]:
    return [
        {
            "name": "alpha",
            "description": "first placemark",
            "geometry_type": "Point",
            "coordinates": [(1.0, 2.0)],
            "extended_data": {"score": "10"},
        },
        {
            "name": "beta",
            "description": "second placemark",
            "geometry_type": "Point",
            "coordinates": [(3.0, 4.0)],
            "extended_data": {"score": "20"},
        },
        {
            "name": "gamma",
            "description": "third placemark",
            "geometry_type": "Point",
            "coordinates": [(5.5, 6.5)],
            "extended_data": {"score": "30"},
        },
    ]


def _coordinates_xy(coords: list[tuple[float, ...]]) -> list[tuple[float, float]]:
    return [(coord[0], coord[1]) for coord in coords]


class TestKmlFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert KmlFormat().name == "kml"

    def test_streaming_property(self) -> None:
        assert KmlFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(KmlFormat(), BatchFileFormat)


class TestKmlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = KmlFormat()
        records = _point_records()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for original, recovered in zip(records, decoded, strict=True):
            assert recovered["name"] == original["name"]
            assert recovered["description"] == original["description"]
            assert recovered["geometry_type"] == original["geometry_type"]
            assert _coordinates_xy(recovered["coordinates"]) == list(
                original["coordinates"]
            )
            assert recovered["extended_data"] == original["extended_data"]

    async def test_round_trip_empty(self) -> None:
        fmt = KmlFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []

    async def test_round_trip_single(self) -> None:
        fmt = KmlFormat()
        records = _point_records()[:1]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["name"] == records[0]["name"]
        assert _coordinates_xy(decoded[0]["coordinates"]) == list(
            records[0]["coordinates"]
        )

    async def test_unsupported_geometry_type_raises(self) -> None:
        fmt = KmlFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt,
                [
                    {
                        "name": "x",
                        "description": "",
                        "geometry_type": "Hexagon",
                        "coordinates": [(0.0, 0.0)],
                        "extended_data": {},
                    }
                ],
            )

    async def test_record_missing_geometry_type_raises(self) -> None:
        fmt = KmlFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt,
                [
                    {
                        "name": "x",
                        "description": "",
                        "coordinates": [(0.0, 0.0)],
                    }
                ],
            )
