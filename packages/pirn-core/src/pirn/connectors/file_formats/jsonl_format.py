"""``JsonlFormat`` — line-delimited JSON encoder/decoder using stdlib ``json``.

Genuinely streamable both directions: each line is one JSON object, so
records can be emitted as they're parsed and serialised as they're
received. Stdlib only — no optional dependency.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class JsonlFormat(StreamingFileFormat):
    """JSON Lines file format backed by stdlib ``json``.

    Args:
        encoding: Text encoding for the byte stream. Defaults to
            ``"utf-8"``.
    """

    def __init__(self, encoding: str = "utf-8") -> None:
        if not isinstance(encoding, str):
            raise TypeError("JsonlFormat: encoding must be str")
        if not encoding:
            raise ValueError("JsonlFormat: encoding must be non-empty")
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "jsonl"

    @property
    def encoding(self) -> str:
        return self._encoding

    async def read(self, body: AsyncIterator[bytes]) -> AsyncIterator[Mapping[str, Any]]:
        encoding = self._encoding
        buffered = bytearray()

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            async for chunk in body:
                buffered.extend(chunk)
                while True:
                    newline_index = buffered.find(b"\n")
                    if newline_index == -1:
                        break
                    line = bytes(buffered[:newline_index])
                    del buffered[: newline_index + 1]
                    text = line.decode(encoding).strip()
                    if not text:
                        continue
                    record = json.loads(text)
                    if not isinstance(record, dict):
                        raise ValueError(
                            f"JsonlFormat: line is not a JSON object: {type(record).__name__}"
                        )
                    yield record
            if buffered:
                text = bytes(buffered).decode(encoding).strip()
                buffered.clear()
                if text:
                    record = json.loads(text)
                    if not isinstance(record, dict):
                        raise ValueError(
                            f"JsonlFormat: line is not a JSON object: {type(record).__name__}"
                        )
                    yield record

        return _iter()

    async def write(self, records: AsyncIterator[Mapping[str, Any]]) -> AsyncIterator[bytes]:
        encoding = self._encoding

        async def _iter() -> AsyncIterator[bytes]:
            async for record in records:
                line = json.dumps(dict(record)) + "\n"
                yield line.encode(encoding)

        return _iter()
