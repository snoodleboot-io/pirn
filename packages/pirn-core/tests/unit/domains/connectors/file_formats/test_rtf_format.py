"""Round-trip and validation tests for :class:`RtfFormat`."""

from __future__ import annotations

import unittest

try:
    import striprtf  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("striprtf not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.rtf_format import RtfFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestRtfFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = RtfFormat()
        assert fmt.encoding == "utf-8"

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            RtfFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            RtfFormat(encoding="")


class TestRtfFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert RtfFormat().name == "rtf"

    def test_streaming_property(self) -> None:
        assert RtfFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(RtfFormat(), BatchFileFormat)


class TestRtfFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = RtfFormat()
        records = [{"text": "Hello world from RTF."}]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert "Hello world from RTF" in decoded[0]["text"]

    async def test_round_trip_multi_record_concatenated(self) -> None:
        fmt = RtfFormat()
        records = [
            {"text": "First fragment."},
            {"text": "Second fragment."},
        ]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        # RTF has no record boundaries; reads always yield 1 record.
        assert len(decoded) == 1
        assert "First fragment" in decoded[0]["text"]
        assert "Second fragment" in decoded[0]["text"]

    async def test_round_trip_empty(self) -> None:
        fmt = RtfFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []

    async def test_round_trip_special_chars(self) -> None:
        fmt = RtfFormat()
        records = [{"text": "Curly braces {x} and a backslash \\."}]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert "{x}" in decoded[0]["text"]
        assert "\\" in decoded[0]["text"]


class TestRtfFormatValidation(unittest.IsolatedAsyncioTestCase):
    async def test_missing_text_key_raises(self) -> None:
        fmt = RtfFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"foo": "bar"}])

    async def test_non_string_text_rejected(self) -> None:
        fmt = RtfFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(fmt, [{"text": 1}])
