"""``ArrowIpcFormat`` — Apache Arrow IPC stream encoder/decoder.

Uses ``pyarrow.ipc`` to read and write the Arrow IPC streaming format
(``new_stream`` / ``open_stream``). Suitable for shared-memory hand-off
and Feather v2 payloads.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, ClassVar, Mapping

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class ArrowIpcFormat(StreamingFileFormat):
    """Arrow IPC streaming format backed by ``pyarrow.ipc``.

    Args:
        compression: Optional Arrow IPC compression codec. ``None``
            disables compression. Allowed values: ``None``, ``"lz4"``,
            ``"zstd"``.
    """

    _supported_compression: ClassVar[frozenset[str]] = frozenset(
        {"lz4", "zstd"}
    )

    def __init__(self, compression: str | None = None) -> None:
        if compression is not None:
            if not isinstance(compression, str):
                raise TypeError(
                    "ArrowIpcFormat: compression must be str | None"
                )
            if compression not in self._supported_compression:
                raise ValueError(
                    "ArrowIpcFormat: compression must be one of "
                    f"{sorted(self._supported_compression)} or None, "
                    f"got {compression!r}"
                )
        self._compression = compression

    @property
    def name(self) -> str:
        return "arrow_ipc"

    @property
    def compression(self) -> str | None:
        return self._compression

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        try:
            import pyarrow as pa
            import pyarrow.ipc as ipc
        except ImportError as exc:
            raise ImportError(
                "ArrowIpcFormat requires pyarrow. Install with "
                "'pip install pirn[arrow]'."
            ) from exc

        payload = await self._drain_bytes(body)
        buffer = pa.BufferReader(payload)
        reader = ipc.open_stream(buffer)

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for batch in reader:
                for record in batch.to_pylist():
                    yield record

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        try:
            import pyarrow as pa
            import pyarrow.ipc as ipc
        except ImportError as exc:
            raise ImportError(
                "ArrowIpcFormat requires pyarrow. Install with "
                "'pip install pirn[arrow]'."
            ) from exc

        materialised = await self._drain_records(records)
        rows = [dict(record) for record in materialised]
        table = pa.Table.from_pylist(rows)

        sink = pa.BufferOutputStream()
        options = (
            ipc.IpcWriteOptions(compression=self._compression)
            if self._compression is not None
            else None
        )
        if options is None:
            writer = ipc.new_stream(sink, table.schema)
        else:
            writer = ipc.new_stream(sink, table.schema, options=options)
        try:
            writer.write_table(table)
        finally:
            writer.close()
        payload = sink.getvalue().to_pybytes()

        async def _iter() -> AsyncIterator[bytes]:
            yield payload

        return _iter()
