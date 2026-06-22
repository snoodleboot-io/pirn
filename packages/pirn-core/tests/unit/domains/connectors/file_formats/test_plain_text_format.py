"""Unit tests for :class:`PlainTextFormat`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.connectors.file_formats.plain_text_format import (
    PlainTextFormat,
)
from pirn.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestPlainTextFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = PlainTextFormat()
        assert fmt.split_on == "line"
        assert fmt.encoding == "utf-8"

    def test_split_on_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            PlainTextFormat(split_on=1)  # type: ignore[arg-type]

    def test_split_on_must_be_supported(self) -> None:
        with self.assertRaises(ValueError):
            PlainTextFormat(split_on="word")

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            PlainTextFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            PlainTextFormat(encoding="")


class TestPlainTextFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert PlainTextFormat().name == "plain_text"

    def test_streaming_property(self) -> None:
        assert PlainTextFormat().streaming is True

    def test_inherits_streaming_base(self) -> None:
        assert isinstance(PlainTextFormat(), StreamingFileFormat)


class TestPlainTextFormatLineMode(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = PlainTextFormat(split_on="line")
        records = [
            {"text": "alpha", "line_number": 1},
            {"text": "beta", "line_number": 2},
            {"text": "gamma", "line_number": 3},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = PlainTextFormat(split_on="line")
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single(self) -> None:
        fmt = PlainTextFormat(split_on="line")
        records = [{"text": "solo", "line_number": 1}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_streaming_yields_incrementally(self) -> None:
        fmt = PlainTextFormat(split_on="line")

        async def _body() -> AsyncIterator[bytes]:
            yield b"first\n"
            yield b"second\n"
            yield b"third"

        decoded: list[Mapping[str, Any]] = []
        record_iter = await fmt.read(_body())
        async for record in record_iter:
            decoded.append(dict(record))
        assert decoded == [
            {"text": "first", "line_number": 1},
            {"text": "second", "line_number": 2},
            {"text": "third", "line_number": 3},
        ]


class TestPlainTextFormatParagraphMode(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = PlainTextFormat(split_on="paragraph")
        records = [
            {"text": "first paragraph"},
            {"text": "second paragraph\nwith two lines"},
            {"text": "third paragraph"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_single(self) -> None:
        fmt = PlainTextFormat(split_on="paragraph")
        records = [{"text": "lone paragraph"}]
        await FormatRoundTrip.assert_round_trip(fmt, records)


class TestPlainTextFormatFileMode(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = PlainTextFormat(split_on="file")
        records = [{"text": "whole file\ncontents\nas one record"}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = PlainTextFormat(split_on="file")
        await FormatRoundTrip.assert_round_trip(fmt, [])


class TestPlainTextFormatValidation(unittest.IsolatedAsyncioTestCase):
    async def test_missing_text_key_raises(self) -> None:
        fmt = PlainTextFormat(split_on="line")
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"line_number": 1}])

    async def test_non_string_text_raises(self) -> None:
        fmt = PlainTextFormat(split_on="line")
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(fmt, [{"text": 123}])
