"""``Lz4Codec`` — LZ4 frame compression via the ``lz4`` library.

Uses ``lz4.frame`` (the framed format with checksums and content size)
rather than the raw ``lz4.block`` format, so payloads are
self-describing. Buffers the input stream into a single buffer and
emits a single frame; use the file-format layer to chunk very large
single objects.

Install with ``pip install "pirn-core[lz4]"``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pirn.connectors.file_formats.codec import Codec
from pirn.core.optional_dependency import OptionalDependency


class Lz4Codec(Codec):
    """LZ4-frame codec. Requires the ``pirn-core[lz4]`` extra."""

    @property
    def name(self) -> str:
        return "lz4"

    async def compress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        lz4_frame = OptionalDependency.require("lz4.frame", extra="lz4")
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        compressed: bytes = lz4_frame.compress(payload)
        yield compressed

    async def decompress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        lz4_frame = OptionalDependency.require("lz4.frame", extra="lz4")
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            return
        decompressed: bytes = lz4_frame.decompress(payload)
        yield decompressed
