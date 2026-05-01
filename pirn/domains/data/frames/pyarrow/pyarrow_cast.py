"""``PyarrowCast`` — Tier-2 type coercion via :func:`pyarrow.compute.cast`.

The ``casts`` mapping accepts column → PyArrow ``DataType`` pairs (e.g.
``{"id": pa.int64(), "amount": pa.float64()}``) or column → Python
primitive type pairs (``int``, ``float``, ``str``, ``bool``); the latter
are translated to the corresponding PyArrow type.
"""

from __future__ import annotations

from typing import Any, Mapping

import pyarrow as pa
import pyarrow.compute as pc

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowCast(Knot):
    """Coerce values per column to caller-specified PyArrow types."""

    def __init__(
        self,
        *,
        batch: Knot,
        casts: Mapping[str, Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(casts, Mapping) or not casts:
            raise TypeError(
                "PyarrowCast: casts must be a non-empty Mapping[column, dtype]"
            )
        for column in casts:
            if not isinstance(column, str) or not column:
                raise TypeError("PyarrowCast: casts keys must be non-empty strings")
        self._casts: dict[str, pa.DataType] = {
            column: self._normalise_dtype(column, dtype)
            for column, dtype in casts.items()
        }
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def casts(self) -> Mapping[str, pa.DataType]:
        return dict(self._casts)

    async def process(self, batch: PyarrowDataBatch, **_: Any) -> PyarrowDataBatch:
        applicable = {
            column: dtype for column, dtype in self._casts.items()
            if column in batch.table.column_names
        }
        if not applicable:
            return batch
        # Cast column-by-column. ``Table.cast(target_schema)`` exists but
        # requires a schema covering every column in the right order;
        # iterating with ``set_column`` keeps unmapped columns untouched
        # and avoids constructing a parallel schema.
        table = batch.table
        for column, dtype in applicable.items():
            field_index = table.schema.get_field_index(column)
            casted = pc.cast(table.column(column), dtype)
            table = table.set_column(
                field_index, pa.field(column, dtype), casted
            )
        return batch.with_table(table)

    def _normalise_dtype(self, column: str, dtype: Any) -> pa.DataType:
        # Already a PyArrow DataType? Pass through.
        if isinstance(dtype, pa.DataType):
            return dtype
        # Python primitive → PyArrow DataType.
        primitives: dict[type, pa.DataType] = {
            int: pa.int64(),
            float: pa.float64(),
            str: pa.string(),
            bool: pa.bool_(),
        }
        if isinstance(dtype, type) and dtype in primitives:
            return primitives[dtype]
        raise TypeError(
            f"PyarrowCast: casts[{column!r}] must be a pyarrow.DataType or a "
            f"Python primitive (int/float/str/bool), got {dtype!r}"
        )
