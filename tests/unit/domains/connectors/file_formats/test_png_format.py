"""Round-trip and validation tests for :class:`PngFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.png_format import (
    PngFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _tiny_rgb_record() -> dict[str, object]:
    # 4x4 RGB checker pattern with deterministic pixel values.
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


class TestPngFormatConstruction:
    def test_default_construction(self) -> None:
        fmt = PngFormat()
        assert fmt.name == "png"


class TestPngFormatBasics:
    def test_name(self) -> None:
        assert PngFormat().name == "png"

    def test_streaming_property(self) -> None:
        assert PngFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(PngFormat(), BatchFileFormat)


class TestPngFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        record = _tiny_rgb_record()
        fmt = PngFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        recovered = decoded[0]
        # PNG is lossless — pixel-exactness must hold.
        assert recovered["width"] == record["width"]
        assert recovered["height"] == record["height"]
        assert recovered["mode"] == record["mode"]
        assert recovered["data"] == record["data"]

    @pytest.mark.asyncio
    async def test_round_trip_single_record(self) -> None:
        record = _tiny_rgb_record()
        fmt = PngFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [record])

    @pytest.mark.asyncio
    async def test_empty_records_rejected(self) -> None:
        fmt = PngFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    @pytest.mark.asyncio
    async def test_missing_field_rejected(self) -> None:
        fmt = PngFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(
                fmt, [{"width": 4, "height": 4, "mode": "RGB"}]
            )

    @pytest.mark.asyncio
    async def test_invalid_width_rejected(self) -> None:
        fmt = PngFormat()
        bad = {"width": 0, "height": 4, "mode": "RGB", "data": b"\x00"}
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [bad])
