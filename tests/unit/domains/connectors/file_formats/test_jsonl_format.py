"""Unit tests for :class:`JsonlFormat`."""

from __future__ import annotations
import unittest


from pirn.domains.connectors.file_formats.jsonl_format import JsonlFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestJsonlFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = JsonlFormat()
        assert fmt.encoding == "utf-8"

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            JsonlFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            JsonlFormat(encoding="")


class TestJsonlFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert JsonlFormat().name == "jsonl"

    def test_streaming_property(self) -> None:
        assert JsonlFormat().streaming is True


class TestJsonlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = JsonlFormat()
        records = [
            {"id": 1, "value": 1.5, "name": "alpha", "active": True, "note": None},
            {"id": 2, "value": 2.5, "name": "beta", "active": False, "note": "ok"},
            {"id": 3, "value": 3.5, "name": "gamma", "active": True, "note": None},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = JsonlFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        fmt = JsonlFormat()
        records = [{"id": 1, "value": 1.0, "name": "only", "active": True, "note": None}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_no_trailing_newline(self) -> None:
        fmt = JsonlFormat()
        records = [
            {"a": 1},
            {"a": 2},
            {"a": 3},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)
