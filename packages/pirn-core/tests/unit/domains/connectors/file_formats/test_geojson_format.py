"""Round-trip and validation tests for :class:`GeoJsonFormat`."""

from __future__ import annotations

import unittest

from pirn.connectors.file_formats.geojson_format import (
    GeoJsonFormat,
)
from pirn.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _point_features() -> list[dict[str, object]]:
    return [
        {
            "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
            "properties": {"name": "alpha", "score": 1},
            "feature_id": "f1",
        },
        {
            "geometry": {"type": "Point", "coordinates": [3.0, 4.0]},
            "properties": {"name": "beta", "score": 2},
            "feature_id": "f2",
        },
        {
            "geometry": {"type": "Point", "coordinates": [5.5, 6.5]},
            "properties": {"name": "gamma", "score": 3},
            "feature_id": "f3",
        },
    ]


class TestGeoJsonFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = GeoJsonFormat()
        assert fmt.encoding == "utf-8"

    def test_invalid_encoding_type(self) -> None:
        with self.assertRaises(TypeError):
            GeoJsonFormat(encoding=1)  # type: ignore[arg-type]

    def test_empty_encoding_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GeoJsonFormat(encoding="")


class TestGeoJsonFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert GeoJsonFormat().name == "geojson"

    def test_streaming_property(self) -> None:
        assert GeoJsonFormat().streaming is True

    def test_inherits_streaming_base(self) -> None:
        assert isinstance(GeoJsonFormat(), StreamingFileFormat)


class TestGeoJsonFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = GeoJsonFormat()
        await FormatRoundTrip.assert_round_trip(fmt, _point_features())

    async def test_round_trip_empty(self) -> None:
        fmt = GeoJsonFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single(self) -> None:
        fmt = GeoJsonFormat()
        await FormatRoundTrip.assert_round_trip(fmt, _point_features()[:1])

    async def test_read_rejects_non_feature_collection(self) -> None:
        fmt = GeoJsonFormat()
        payload = b'{"type": "Point", "coordinates": [1.0, 2.0]}'
        with self.assertRaises(ValueError):
            await FormatRoundTrip.decode(fmt, payload)
