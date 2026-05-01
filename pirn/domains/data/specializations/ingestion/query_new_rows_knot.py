"""``QueryNewRowsKnot`` — internal helper for
:class:`WatermarkIncrementalExtract`.

Generates and runs the appropriate source query based on the upstream
high-water mark:
- ``None`` (initial load) → ``SELECT <columns> FROM <table>``
- a value → ``SELECT <columns> FROM <table> WHERE <wmk_col> > ?``

Generating the SQL inside the knot means callers don't have to write a
template that handles both cases. Identifier guards (alphanumeric +
underscores) keep this defence-in-depth even though identifiers come
from configuration, not user input.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool


class QueryNewRowsKnot(Knot):
    """Generate and run an incremental SELECT against the source pool."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        table: str,
        columns: Sequence[str],
        watermark_column: str,
        high_water_mark: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "QueryNewRowsKnot: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(table, str) or not table:
            raise ValueError("QueryNewRowsKnot: table must be a non-empty string")
        if not isinstance(watermark_column, str) or not watermark_column:
            raise ValueError(
                "QueryNewRowsKnot: watermark_column must be a non-empty string"
            )
        for label, value in (("table", table), ("watermark_column", watermark_column)):
            if not value.replace("_", "").isalnum():
                raise ValueError(
                    f"QueryNewRowsKnot: {label} {value!r} must be alphanumeric"
                )
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("QueryNewRowsKnot: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column.replace("_", "").isalnum():
                raise ValueError(
                    f"QueryNewRowsKnot: column {column!r} must be alphanumeric"
                )
        self._pool = pool
        self._table = table
        self._columns = column_tuple
        self._watermark_column = watermark_column
        super().__init__(
            high_water_mark=high_water_mark, _config=_config, **kwargs
        )

    async def process(self, high_water_mark: Any, **_: Any) -> list:
        fetch_all = getattr(self._pool, "fetch_all", None)
        if fetch_all is None:
            raise TypeError(
                "QueryNewRowsKnot: pool does not support fetch_all()"
            )
        column_list = ", ".join(self._columns)
        if high_water_mark is None:
            query = (
                f"SELECT {column_list} FROM {self._table} "
                f"ORDER BY {self._watermark_column}"
            )
            return await fetch_all(query)
        query = (
            f"SELECT {column_list} FROM {self._table} "
            f"WHERE {self._watermark_column} > ? "
            f"ORDER BY {self._watermark_column}"
        )
        return await fetch_all(query, (high_water_mark,))
