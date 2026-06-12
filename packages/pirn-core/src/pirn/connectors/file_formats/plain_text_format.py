"""``PlainTextFormat`` — UTF-8 plain-text encoder/decoder using stdlib only.

Three split modes:

* ``"line"`` — one record per line. Genuinely streaming both directions.
* ``"paragraph"`` — paragraphs are double-newline-separated blocks.
* ``"file"`` — the whole file is a single record.

Records have shape ``{"text": str}`` for paragraph and file modes, and
``{"text": str, "line_number": int}`` for line mode (1-based).

No optional dependency — this format always works on a stock pirn
install.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar

from pirn.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class PlainTextFormat(StreamingFileFormat):
    """Plain-text file format backed by the stdlib codec machinery.

    Args:
        split_on: Record boundary mode. One of ``"line"``,
            ``"paragraph"``, ``"file"``.
        encoding: Text encoding for the byte stream. Defaults to
            ``"utf-8"``.
    """

    _supported_split_modes: ClassVar[frozenset[str]] = frozenset({"line", "paragraph", "file"})

    def __init__(
        self,
        split_on: str = "line",
        encoding: str = "utf-8",
    ) -> None:
        if not isinstance(split_on, str):
            raise TypeError("PlainTextFormat: split_on must be str")
        if split_on not in self._supported_split_modes:
            raise ValueError(
                "PlainTextFormat: split_on must be one of "
                f"{sorted(self._supported_split_modes)}, got "
                f"{split_on!r}"
            )
        if not isinstance(encoding, str):
            raise TypeError("PlainTextFormat: encoding must be str")
        if not encoding:
            raise ValueError("PlainTextFormat: encoding must be non-empty")
        self._split_on = split_on
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "plain_text"

    @property
    def split_on(self) -> str:
        return self._split_on

    @property
    def encoding(self) -> str:
        return self._encoding

    async def read(self, body: AsyncIterator[bytes]) -> AsyncIterator[Mapping[str, Any]]:
        encoding = self._encoding
        split_on = self._split_on

        if split_on == "line":
            return self._read_lines(body, encoding)
        if split_on == "paragraph":
            return self._read_paragraphs(body, encoding)
        return self._read_file(body, encoding)

    async def write(self, records: AsyncIterator[Mapping[str, Any]]) -> AsyncIterator[bytes]:
        encoding = self._encoding
        split_on = self._split_on

        if split_on == "line":
            return self._write_lines(records, encoding)
        if split_on == "paragraph":
            return self._write_paragraphs(records, encoding)
        return self._write_file(records, encoding)

    @staticmethod
    def _extract_text(record: Mapping[str, Any]) -> str:
        if "text" not in record:
            raise ValueError("PlainTextFormat: record missing required 'text' key")
        text = record["text"]
        if not isinstance(text, str):
            raise TypeError(
                f"PlainTextFormat: record 'text' value must be str, got {type(text).__name__}"
            )
        return text

    @classmethod
    def _read_lines(
        cls,
        body: AsyncIterator[bytes],
        encoding: str,
    ) -> AsyncIterator[Mapping[str, Any]]:
        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            buffered = bytearray()
            line_number = 0
            async for chunk in body:
                buffered.extend(chunk)
                while True:
                    newline_index = buffered.find(b"\n")
                    if newline_index == -1:
                        break
                    line = bytes(buffered[:newline_index])
                    del buffered[: newline_index + 1]
                    line_number += 1
                    text = line.decode(encoding)
                    yield {
                        "text": text,
                        "line_number": line_number,
                    }
            if buffered:
                line_number += 1
                text = bytes(buffered).decode(encoding)
                buffered.clear()
                yield {
                    "text": text,
                    "line_number": line_number,
                }

        return _iter()

    @classmethod
    def _read_paragraphs(
        cls,
        body: AsyncIterator[bytes],
        encoding: str,
    ) -> AsyncIterator[Mapping[str, Any]]:
        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            chunks: list[bytes] = []
            async for chunk in body:
                chunks.append(chunk)
            payload = b"".join(chunks)
            if not payload:
                return
            text = payload.decode(encoding)
            for paragraph in text.split("\n\n"):
                if paragraph == "":
                    continue
                yield {"text": paragraph}

        return _iter()

    @classmethod
    def _read_file(
        cls,
        body: AsyncIterator[bytes],
        encoding: str,
    ) -> AsyncIterator[Mapping[str, Any]]:
        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            chunks: list[bytes] = []
            async for chunk in body:
                chunks.append(chunk)
            payload = b"".join(chunks)
            if not payload:
                return
            yield {"text": payload.decode(encoding)}

        return _iter()

    @classmethod
    def _write_lines(
        cls,
        records: AsyncIterator[Mapping[str, Any]],
        encoding: str,
    ) -> AsyncIterator[bytes]:
        async def _iter() -> AsyncIterator[bytes]:
            first = True
            async for record in records:
                text = cls._extract_text(record)
                if first:
                    yield text.encode(encoding)
                    first = False
                else:
                    yield ("\n" + text).encode(encoding)

        return _iter()

    @classmethod
    def _write_paragraphs(
        cls,
        records: AsyncIterator[Mapping[str, Any]],
        encoding: str,
    ) -> AsyncIterator[bytes]:
        async def _iter() -> AsyncIterator[bytes]:
            first = True
            async for record in records:
                text = cls._extract_text(record)
                if first:
                    yield text.encode(encoding)
                    first = False
                else:
                    yield ("\n\n" + text).encode(encoding)

        return _iter()

    @classmethod
    def _write_file(
        cls,
        records: AsyncIterator[Mapping[str, Any]],
        encoding: str,
    ) -> AsyncIterator[bytes]:
        async def _iter() -> AsyncIterator[bytes]:
            async for record in records:
                text = cls._extract_text(record)
                yield text.encode(encoding)

        return _iter()
