"""Round-trip and validation tests for :class:`ShapefileFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("shapefile")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.shapefile_format import (
    ShapefileFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _point_records() -> list[dict[str, object]]:
    return [
        {
            "geometry": [(1.0, 2.0)],
            "shape_type": "POINT",
            "name": "alpha",
            "label": "first",
        },
        {
            "geometry": [(3.0, 4.0)],
            "shape_type": "POINT",
            "name": "beta",
            "label": "second",
        },
        {
            "geometry": [(5.5, 6.5)],
            "shape_type": "POINT",
            "name": "gamma",
            "label": "third",
        },
    ]


class TestShapefileFormatBasics:
    def test_name(self) -> None:
        assert ShapefileFormat().name == "shapefile"

    def test_streaming_property(self) -> None:
        assert ShapefileFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(ShapefileFormat(), BatchFileFormat)


class TestShapefileFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        fmt = ShapefileFormat()
        records = _point_records()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for original, recovered in zip(records, decoded, strict=True):
            assert recovered["geometry"] == original["geometry"]
            assert recovered["shape_type"] == "POINT"
            assert recovered["name"] == original["name"]
            assert recovered["label"] == original["label"]

    @pytest.mark.asyncio
    async def test_round_trip_single(self) -> None:
        fmt = ShapefileFormat()
        records = _point_records()[:1]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["geometry"] == records[0]["geometry"]
        assert decoded[0]["name"] == records[0]["name"]

    @pytest.mark.asyncio
    async def test_decode_rejects_non_zip_payload(self) -> None:
        fmt = ShapefileFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.decode(fmt, b"not a zip archive")

    @pytest.mark.asyncio
    async def test_encode_rejects_record_without_geometry(self) -> None:
        fmt = ShapefileFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"name": "x"}])

    @pytest.mark.asyncio
    async def test_encode_rejects_empty_geometry_list(self) -> None:
        fmt = ShapefileFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(
                fmt, [{"geometry": [], "name": "x"}]
            )
