"""Unit tests for :class:`CsvFormat`.

CSV is a textual format with no type metadata, so the round-trip
fixtures use string values exclusively. Schema inference is a non-goal
of pirn (per Phase 4 PRD).
"""

from __future__ import annotations

import pytest

from pirn.domains.connectors.file_formats.csv_format import CsvFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestCsvFormatConstruction:
    def test_default_construction(self) -> None:
        fmt = CsvFormat()
        assert fmt.delimiter == ","
        assert fmt.quotechar == '"'
        assert fmt.has_header is True
        assert fmt.column_names is None
        assert fmt.encoding == "utf-8"

    def test_delimiter_must_be_str(self) -> None:
        with pytest.raises(TypeError):
            CsvFormat(delimiter=1)  # type: ignore[arg-type]

    def test_delimiter_must_be_single_char(self) -> None:
        with pytest.raises(ValueError):
            CsvFormat(delimiter=",,")
        with pytest.raises(ValueError):
            CsvFormat(delimiter="")

    def test_quotechar_must_be_str(self) -> None:
        with pytest.raises(TypeError):
            CsvFormat(quotechar=1)  # type: ignore[arg-type]

    def test_quotechar_must_be_single_char(self) -> None:
        with pytest.raises(ValueError):
            CsvFormat(quotechar='""')

    def test_has_header_must_be_bool(self) -> None:
        with pytest.raises(TypeError):
            CsvFormat(has_header="yes")  # type: ignore[arg-type]

    def test_column_names_required_when_no_header(self) -> None:
        with pytest.raises(ValueError):
            CsvFormat(has_header=False)

    def test_column_names_must_be_sequence_of_str(self) -> None:
        with pytest.raises(TypeError):
            CsvFormat(column_names="abc")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            CsvFormat(column_names=[1, 2])  # type: ignore[list-item]

    def test_encoding_must_be_nonempty_str(self) -> None:
        with pytest.raises(TypeError):
            CsvFormat(encoding=123)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            CsvFormat(encoding="")


class TestCsvFormatProperties:
    def test_name(self) -> None:
        assert CsvFormat().name == "csv"

    def test_streaming_property(self) -> None:
        assert CsvFormat().streaming is True


class TestCsvFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        fmt = CsvFormat()
        records = [
            {"id": "1", "name": "alpha", "active": "true"},
            {"id": "2", "name": "beta", "active": "false"},
            {"id": "3", "name": "gamma", "active": "true"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_empty(self) -> None:
        fmt = CsvFormat(
            has_header=False,
            column_names=("id", "name"),
        )
        await FormatRoundTrip.assert_round_trip(fmt, [])

    @pytest.mark.asyncio
    async def test_round_trip_single_row(self) -> None:
        fmt = CsvFormat()
        records = [{"id": "1", "name": "only", "active": "true"}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_no_header(self) -> None:
        fmt = CsvFormat(
            has_header=False,
            column_names=("id", "name", "value"),
        )
        records = [
            {"id": "1", "name": "alpha", "value": "x"},
            {"id": "2", "name": "beta", "value": "y"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    @pytest.mark.asyncio
    async def test_round_trip_custom_delimiter(self) -> None:
        fmt = CsvFormat(delimiter=";")
        records = [
            {"a": "one", "b": "two"},
            {"a": "three", "b": "four"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)
