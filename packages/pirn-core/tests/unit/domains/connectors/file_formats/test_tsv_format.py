"""Unit tests for :class:`TsvFormat`."""

from __future__ import annotations

import unittest

from pirn.connectors.file_formats.tsv_format import TsvFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestTsvFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = TsvFormat()
        assert fmt.delimiter == "\t"
        assert fmt.quotechar == '"'
        assert fmt.has_header is True
        assert fmt.column_names is None
        assert fmt.encoding == "utf-8"

    def test_delimiter_must_be_single_char(self) -> None:
        with self.assertRaises(ValueError):
            TsvFormat(delimiter="\t\t")

    def test_column_names_required_when_no_header(self) -> None:
        with self.assertRaises(ValueError):
            TsvFormat(has_header=False)


class TestTsvFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert TsvFormat().name == "tsv"

    def test_streaming_property(self) -> None:
        assert TsvFormat().streaming is True


class TestTsvFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = TsvFormat()
        records = [
            {"id": "1", "name": "alpha", "active": "true"},
            {"id": "2", "name": "beta", "active": "false"},
            {"id": "3", "name": "gamma", "active": "true"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = TsvFormat(
            has_header=False,
            column_names=("id", "name"),
        )
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        fmt = TsvFormat()
        records = [{"id": "1", "name": "only", "active": "true"}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_no_header(self) -> None:
        fmt = TsvFormat(
            has_header=False,
            column_names=("id", "name"),
        )
        records = [
            {"id": "1", "name": "alpha"},
            {"id": "2", "name": "beta"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)
