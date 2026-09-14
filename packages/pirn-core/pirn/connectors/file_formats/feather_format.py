# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``FeatherFormat`` — Apache Arrow Feather v2 encoder/decoder.

Feather is the random-access on-disk form of the Arrow columnar
specification. It is distinct from Arrow IPC (the streaming form):
different file framing, different reader API. This module wraps
``pyarrow.feather``.

Install: ``pip install "pirn-core[feather]"`` (or ``"pirn-core[arrow]"``).
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.core.optional_dependency import OptionalDependency


class FeatherFormat(BatchFileFormat):
    """Whole-file Feather v2 encoder/decoder backed by ``pyarrow``."""

    _supported_compressions: ClassVar[frozenset[str]] = frozenset({"lz4", "zstd", "uncompressed"})

    def __init__(self, compression: str | None = None) -> None:
        if compression is not None:
            if not isinstance(compression, str):
                raise TypeError(
                    "FeatherFormat: compression must be a string or None, "
                    f"got {type(compression).__name__}"
                )
            if compression.lower() not in self._supported_compressions:
                raise ValueError(
                    "FeatherFormat: compression must be one of "
                    f"{sorted(self._supported_compressions)}, "
                    f"got {compression!r}"
                )
        self._compression = compression

    @property
    def name(self) -> str:
        return "feather"

    @property
    def compression(self) -> str | None:
        return self._compression

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        pa = OptionalDependency.require("pyarrow", extra="feather")
        feather = OptionalDependency.require("pyarrow.feather", extra="feather")
        table = feather.read_table(pa.BufferReader(payload))
        return [dict(row) for row in table.to_pylist()]

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        pa = OptionalDependency.require("pyarrow", extra="feather")
        feather = OptionalDependency.require("pyarrow.feather", extra="feather")
        materialised: list[Mapping[str, Any]] = list(records)
        table = pa.Table.from_pylist(materialised)
        buf = io.BytesIO()
        if self._compression is not None:
            feather.write_feather(table, buf, compression=self._compression)
        else:
            feather.write_feather(table, buf)
        return buf.getvalue()
