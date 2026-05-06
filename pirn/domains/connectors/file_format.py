"""Interface for file-format encoders/decoders.

A :class:`FileFormat` plugs into an :class:`ObjectStore` connector — the
object store handles transport, the file format handles encoding.

Two flavours:

* :class:`StreamingFileFormat` — decode/encode incrementally. Right for
  Parquet, Arrow IPC, Avro, JSONL, line-delimited CSV.
* :class:`BatchFileFormat` — whole-file decode required. Right for
  XLSX, PDF, HDF5, DICOM. The base ``read`` / ``write`` helpers buffer
  the iterator and dispatch to ``_decode_full`` / ``_encode_full``.

Compression is layered separately via :class:`CompressedFileFormat`.
Multi-file archives (tar, zip) get their own wrapper shape.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class FileFormat(PirnOpaqueValue):
    """Base interface every file-format implementation must satisfy."""

    @property
    def name(self) -> str:
        """Identifier used by registries and YAML pipelines."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement name"
        )

    @property
    def streaming(self) -> bool:
        """``True`` if :meth:`read` and :meth:`write` decode/encode
        incrementally; ``False`` if the whole payload must be buffered.
        Default ``False`` — subclasses opt in by overriding or
        inheriting from :class:`StreamingFileFormat`."""
        return False

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Decode a streamed body into an iterator of records."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement read()"
        )

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        """Encode records into a streamed body."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement write()"
        )

    @staticmethod
    async def _drain_bytes(body: AsyncIterator[bytes]) -> bytes:
        """Buffer an async byte stream into a single ``bytes`` payload.

        Used by :class:`BatchFileFormat` and any consumer that needs
        the whole body in memory before decoding.
        """
        chunks: list[bytes] = []
        async for chunk in body:
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _drain_records(
        records: AsyncIterator[Mapping[str, Any]],
    ) -> list[Mapping[str, Any]]:
        """Buffer an async record stream into a list."""
        materialised: list[Mapping[str, Any]] = []
        async for record in records:
            materialised.append(record)
        return materialised
