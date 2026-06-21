"""Round-trip and validation tests for :class:`DocxFormat`."""

from __future__ import annotations

import unittest

try:
    import docx  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("docx not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.docx_format import DocxFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestDocxFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = DocxFormat()
        assert fmt.paragraph_separator == "\n"

    def test_custom_arguments(self) -> None:
        fmt = DocxFormat(paragraph_separator="\n\n")
        assert fmt.paragraph_separator == "\n\n"

    def test_non_string_paragraph_separator(self) -> None:
        with self.assertRaises(TypeError):
            DocxFormat(paragraph_separator=42)  # type: ignore[arg-type]


class TestDocxFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert DocxFormat().name == "docx"

    def test_streaming_property(self) -> None:
        assert DocxFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(DocxFormat(), BatchFileFormat)


class TestDocxFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {"text": "first paragraph", "style": "Normal"},
            {"text": "second paragraph", "style": "Normal"},
            {"text": "third paragraph", "style": "Normal"},
        ]
        fmt = DocxFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for index, (original, recovered) in enumerate(
            zip(records, decoded, strict=True)
        ):
            assert recovered["index"] == index
            assert recovered["text"] == original["text"]
            assert recovered["style"] == original["style"]

    async def test_round_trip_empty(self) -> None:
        fmt = DocxFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []

    async def test_round_trip_single(self) -> None:
        records = [{"text": "lonely paragraph"}]
        fmt = DocxFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["text"] == "lonely paragraph"
        assert decoded[0]["index"] == 0
        assert isinstance(decoded[0]["style"], str)

    async def test_round_trip_with_heading_style(self) -> None:
        records = [
            {"text": "Title here", "style": "Heading 1"},
            {"text": "body content"},
        ]
        fmt = DocxFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded[0]["style"] == "Heading 1"
        assert decoded[0]["text"] == "Title here"
        assert decoded[1]["text"] == "body content"

    async def test_encode_rejects_missing_text(self) -> None:
        fmt = DocxFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"style": "Normal"}])

    async def test_encode_rejects_non_string_text(self) -> None:
        fmt = DocxFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(fmt, [{"text": 123}])

    async def test_encode_rejects_non_string_style(self) -> None:
        fmt = DocxFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(
                fmt, [{"text": "hi", "style": 9}]
            )
