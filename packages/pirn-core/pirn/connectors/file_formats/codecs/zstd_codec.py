# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``ZstdCodec`` — Zstandard compression via the ``zstandard`` library.

Uses true streaming primitives:

* compress: ``ZstdCompressor.compressobj()`` for incremental ``compress``
  / ``flush`` calls, mirroring the ``zlib`` chunked pattern.
* decompress: ``ZstdDecompressor.decompressobj()`` for incremental decode.

Install with ``pip install "pirn-core[zstd]"``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pirn.connectors.file_formats.codec import Codec
from pirn.core.optional_dependency import OptionalDependency


class ZstdCodec(Codec):
    """Streaming Zstandard codec. Requires the ``pirn-core[zstd]`` extra."""

    def __init__(self, level: int = 3) -> None:
        if not isinstance(level, int):
            raise TypeError(f"ZstdCodec: level must be int, got {type(level).__name__}")
        self._level = level

    @property
    def name(self) -> str:
        return "zstd"

    async def compress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        zstandard = OptionalDependency.require("zstandard", extra="zstd")
        compressor = zstandard.ZstdCompressor(level=self._level)
        compressobj = compressor.compressobj()
        async for chunk in body:
            if not chunk:
                continue
            compressed: bytes = compressobj.compress(chunk)
            if compressed:
                yield compressed
        tail: bytes = compressobj.flush()
        if tail:
            yield tail

    async def decompress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        zstandard = OptionalDependency.require("zstandard", extra="zstd")
        decompressor = zstandard.ZstdDecompressor()
        decompressobj = decompressor.decompressobj()
        async for chunk in body:
            if not chunk:
                continue
            decompressed: bytes = decompressobj.decompress(chunk)
            if decompressed:
                yield decompressed
        tail: bytes = decompressobj.flush()
        if tail:
            yield tail
