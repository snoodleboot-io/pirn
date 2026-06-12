"""Round-trip and validation tests for :class:`MarkdownFormat`."""

from __future__ import annotations

import unittest

try:
    import markdown_it  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("markdown_it not installed") from _e
try:
    import markdown  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("markdown not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.markdown_format import (
    MarkdownFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestMarkdownFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = MarkdownFormat()
        assert fmt.split_on == "heading"
        assert fmt.encoding == "utf-8"

    def test_split_on_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            MarkdownFormat(split_on=1)  # type: ignore[arg-type]

    def test_split_on_must_be_supported(self) -> None:
        with self.assertRaises(ValueError):
            MarkdownFormat(split_on="word")

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            MarkdownFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            MarkdownFormat(encoding="")


class TestMarkdownFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert MarkdownFormat().name == "markdown"

    def test_streaming_property(self) -> None:
        assert MarkdownFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(MarkdownFormat(), BatchFileFormat)


class TestMarkdownFormatHeadingMode(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = MarkdownFormat(split_on="heading")
        records = [
            {
                "title": "Introduction",
                "level": 1,
                "text": "First chapter prose.",
            },
            {
                "title": "Methods",
                "level": 1,
                "text": "Second chapter prose with details.",
            },
        ]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 2
        assert decoded[0]["title"] == "Introduction"
        assert decoded[0]["level"] == 1
        assert "First chapter prose" in decoded[0]["text"]
        assert decoded[1]["title"] == "Methods"
        assert "Second chapter prose" in decoded[1]["text"]

    async def test_round_trip_empty(self) -> None:
        fmt = MarkdownFormat(split_on="heading")
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []

    async def test_round_trip_single(self) -> None:
        fmt = MarkdownFormat(split_on="heading")
        records = [
            {"title": "Solo", "level": 1, "text": "Just one section."}
        ]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["title"] == "Solo"
        assert "Just one section" in decoded[0]["text"]


class TestMarkdownFormatParagraphMode(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = MarkdownFormat(split_on="paragraph")
        records = [
            {"text": "First paragraph.", "level": 0, "title": None},
            {"text": "Second paragraph.", "level": 0, "title": None},
            {"text": "Third paragraph.", "level": 0, "title": None},
        ]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 3
        assert decoded[0]["text"] == "First paragraph."


class TestMarkdownFormatFileMode(unittest.IsolatedAsyncioTestCase):
    async def test_decode_renders_html(self) -> None:
        fmt = MarkdownFormat(split_on="file")
        records = [
            {"text": "# Heading\n\nSome body.", "level": 0, "title": None}
        ]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert "<h1>" in decoded[0]["text"]


class TestMarkdownFormatValidation(unittest.IsolatedAsyncioTestCase):
    async def test_missing_text_key_raises(self) -> None:
        fmt = MarkdownFormat(split_on="paragraph")
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"title": "x", "level": 0}])

    async def test_non_string_text_raises(self) -> None:
        fmt = MarkdownFormat(split_on="heading")
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(
                fmt, [{"text": 1, "title": "x", "level": 1}]
            )
