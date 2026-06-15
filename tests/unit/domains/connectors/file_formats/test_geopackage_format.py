"""Round-trip and validation tests for :class:`GeopackageFormat`."""

from __future__ import annotations

import unittest

import pytest

try:
    import fiona  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("fiona not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.geopackage_format import (
    GeopackageFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _point_records() -> list[dict[str, object]]:
    return [
        {
            "geometry": {
                "type": "Point",
                "coordinates": (1.0, 2.0),
            },
            "properties": {"name": "alpha", "score": 1},
        },
        {
            "geometry": {
                "type": "Point",
                "coordinates": (3.0, 4.0),
            },
            "properties": {"name": "beta", "score": 2},
        },
        {
            "geometry": {
                "type": "Point",
                "coordinates": (5.5, 6.5),
            },
            "properties": {"name": "gamma", "score": 3},
        },
    ]


class TestGeopackageFormatConstruction(unittest.TestCase):
    def test_default_layer_name(self) -> None:
        fmt = GeopackageFormat()
        assert fmt.layer_name == "default"

    def test_explicit_layer_name(self) -> None:
        fmt = GeopackageFormat(layer_name="cities")
        assert fmt.layer_name == "cities"

    def test_layer_name_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            GeopackageFormat(layer_name=123)  # type: ignore[arg-type]

    def test_layer_name_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            GeopackageFormat(layer_name="")


class TestGeopackageFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert GeopackageFormat().name == "geopackage"

    def test_streaming_property(self) -> None:
        assert GeopackageFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(GeopackageFormat(), BatchFileFormat)


class TestGeopackageFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = GeopackageFormat(layer_name="points")
        records = _point_records()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for original, recovered in zip(records, decoded, strict=True):
            assert recovered["geometry"]["type"] == "Point"
            recovered_coords = recovered["geometry"]["coordinates"]
            original_coords = original["geometry"]["coordinates"]
            assert (
                recovered_coords[0] == pytest.approx(original_coords[0])
            )
            assert (
                recovered_coords[1] == pytest.approx(original_coords[1])
            )
            assert recovered["properties"]["name"] == (
                original["properties"]["name"]
            )
            assert recovered["properties"]["score"] == (
                original["properties"]["score"]
            )

    async def test_round_trip_single(self) -> None:
        fmt = GeopackageFormat()
        records = _point_records()[:1]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["geometry"]["type"] == "Point"

    async def test_encode_rejects_empty_records(self) -> None:
        fmt = GeopackageFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_encode_rejects_record_missing_geometry(self) -> None:
        fmt = GeopackageFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt, [{"properties": {"name": "x"}}]
            )

    async def test_encode_rejects_geometry_without_type(self) -> None:
        fmt = GeopackageFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt,
                [{"geometry": {"coordinates": (0.0, 0.0)}, "properties": {}}],
            )
