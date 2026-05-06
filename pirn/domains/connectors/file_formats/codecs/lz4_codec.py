"""``Lz4Codec`` — LZ4 frame compression via the ``lz4`` library.

Uses ``lz4.frame`` (the framed format with checksums and content size)
rather than the raw ``lz4.block`` format, so payloads are
self-describing. Buffers the input stream into a single buffer and
emits a single frame; use the file-format layer to chunk very large
single objects.

Install with ``pirn[lz4]``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pirn.domains.connectors.file_formats.codec import Codec


class Lz4Codec(Codec):
    """LZ4-frame codec. Requires ``pirn[lz4]`` extra."""

    @property
    def name(self) -> str:
        return "lz4"

    @staticmethod
    def _load_lz4_frame() -> Any:
        try:
            import lz4.frame as lz4_frame
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "Lz4Codec requires the 'lz4' package. "
                "Install with: pip install 'pirn[lz4]'"
            ) from exc
        return lz4_frame

    async def compress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        lz4_frame = self._load_lz4_frame()
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        yield lz4_frame.compress(payload)

    async def decompress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        lz4_frame = self._load_lz4_frame()
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            return
        yield lz4_frame.decompress(payload)
