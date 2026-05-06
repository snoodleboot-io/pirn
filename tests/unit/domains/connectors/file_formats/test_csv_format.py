"""Unit tests for :class:`CsvFormat`.

CSV is a textual format with no type metadata, so the round-trip
fixtures use string values exclusively. Schema inference is a non-goal
of pirn (per Phase 4 PRD).
"""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats.csv_format import CsvFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestCsvFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = CsvFormat()
        assert fmt.delimiter == ","
        assert fmt.quotechar == '"'
        assert fmt.has_header is True
        assert fmt.column_names is None
        assert fmt.encoding == "utf-8"

    def test_delimiter_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            CsvFormat(delimiter=1)  # type: ignore[arg-type]

    def test_delimiter_must_be_single_char(self) -> None:
        with self.assertRaises(ValueError):
            CsvFormat(delimiter=",,")
        with self.assertRaises(ValueError):
            CsvFormat(delimiter="")

    def test_quotechar_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            CsvFormat(quotechar=1)  # type: ignore[arg-type]

    def test_quotechar_must_be_single_char(self) -> None:
        with self.assertRaises(ValueError):
            CsvFormat(quotechar='""')

    def test_has_header_must_be_bool(self) -> None:
        with self.assertRaises(TypeError):
            CsvFormat(has_header="yes")  # type: ignore[arg-type]

    def test_column_names_required_when_no_header(self) -> None:
        with self.assertRaises(ValueError):
            CsvFormat(has_header=False)

    def test_column_names_must_be_sequence_of_str(self) -> None:
        with self.assertRaises(TypeError):
            CsvFormat(column_names="abc")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            CsvFormat(column_names=[1, 2])  # type: ignore[list-item]

    def test_encoding_must_be_nonempty_str(self) -> None:
        with self.assertRaises(TypeError):
            CsvFormat(encoding=123)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            CsvFormat(encoding="")


class TestCsvFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert CsvFormat().name == "csv"

    def test_streaming_property(self) -> None:
        assert CsvFormat().streaming is True


class TestCsvFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = CsvFormat()
        records = [
            {"id": "1", "name": "alpha", "active": "true"},
            {"id": "2", "name": "beta", "active": "false"},
            {"id": "3", "name": "gamma", "active": "true"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = CsvFormat(
            has_header=False,
            column_names=("id", "name"),
        )
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        fmt = CsvFormat()
        records = [{"id": "1", "name": "only", "active": "true"}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

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

    async def test_round_trip_custom_delimiter(self) -> None:
        fmt = CsvFormat(delimiter=";")
        records = [
            {"a": "one", "b": "two"},
            {"a": "three", "b": "four"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)
