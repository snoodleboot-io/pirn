"""Round-trip and validation tests for :class:`HtmlFormat`.

HTML round-trip is lossy — the writer emits a minimal skeleton, so we
assert content survival rather than byte equality.
"""

from __future__ import annotations
import unittest


try:
    import bs4
except ImportError as _e:
    raise unittest.SkipTest("bs4 not installed") from _e
try:
    import lxml
except ImportError as _e:
    raise unittest.SkipTest("lxml not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.html_format import HtmlFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestHtmlFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = HtmlFormat()
        assert fmt.extract_tables is False

    def test_custom_arguments(self) -> None:
        fmt = HtmlFormat(extract_tables=True)
        assert fmt.extract_tables is True

    def test_non_bool_extract_tables(self) -> None:
        with self.assertRaises(TypeError):
            HtmlFormat(extract_tables="yes")  # type: ignore[arg-type]


class TestHtmlFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert HtmlFormat().name == "html"

    def test_streaming_property(self) -> None:
        assert HtmlFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(HtmlFormat(), BatchFileFormat)


class TestHtmlFormatDocumentMode(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {
                "title": "My Page",
                "text": "hello world",
                "links": [],
            }
        ]
        fmt = HtmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["title"] == "My Page"
        assert "hello world" in decoded[0]["text"]
        assert decoded[0]["links"] == []

    async def test_round_trip_empty(self) -> None:
        fmt = HtmlFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["title"] == ""
        assert decoded[0]["text"] == ""
        assert decoded[0]["links"] == []

    async def test_round_trip_single(self) -> None:
        records = [{"title": "T", "text": "single document"}]
        fmt = HtmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded[0]["title"] == "T"
        assert "single document" in decoded[0]["text"]

    async def test_decode_extracts_links(self) -> None:
        payload = (
            b"<html><head><title>links</title></head><body>"
            b'<a href="https://a.example">A</a>'
            b'<a href="https://b.example">B</a>'
            b"<p>body text</p>"
            b"</body></html>"
        )
        fmt = HtmlFormat()
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded[0]["title"] == "links"
        assert "body text" in decoded[0]["text"]
        assert decoded[0]["links"] == [
            "https://a.example",
            "https://b.example",
        ]

    async def test_decode_strips_script_and_style(self) -> None:
        payload = (
            b"<html><head><title>x</title>"
            b"<style>p{color:red}</style></head>"
            b"<body><script>alert(1)</script>"
            b"<p>visible content</p></body></html>"
        )
        fmt = HtmlFormat()
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert "alert" not in decoded[0]["text"]
        assert "color" not in decoded[0]["text"]
        assert "visible content" in decoded[0]["text"]

    async def test_encode_rejects_non_string_title(self) -> None:
        fmt = HtmlFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(fmt, [{"title": 9}])

    async def test_encode_rejects_non_string_text(self) -> None:
        fmt = HtmlFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(fmt, [{"text": 9}])

    async def test_encode_escapes_html_special_characters(self) -> None:
        records = [
            {"title": "<unsafe>", "text": "<script>alert(1)</script>"}
        ]
        fmt = HtmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        # The literal script tag must not survive into the output bytes.
        assert b"<script>alert(1)</script>" not in payload
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded[0]["title"] == "<unsafe>"
        assert "<script>alert(1)</script>" in decoded[0]["text"]


class TestHtmlFormatTableMode(unittest.IsolatedAsyncioTestCase):
    async def test_extract_tables_yields_one_record_per_row(self) -> None:
        payload = (
            b"<html><body><table>"
            b"<tr><th>name</th><th>age</th></tr>"
            b"<tr><td>alpha</td><td>1</td></tr>"
            b"<tr><td>beta</td><td>2</td></tr>"
            b"</table></body></html>"
        )
        fmt = HtmlFormat(extract_tables=True)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == [
            {"name": "alpha", "age": "1"},
            {"name": "beta", "age": "2"},
        ]

    async def test_extract_tables_no_header(self) -> None:
        payload = (
            b"<html><body><table>"
            b"<tr><td>x</td><td>y</td></tr>"
            b"<tr><td>1</td><td>2</td></tr>"
            b"</table></body></html>"
        )
        fmt = HtmlFormat(extract_tables=True)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == [
            {"col_0": "x", "col_1": "y"},
            {"col_0": "1", "col_1": "2"},
        ]

    async def test_extract_tables_no_table(self) -> None:
        payload = b"<html><body><p>no tables here</p></body></html>"
        fmt = HtmlFormat(extract_tables=True)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []
