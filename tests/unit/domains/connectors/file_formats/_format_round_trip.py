"""Shared round-trip test helper for :class:`FileFormat` implementations.

Every concrete file format gets a ``test_<format>_round_trip`` test
that uses :class:`FormatRoundTrip` to encode a fixture batch, decode
the bytes, and assert equality. The helper handles both
:class:`StreamingFileFormat` and :class:`BatchFileFormat` shapes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.domains.connectors.file_format import FileFormat


class FormatRoundTrip:
    """Encode → decode → equality assertion for a :class:`FileFormat`."""

    @staticmethod
    async def encode(
        format: FileFormat,
        records: Sequence[Mapping[str, Any]],
    ) -> bytes:
        async def _record_iter() -> AsyncIterator[Mapping[str, Any]]:
            for record in records:
                yield record

        chunks: list[bytes] = []
        body_iter = await format.write(_record_iter())
        async for chunk in body_iter:
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def decode(
        format: FileFormat,
        payload: bytes,
    ) -> list[Mapping[str, Any]]:
        async def _byte_iter() -> AsyncIterator[bytes]:
            yield payload

        decoded: list[Mapping[str, Any]] = []
        record_iter = await format.read(_byte_iter())
        async for record in record_iter:
            decoded.append(dict(record))
        return decoded

    @classmethod
    async def assert_round_trip(
        cls,
        format: FileFormat,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        """Encode then decode; assert decoded equals input."""
        payload = await cls.encode(format, records)
        decoded = await cls.decode(format, payload)
        assert len(decoded) == len(records), (
            f"{format.name}: decoded {len(decoded)} != input {len(records)}"
        )
        for original, recovered in zip(records, decoded, strict=True):
            assert dict(original) == dict(recovered), (
                f"{format.name}: row mismatch — original={original} "
                f"decoded={recovered}"
            )
