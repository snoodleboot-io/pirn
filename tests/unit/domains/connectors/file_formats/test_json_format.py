"""Unit tests for :class:`JsonFormat`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats.json_format import JsonFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestJsonFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = JsonFormat()
        assert fmt.array_root is True
        assert fmt.encoding == "utf-8"

    def test_array_root_must_be_bool(self) -> None:
        with self.assertRaises(TypeError):
            JsonFormat(array_root="yes")  # type: ignore[arg-type]

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            JsonFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            JsonFormat(encoding="")


class TestJsonFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert JsonFormat().name == "json"

    def test_streaming_property(self) -> None:
        assert JsonFormat().streaming is True


class TestJsonFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = JsonFormat()
        records = [
            {"id": 1, "value": 1.5, "name": "alpha", "active": True, "note": None},
            {"id": 2, "value": 2.5, "name": "beta", "active": False, "note": "ok"},
            {"id": 3, "value": 3.5, "name": "gamma", "active": True, "note": None},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = JsonFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        fmt = JsonFormat()
        records = [{"id": 1, "value": 1.0, "name": "only", "active": True, "note": None}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_object_root_single(self) -> None:
        fmt = JsonFormat(array_root=False)
        records = [{"id": 7, "name": "single", "active": True}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_object_root_rejects_multiple_records_on_write(self) -> None:
        fmt = JsonFormat(array_root=False)
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(
                fmt,
                [{"a": 1}, {"a": 2}],
            )
