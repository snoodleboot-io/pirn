"""Interface for file-format encoders/decoders (Parquet, CSV, JSON, Avro,
ORC, Delta, Iceberg).

A :class:`FileFormat` plugs into an :class:`ObjectStore` connector — the
object store handles transport, the file format handles encoding.
"""

from __future__ import annotations

from typing import Any, AsyncIterator


class FileFormat:
    """Interface every file-format implementation must satisfy."""

    @property
    def name(self) -> str:
        """Identifier used by registries and YAML pipelines."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement name"
        )

    async def read(self, body: AsyncIterator[bytes]) -> AsyncIterator[Any]:
        """Decode a streamed body into an iterator of records."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement read()"
        )

    async def write(self, records: AsyncIterator[Any]) -> AsyncIterator[bytes]:
        """Encode records into a streamed body."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement write()"
        )
