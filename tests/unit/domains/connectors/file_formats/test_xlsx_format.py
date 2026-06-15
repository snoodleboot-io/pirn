"""Round-trip and validation tests for :class:`XlsxFormat`."""

from __future__ import annotations

import unittest

try:
    import openpyxl  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("openpyxl not installed") from _e
try:
    import xlsxwriter  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("xlsxwriter not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.xlsx_format import (
    XlsxFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestXlsxFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = XlsxFormat()
        assert fmt.sheet_name == "Sheet1"
        assert fmt.has_header is True
        assert fmt.column_names is None

    def test_custom_arguments(self) -> None:
        fmt = XlsxFormat(
            sheet_name="Data",
            has_header=False,
            column_names=("a", "b"),
        )
        assert fmt.sheet_name == "Data"
        assert fmt.has_header is False
        assert fmt.column_names == ("a", "b")

    def test_empty_sheet_name(self) -> None:
        with self.assertRaises(ValueError):
            XlsxFormat(sheet_name="")

    def test_non_string_sheet_name(self) -> None:
        with self.assertRaises(ValueError):
            XlsxFormat(sheet_name=123)  # type: ignore[arg-type]

    def test_non_bool_has_header(self) -> None:
        with self.assertRaises(TypeError):
            XlsxFormat(has_header="yes")  # type: ignore[arg-type]

    def test_invalid_column_names_type(self) -> None:
        with self.assertRaises(TypeError):
            XlsxFormat(column_names="ab")  # type: ignore[arg-type]

    def test_empty_column_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            XlsxFormat(column_names=("a", ""))

    def test_no_header_requires_column_names(self) -> None:
        with self.assertRaises(ValueError):
            XlsxFormat(has_header=False)


class TestXlsxFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert XlsxFormat().name == "xlsx"

    def test_streaming_property(self) -> None:
        assert XlsxFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(XlsxFormat(), BatchFileFormat)


class TestXlsxFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
        ]
        fmt = XlsxFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = XlsxFormat(column_names=("id", "name"))
        # Empty: nothing to assert beyond a clean round trip.
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = XlsxFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_no_header(self) -> None:
        records = [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
        ]
        fmt = XlsxFormat(
            has_header=False, column_names=("id", "name")
        )
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_custom_sheet(self) -> None:
        records = [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
        ]
        fmt = XlsxFormat(sheet_name="Custom")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_decode_unknown_sheet_raises(self) -> None:
        records = [{"id": 1, "name": "alpha"}]
        writer = XlsxFormat(sheet_name="Sheet1")
        payload = await FormatRoundTrip.encode(writer, records)
        reader = XlsxFormat(sheet_name="Missing")
        with self.assertRaises(ValueError):
            await FormatRoundTrip.decode(reader, payload)
