"""``SnappyCodec`` — Snappy compression via the ``python-snappy`` library.

Uses the **framed** Snappy format (Hadoop-style) — not raw Snappy
blocks — so streams are self-delimiting and concatenation works.
Implemented with :class:`snappy.StreamCompressor` /
:class:`snappy.StreamDecompressor`, which expose chunked
``add_chunk`` / ``decompress`` calls.

Install with ``pip install "pirn-core[snappy]"``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pirn.connectors.file_formats.codec import Codec
from pirn.core.optional_dependency import OptionalDependency


class SnappyCodec(Codec):
    """Framed Snappy codec. Requires the ``pirn-core[snappy]`` extra."""

    @property
    def name(self) -> str:
        return "snappy"

    async def compress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        snappy = OptionalDependency.require("snappy", extra="snappy")
        compressor = snappy.StreamCompressor()
        async for chunk in body:
            if not chunk:
                continue
            framed: bytes = compressor.add_chunk(chunk)
            if framed:
                yield framed

    async def decompress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        snappy = OptionalDependency.require("snappy", extra="snappy")
        decompressor = snappy.StreamDecompressor()
        async for chunk in body:
            if not chunk:
                continue
            decoded: bytes = decompressor.decompress(chunk)
            if decoded:
                yield decoded
