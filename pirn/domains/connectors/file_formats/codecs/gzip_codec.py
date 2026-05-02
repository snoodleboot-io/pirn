"""``GzipCodec`` — gzip compression using stdlib :mod:`gzip`.

The implementation drains the input byte stream into a single buffer
and emits one compressed blob (and vice versa for decompression).
This keeps the implementation simple and correct at the cost of
holding the full payload in memory once. For typical pipeline
payloads (per-file/per-batch) this is the right trade-off; truly
massive single objects should be chunked at the file-format layer
above.
"""

from __future__ import annotations

import gzip
from typing import AsyncIterator

from pirn.domains.connectors.file_formats.codec import Codec


class GzipCodec(Codec):
    """Stdlib gzip codec. No optional dependency required."""

    def __init__(self, compresslevel: int = 9) -> None:
        if not isinstance(compresslevel, int):
            raise TypeError(
                "GzipCodec: compresslevel must be int, got "
                f"{type(compresslevel).__name__}"
            )
        if not 0 <= compresslevel <= 9:
            raise ValueError(
                "GzipCodec: compresslevel must be between 0 and 9, "
                f"got {compresslevel}"
            )
        self._compresslevel = compresslevel

    @property
    def name(self) -> str:
        return "gzip"

    async def compress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        yield gzip.compress(payload, compresslevel=self._compresslevel)

    async def decompress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            return
        yield gzip.decompress(payload)
