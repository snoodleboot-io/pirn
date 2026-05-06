"""``Bzip2Codec`` — bzip2 compression using stdlib :mod:`bz2`.

Same buffering trade-off as :class:`GzipCodec`: drain the byte stream
into a single buffer, then emit a single compressed/decompressed blob.
Right for per-file/per-batch payloads; chunk at the file-format layer
for very large single objects.
"""

from __future__ import annotations

import bz2
from collections.abc import AsyncIterator

from pirn.domains.connectors.file_formats.codec import Codec


class Bzip2Codec(Codec):
    """Stdlib bzip2 codec. No optional dependency required."""

    def __init__(self, compresslevel: int = 9) -> None:
        if not isinstance(compresslevel, int):
            raise TypeError(
                f"Bzip2Codec: compresslevel must be int, got {type(compresslevel).__name__}"
            )
        if not 1 <= compresslevel <= 9:
            raise ValueError(
                f"Bzip2Codec: compresslevel must be between 1 and 9, got {compresslevel}"
            )
        self._compresslevel = compresslevel

    @property
    def name(self) -> str:
        return "bzip2"

    async def compress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        yield bz2.compress(payload, compresslevel=self._compresslevel)

    async def decompress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            return
        yield bz2.decompress(payload)
