"""Round-trip and validation tests for :class:`PdfFormat`.

PDF round-trip is intrinsically lossy — text is re-rendered through
``reportlab`` and re-extracted via ``pypdf``. Tests assert that the
text content survives (whitespace-normalised) rather than checking
byte equality.
"""

from __future__ import annotations

import unittest

try:
    import pypdf  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pypdf not installed") from _e
try:
    import reportlab  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("reportlab not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.pdf_format import PdfFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _normalise(text: str) -> str:
    return " ".join(text.split())


class TestPdfFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = PdfFormat()
        assert fmt.extract_layout is False

    def test_custom_arguments(self) -> None:
        fmt = PdfFormat(extract_layout=True)
        assert fmt.extract_layout is True

    def test_non_bool_extract_layout(self) -> None:
        with self.assertRaises(TypeError):
            PdfFormat(extract_layout="yes")  # type: ignore[arg-type]


class TestPdfFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert PdfFormat().name == "pdf"

    def test_streaming_property(self) -> None:
        assert PdfFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(PdfFormat(), BatchFileFormat)


class TestPdfFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_text_survives(self) -> None:
        records = [
            {"text": "alpha beta gamma"},
            {"text": "delta epsilon"},
            {"text": "zeta eta theta"},
        ]
        fmt = PdfFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for index, (original, recovered) in enumerate(
            zip(records, decoded, strict=True)
        ):
            assert recovered["page_number"] == index + 1
            assert _normalise(original["text"]) in _normalise(
                recovered["text"]
            )

    async def test_round_trip_empty(self) -> None:
        fmt = PdfFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        # Decoder still parses a valid PDF; one blank page is acceptable.
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) <= 1
        for record in decoded:
            assert _normalise(record["text"]) == ""

    async def test_round_trip_single(self) -> None:
        records = [{"text": "only one page here"}]
        fmt = PdfFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert _normalise("only one page here") in _normalise(
            decoded[0]["text"]
        )
        assert decoded[0]["page_number"] == 1

    async def test_extract_layout_includes_bbox(self) -> None:
        records = [{"text": "layout probe"}]
        writer = PdfFormat()
        reader = PdfFormat(extract_layout=True)
        payload = await FormatRoundTrip.encode(writer, records)
        decoded = await FormatRoundTrip.decode(reader, payload)
        assert "bbox" in decoded[0]
        bbox = decoded[0]["bbox"]
        assert {"x0", "y0", "x1", "y1"} <= set(bbox.keys())
        assert bbox["x1"] > bbox["x0"]
        assert bbox["y1"] > bbox["y0"]

    async def test_encode_rejects_missing_text(self) -> None:
        fmt = PdfFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"page_number": 1}])

    async def test_encode_rejects_non_string_text(self) -> None:
        fmt = PdfFormat()
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(fmt, [{"text": 123}])
