"""``Codec`` interface for compression codecs used by
:class:`CompressedFileFormat`.

Each codec implements :meth:`compress_stream` and
:meth:`decompress_stream`. Both work on :class:`AsyncIterator[bytes]`
so they layer cleanly with streaming file formats.
"""

from __future__ import annotations

from typing import AsyncIterator


class Codec:
    """Interface for streaming compression codecs."""

    @property
    def name(self) -> str:
        """Codec identifier (``"gzip"``, ``"zstd"``, etc.)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement name"
        )

    async def compress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        """Compress an incoming byte stream."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement compress_stream()"
        )

    async def decompress_stream(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[bytes]:
        """Decompress an incoming byte stream."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement decompress_stream()"
        )
