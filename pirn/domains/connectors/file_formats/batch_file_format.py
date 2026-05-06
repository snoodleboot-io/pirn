"""``BatchFileFormat`` — whole-file decode/encode base.

Subclasses implement :meth:`_decode_full` and :meth:`_encode_full`. The
public :meth:`read` / :meth:`write` methods buffer the byte / record
stream and dispatch.

Right for formats whose libraries cannot decode incrementally — XLSX,
PDF, HDF5, DICOM, OpenSlide, etc.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Mapping
from typing import Any

from pirn.domains.connectors.file_format import FileFormat


class BatchFileFormat(FileFormat):
    """Base for formats that require full-file decode."""

    @property
    def streaming(self) -> bool:
        return False

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        """Decode a complete file payload into records."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement _decode_full()"
        )

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        """Encode a complete record sequence into a single byte payload."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement _encode_full()"
        )

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        payload = await self._drain_bytes(body)
        decoded = await self._decode_full(payload)

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for record in decoded:
                yield record

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        materialised = await self._drain_records(records)
        payload = await self._encode_full(materialised)

        async def _iter() -> AsyncIterator[bytes]:
            yield payload

        return _iter()
