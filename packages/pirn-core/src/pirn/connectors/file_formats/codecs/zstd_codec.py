"""``ZstdCodec`` — Zstandard compression via the ``zstandard`` library.

Uses true streaming primitives:

* compress: ``ZstdCompressor.compressobj()`` for incremental ``compress``
  / ``flush`` calls, mirroring the ``zlib`` chunked pattern.
* decompress: ``ZstdDecompressor.decompressobj()`` for incremental decode.

Install with ``pirn[zstd]``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.file_formats.codec import Codec


class ZstdCodec(Codec):
    """Streaming Zstandard codec. Requires ``pirn[zstd]`` extra."""

    def __init__(self, level: int = 3) -> None:
        if not isinstance(level, int):
            raise TypeError(f"ZstdCodec: level must be int, got {type(level).__name__}")
        self._level = level

    @property
    def name(self) -> str:
        return "zstd"

    @staticmethod
    def _load_zstandard() -> Any:
        try:
            import zstandard
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "ZstdCodec requires the 'zstandard' package. Install with: pip install 'pirn[zstd]'"
            ) from exc
        return zstandard

    async def compress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        zstandard = self._load_zstandard()
        compressor = zstandard.ZstdCompressor(level=self._level)
        compressobj = compressor.compressobj()
        async for chunk in body:
            if not chunk:
                continue
            compressed = compressobj.compress(chunk)
            if compressed:
                yield compressed
        tail = compressobj.flush()
        if tail:
            yield tail

    async def decompress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        zstandard = self._load_zstandard()
        decompressor = zstandard.ZstdDecompressor()
        decompressobj = decompressor.decompressobj()
        async for chunk in body:
            if not chunk:
                continue
            decompressed = decompressobj.decompress(chunk)
            if decompressed:
                yield decompressed
        tail = decompressobj.flush()
        if tail:
            yield tail
