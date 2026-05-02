"""Round-trip and validation tests for :class:`PptxFormat`.

Round-trip is lossy — ``python-pptx`` cannot recover the exact shape
geometry from a freshly emitted text frame. Tests assert text content
survival (whitespace-normalised) rather than byte equality.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pptx")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.pptx_format import PptxFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _normalise(text: str) -> str:
    return " ".join(text.split())


class TestPptxFormatConstruction:
    def test_default_arguments(self) -> None:
        fmt = PptxFormat()
        assert fmt.extract_speaker_notes is True

    def test_custom_arguments(self) -> None:
        fmt = PptxFormat(extract_speaker_notes=False)
        assert fmt.extract_speaker_notes is False

    def test_non_bool_extract_speaker_notes(self) -> None:
        with pytest.raises(TypeError):
            PptxFormat(extract_speaker_notes="yes")  # type: ignore[arg-type]


class TestPptxFormatBasics:
    def test_name(self) -> None:
        assert PptxFormat().name == "pptx"

    def test_streaming_property(self) -> None:
        assert PptxFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(PptxFormat(), BatchFileFormat)


class TestPptxFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_text_survives(self) -> None:
        records = [
            {"text": "slide one heading", "notes": "speaker note one"},
            {"text": "slide two body", "notes": None},
            {"text": "slide three closing", "notes": "final note"},
        ]
        fmt = PptxFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for index, (original, recovered) in enumerate(
            zip(records, decoded, strict=True)
        ):
            assert recovered["slide_number"] == index + 1
            assert _normalise(original["text"]) in _normalise(
                recovered["text"]
            )
            if original["notes"]:
                assert recovered["notes"] is not None
                assert _normalise(original["notes"]) in _normalise(
                    recovered["notes"]
                )

    @pytest.mark.asyncio
    async def test_round_trip_empty(self) -> None:
        fmt = PptxFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []

    @pytest.mark.asyncio
    async def test_round_trip_single(self) -> None:
        records = [{"text": "single slide content"}]
        fmt = PptxFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert _normalise("single slide content") in _normalise(
            decoded[0]["text"]
        )
        assert decoded[0]["slide_number"] == 1

    @pytest.mark.asyncio
    async def test_extract_speaker_notes_false(self) -> None:
        records = [{"text": "slide", "notes": "hidden notes"}]
        writer = PptxFormat()
        reader = PptxFormat(extract_speaker_notes=False)
        payload = await FormatRoundTrip.encode(writer, records)
        decoded = await FormatRoundTrip.decode(reader, payload)
        assert decoded[0]["notes"] is None

    @pytest.mark.asyncio
    async def test_encode_rejects_missing_text(self) -> None:
        fmt = PptxFormat()
        with pytest.raises(ValueError):
            await FormatRoundTrip.encode(fmt, [{"notes": "n"}])

    @pytest.mark.asyncio
    async def test_encode_rejects_non_string_text(self) -> None:
        fmt = PptxFormat()
        with pytest.raises(TypeError):
            await FormatRoundTrip.encode(fmt, [{"text": 9}])

    @pytest.mark.asyncio
    async def test_encode_rejects_non_string_notes(self) -> None:
        fmt = PptxFormat()
        with pytest.raises(TypeError):
            await FormatRoundTrip.encode(
                fmt, [{"text": "ok", "notes": 9}]
            )
