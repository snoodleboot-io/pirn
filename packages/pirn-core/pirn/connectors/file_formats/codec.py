"""``Codec`` interface for compression codecs used by
:class:`CompressedFileFormat`.

Each codec implements :meth:`compress_stream` and
:meth:`decompress_stream`. Both work on :class:`AsyncIterator[bytes]`
so they layer cleanly with streaming file formats.
"""

from __future__ import annotations

from collections.abc import AsyncIterator


class Codec:
    """Interface for streaming compression codecs."""

    @property
    def name(self) -> str:
        """Codec identifier (``"gzip"``, ``"zstd"``, etc.)."""
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    def compress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Compress an incoming byte stream.

        Declared ``def``, not ``async def``: every concrete codec implements
        this as an async generator, whose *call* already returns the iterator.
        An ``async def`` declaration here would tell a caller typed against
        this interface to ``await`` the call — which raises ``TypeError``
        against every real codec (PIR-833). Call it and iterate the result.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement compress_stream()")

    def decompress_stream(self, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Decompress an incoming byte stream.

        Declared ``def`` for the same reason as :meth:`compress_stream`.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement decompress_stream()")
