"""Round-trip and validation tests for :class:`EpubFormat`."""

from __future__ import annotations

import pytest

pytest.importorskip("ebooklib")

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.epub_format import EpubFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestEpubFormatConstruction:
    def test_default_arguments(self) -> None:
        fmt = EpubFormat()
        assert fmt.title == "pirn"
        assert fmt.language == "en"
        assert fmt.identifier == "pirn-epub"

    def test_custom_arguments(self) -> None:
        fmt = EpubFormat(
            title="Book", language="fr", identifier="custom-id"
        )
        assert fmt.title == "Book"
        assert fmt.language == "fr"
        assert fmt.identifier == "custom-id"

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValueError):
            EpubFormat(title="")

    def test_empty_language_rejected(self) -> None:
        with pytest.raises(ValueError):
            EpubFormat(language="")

    def test_empty_identifier_rejected(self) -> None:
        with pytest.raises(ValueError):
            EpubFormat(identifier="")

    def test_non_string_title_rejected(self) -> None:
        with pytest.raises(ValueError):
            EpubFormat(title=1)  # type: ignore[arg-type]


class TestEpubFormatProperties:
    def test_name(self) -> None:
        assert EpubFormat().name == "epub"

    def test_streaming_property(self) -> None:
        assert EpubFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(EpubFormat(), BatchFileFormat)


class TestEpubFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_basic(self) -> None:
        fmt = EpubFormat()
        records = [
            {
                "chapter_id": "intro",
                "title": "Introduction",
                "text": "Welcome to the first chapter.",
            },
            {
                "chapter_id": "body",
                "title": "Body",
                "text": "Here is the second chapter content.",
            },
        ]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        # ebooklib may add nav documents; filter to authored chapters.
        authored = [
            row
            for row in decoded
            if row["chapter_id"] in {"intro", "body"}
        ]
        assert len(authored) == 2
        assert any(
            "Welcome to the first chapter" in row["text"]
            for row in authored
        )
        assert any(
            "Here is the second chapter content" in row["text"]
            for row in authored
        )

    @pytest.mark.asyncio
    async def test_round_trip_single(self) -> None:
        fmt = EpubFormat()
        records = [
            {
                "chapter_id": "only",
                "title": "Only Chapter",
                "text": "Single chapter body text.",
            }
        ]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        authored = [
            row for row in decoded if row["chapter_id"] == "only"
        ]
        assert len(authored) == 1
        assert "Single chapter body text" in authored[0]["text"]

    @pytest.mark.asyncio
    async def test_decode_empty_payload(self) -> None:
        fmt = EpubFormat()
        decoded = await FormatRoundTrip.decode(fmt, b"")
        assert decoded == []


class TestEpubFormatValidation:
    @pytest.mark.asyncio
    async def test_non_string_text_rejected(self) -> None:
        fmt = EpubFormat()
        with pytest.raises(TypeError):
            await FormatRoundTrip.encode(
                fmt,
                [{"chapter_id": "x", "title": "y", "text": 1}],
            )
