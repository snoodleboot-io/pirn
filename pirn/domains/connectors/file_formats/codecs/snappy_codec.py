"""``SnappyCodec`` — Snappy compression via the ``python-snappy`` library.

Uses the **framed** Snappy format (Hadoop-style) — not raw Snappy
blocks — so streams are self-delimiting and concatenation works.
Implemented with :class:`snappy.StreamCompressor` /
:class:`snappy.StreamDecompressor`, which expose chunked
``add_chunk`` / ``decompress`` calls.

Install with ``pirn[snappy]``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pirn.domains.connectors.file_formats.codec import Codec


class SnappyCodec(Codec):
    """Framed Snappy codec. Requires ``pirn[snappy]`` extra."""

    @property
    def name(self) -> str:
        return "snappy"

    @staticmethod
    def _load_snappy() -> Any:
        try:
            import snappy
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "SnappyCodec requires the 'python-snappy' package. "
                "Install with: pip install 'pirn[snappy]'"
            ) from exc
        return snappy

    async def compress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        snappy = self._load_snappy()
        compressor = snappy.StreamCompressor()
        async for chunk in body:
            if not chunk:
                continue
            framed = compressor.add_chunk(chunk)
            if framed:
                yield framed

    async def decompress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        snappy = self._load_snappy()
        decompressor = snappy.StreamDecompressor()
        async for chunk in body:
            if not chunk:
                continue
            decoded = decompressor.decompress(chunk)
            if decoded:
                yield decoded
