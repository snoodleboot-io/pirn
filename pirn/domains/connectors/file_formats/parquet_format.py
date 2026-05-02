"""``ParquetFormat`` — Apache Parquet encoder/decoder using ``pyarrow.parquet``.

Streaming on the encode/decode boundary: the body is drained into a
``pyarrow.BufferReader`` (Parquet's footer is at end-of-file, so true
streaming reads are not possible without seekable storage) but row
groups are then emitted one-at-a-time on read, and a single buffered
``Table`` is written on encode. Marked ``streaming=True`` because we
stream rows out, not in.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, ClassVar, Mapping

from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)


class ParquetFormat(StreamingFileFormat):
    """Parquet file format backed by ``pyarrow.parquet``.

    Args:
        compression: Optional compression codec name forwarded to
            ``pyarrow.parquet.write_table``. ``None`` lets pyarrow pick
            its default. Allowed values: ``None``, ``"snappy"``,
            ``"gzip"``, ``"brotli"``, ``"zstd"``, ``"lz4"``, ``"none"``.
        row_group_size: Maximum number of rows per Parquet row group.
            Must be a positive integer.
    """

    _supported_compression: ClassVar[frozenset[str]] = frozenset(
        {"snappy", "gzip", "brotli", "zstd", "lz4", "none"}
    )

    def __init__(
        self,
        compression: str | None = None,
        row_group_size: int = 50_000,
    ) -> None:
        if compression is not None:
            if not isinstance(compression, str):
                raise TypeError(
                    "ParquetFormat: compression must be str | None"
                )
            if compression not in self._supported_compression:
                raise ValueError(
                    "ParquetFormat: compression must be one of "
                    f"{sorted(self._supported_compression)} or None, "
                    f"got {compression!r}"
                )
        if not isinstance(row_group_size, int) or isinstance(
            row_group_size, bool
        ):
            raise TypeError("ParquetFormat: row_group_size must be int")
        if row_group_size <= 0:
            raise ValueError(
                "ParquetFormat: row_group_size must be positive, "
                f"got {row_group_size}"
            )
        self._compression = compression
        self._row_group_size = row_group_size

    @property
    def name(self) -> str:
        return "parquet"

    @property
    def compression(self) -> str | None:
        return self._compression

    @property
    def row_group_size(self) -> int:
        return self._row_group_size

    async def read(
        self, body: AsyncIterator[bytes]
    ) -> AsyncIterator[Mapping[str, Any]]:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError(
                "ParquetFormat requires pyarrow. Install with "
                "'pip install pirn[data]' or 'pip install pirn[arrow]'."
            ) from exc

        payload = await self._drain_bytes(body)
        buffer = pa.BufferReader(payload)
        parquet_file = pq.ParquetFile(buffer)

        async def _iter() -> AsyncIterator[Mapping[str, Any]]:
            for group_index in range(parquet_file.num_row_groups):
                table = parquet_file.read_row_group(group_index)
                for record in table.to_pylist():
                    yield record

        return _iter()

    async def write(
        self, records: AsyncIterator[Mapping[str, Any]]
    ) -> AsyncIterator[bytes]:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError(
                "ParquetFormat requires pyarrow. Install with "
                "'pip install pirn[data]' or 'pip install pirn[arrow]'."
            ) from exc

        materialised = await self._drain_records(records)
        rows = [dict(record) for record in materialised]
        table = pa.Table.from_pylist(rows)
        buffer = pa.BufferOutputStream()
        pq.write_table(
            table,
            buffer,
            compression=self._compression,
            row_group_size=self._row_group_size,
        )
        payload = buffer.getvalue().to_pybytes()

        async def _iter() -> AsyncIterator[bytes]:
            yield payload

        return _iter()
