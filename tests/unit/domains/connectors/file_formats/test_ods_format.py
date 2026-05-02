"""Round-trip and validation tests for :class:`OdsFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("odf")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.ods_format import (
    OdsFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestOdsFormatConstruction:
    def test_default_arguments(self) -> None:
        fmt = OdsFormat()
        assert fmt.sheet_name == "Sheet1"
        assert fmt.has_header is True

    def test_custom_arguments(self) -> None:
        fmt = OdsFormat(sheet_name="Data", has_header=False)
        assert fmt.sheet_name == "Data"
        assert fmt.has_header is False

    def test_empty_sheet_name(self) -> None:
        with pytest.raises(ValueError):
            OdsFormat(sheet_name="")

    def test_non_string_sheet_name(self) -> None:
        with pytest.raises(ValueError):
            OdsFormat(sheet_name=123)  # type: ignore[arg-type]

    def test_non_bool_has_header(self) -> None:
        with pytest.raises(TypeError):
            OdsFormat(has_header="yes")  # type: ignore[arg-type]


class TestOdsFormatBasics:
    def test_name(self) -> None:
        assert OdsFormat().name == "ods"

    def test_streaming_property(self) -> None:
        assert OdsFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(OdsFormat(), BatchFileFormat)


class TestOdsFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5},
            {"id": 2, "name": "beta", "score": 2.25},
            {"id": 3, "name": "gamma", "score": 3.75},
        ]
        fmt = OdsFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_empty(self) -> None:
        fmt = OdsFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    @pytest.mark.asyncio
    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = OdsFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_custom_sheet(self) -> None:
        records = [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
        ]
        fmt = OdsFormat(sheet_name="Custom")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_decode_unknown_sheet_raises(self) -> None:
        records = [{"id": 1, "name": "alpha"}]
        writer = OdsFormat(sheet_name="Sheet1")
        payload = await FormatRoundTrip.encode(writer, records)
        reader = OdsFormat(sheet_name="Missing")
        with pytest.raises(ValueError):
            await FormatRoundTrip.decode(reader, payload)
