"""Shared round-trip helper for :class:`Codec` implementations.

Reused by the per-codec test modules. Each helper drains a codec's
async-generator output into a single ``bytes`` blob and asserts that
``decompress(compress(payload)) == payload``.
"""

from __future__ import annotations

from typing import AsyncIterator

from pirn.domains.connectors.file_formats.codec import Codec


class CodecRoundTrip:
    """Compress → decompress → equality assertion for a :class:`Codec`."""

    @staticmethod
    async def _byte_iter(payload: bytes) -> AsyncIterator[bytes]:
        if payload:
            yield payload

    @classmethod
    async def compress(cls, codec: Codec, payload: bytes) -> bytes:
        chunks: list[bytes] = []
        async for chunk in codec.compress_stream(cls._byte_iter(payload)):
            chunks.append(chunk)
        return b"".join(chunks)

    @classmethod
    async def decompress(cls, codec: Codec, payload: bytes) -> bytes:
        chunks: list[bytes] = []
        async for chunk in codec.decompress_stream(cls._byte_iter(payload)):
            chunks.append(chunk)
        return b"".join(chunks)

    @classmethod
    async def round_trip(cls, codec: Codec, payload: bytes) -> bytes:
        compressed = await cls.compress(codec, payload)
        recovered = await cls.decompress(codec, compressed)
        assert recovered == payload, (
            f"{codec.name}: decompressed {len(recovered)} bytes != "
            f"input {len(payload)} bytes"
        )
        return compressed
