"""``OrcFormat`` — Apache ORC batch encoder/decoder.

Uses ``pyarrow.orc`` (which depends on the bundled C++ ORC reader).
ORC files are columnar with a footer index; ``pyarrow`` requires the
full payload before it can produce a table, so this is a
:class:`BatchFileFormat`.

Install: ``pip install pirn[orc]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)


class OrcFormat(BatchFileFormat):
    """Whole-file ORC encoder/decoder backed by ``pyarrow.orc``."""

    _supported_compressions: ClassVar[frozenset[str]] = frozenset(
        {"uncompressed", "snappy", "zlib", "lz4", "zstd"}
    )

    def __init__(self, compression: str | None = None) -> None:
        if compression is not None:
            if not isinstance(compression, str):
                raise TypeError(
                    "OrcFormat: compression must be a string or None, "
                    f"got {type(compression).__name__}"
                )
            if compression.lower() not in self._supported_compressions:
                raise ValueError(
                    "OrcFormat: compression must be one of "
                    f"{sorted(self._supported_compressions)}, "
                    f"got {compression!r}"
                )
        self._compression = compression

    @property
    def name(self) -> str:
        return "orc"

    @property
    def compression(self) -> str | None:
        return self._compression

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        pa, orc = self._load_pyarrow_orc()
        buf = pa.BufferReader(payload)
        table = orc.read_table(buf)
        return [dict(row) for row in table.to_pylist()]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        pa, orc = self._load_pyarrow_orc()
        materialised: list[Mapping[str, Any]] = list(records)
        table = pa.Table.from_pylist(materialised)
        sink = pa.BufferOutputStream()
        if self._compression is not None:
            orc.write_table(table, sink, compression=self._compression)
        else:
            orc.write_table(table, sink)
        return bytes(sink.getvalue())

    @staticmethod
    def _load_pyarrow_orc() -> tuple[Any, Any]:
        try:
            import pyarrow as pa
            import pyarrow.orc as orc
        except ImportError as exc:
            raise ImportError(
                "OrcFormat requires pyarrow with ORC support. Install with `pip install pirn[orc]`."
            ) from exc
        return pa, orc
