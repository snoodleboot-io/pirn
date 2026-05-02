"""Round-trip and validation tests for :class:`OrcFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("pyarrow")
pytest.importorskip("pyarrow.orc")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.orc_format import (
    OrcFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestOrcFormatConstruction:
    def test_default_compression_is_none(self) -> None:
        fmt = OrcFormat()
        assert fmt.compression is None

    def test_valid_compression(self) -> None:
        fmt = OrcFormat(compression="zstd")
        assert fmt.compression == "zstd"

    def test_invalid_compression_value(self) -> None:
        with pytest.raises(ValueError):
            OrcFormat(compression="brotli")

    def test_invalid_compression_type(self) -> None:
        with pytest.raises(TypeError):
            OrcFormat(compression=123)  # type: ignore[arg-type]


class TestOrcFormatBasics:
    def test_name(self) -> None:
        assert OrcFormat().name == "orc"

    def test_streaming_property(self) -> None:
        assert OrcFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(OrcFormat(), BatchFileFormat)


class TestOrcFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
        ]
        fmt = OrcFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_with_compression(self) -> None:
        records = [
            {"id": 10, "label": "x"},
            {"id": 11, "label": "y"},
        ]
        fmt = OrcFormat(compression="zstd")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = OrcFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_empty(self) -> None:
        # PyArrow tolerates zero pylist rows: ``Table.from_pylist([])``
        # produces an empty table with no columns. The ORC reader then
        # returns an empty record list, which is the expected behaviour
        # when there are no rows to round-trip.
        fmt = OrcFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []
