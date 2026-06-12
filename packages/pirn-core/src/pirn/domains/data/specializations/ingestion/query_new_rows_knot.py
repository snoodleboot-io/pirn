"""``QueryNewRowsKnot`` — generate and run the appropriate incremental
SELECT based on the upstream high-water mark.

- ``None`` (initial load) → ``SELECT <columns> FROM <table>``
- a value → ``SELECT <columns> FROM <table> WHERE <wmk_col> > ?``

Generating the SQL inside ``process()`` means callers don't have to
write a template that handles both cases.  Identifier guards
(alphanumeric + underscores) are applied in ``process()`` for
defence-in-depth.

Algorithm:
    1. Receive ``pool``, ``table``, ``columns``, ``watermark_column``,
       and ``high_water_mark`` in ``process()``.
    2. Validate pool type, non-empty identifiers, alphanumeric guard,
       and non-empty columns.
    3. Build a full SELECT (no WHERE) when ``high_water_mark`` is ``None``,
       or an incremental SELECT (``WHERE wmk_col > ?``) otherwise.
    4. Return the rows fetched from the pool.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — WatermarkIncrementalExtract:
        pirn/domains/data/specializations/ingestion/watermark_incremental_extract.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class QueryNewRowsKnot(Knot):
    """Generate and run an incremental SELECT against the source pool."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        table: Knot | str,
        columns: Knot | Sequence[str],
        watermark_column: Knot | str,
        high_water_mark: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            table=table,
            columns=columns,
            watermark_column=watermark_column,
            high_water_mark=high_water_mark,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: Any,
        table: Any,
        columns: Any,
        watermark_column: Any,
        high_water_mark: Any,
        **_: Any,
    ) -> list:
        """Validate inputs, build the SELECT query, execute it, and return the rows.

        Args:
            pool: The source database connection pool.
            table: The source table name (alphanumeric + underscores).
            columns: Sequence of column names to select.
            watermark_column: The watermark column name (alphanumeric + underscores).
            high_water_mark: The current high-water mark value, or ``None`` for initial load.

        Returns:
            A list of rows returned by the source query.

        Raises:
            TypeError: If ``pool`` is not a ``DatabaseConnectionPool`` or lacks ``fetch_all``.
            ValueError: If identifiers are empty or contain invalid characters.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("QueryNewRowsKnot: pool must be a DatabaseConnectionPool")
        if not isinstance(table, str) or not table:
            raise ValueError("QueryNewRowsKnot: table must be a non-empty string")
        if not isinstance(watermark_column, str) or not watermark_column:
            raise ValueError("QueryNewRowsKnot: watermark_column must be a non-empty string")
        for label, value in (("table", table), ("watermark_column", watermark_column)):
            if not value.replace("_", "").isalnum():
                raise ValueError(f"QueryNewRowsKnot: {label} {value!r} must be alphanumeric")
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("QueryNewRowsKnot: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column.replace("_", "").isalnum():
                raise ValueError(f"QueryNewRowsKnot: column {column!r} must be alphanumeric")
        fetch_all = getattr(pool, "fetch_all", None)
        if fetch_all is None:
            raise TypeError("QueryNewRowsKnot: pool does not support fetch_all()")
        column_list = ", ".join(column_tuple)
        if high_water_mark is None:
            query = f"SELECT {column_list} FROM {table} ORDER BY {watermark_column}"
            return await fetch_all(query)
        query = (
            f"SELECT {column_list} FROM {table} "
            f"WHERE {watermark_column} > ? "
            f"ORDER BY {watermark_column}"
        )
        return await fetch_all(query, (high_water_mark,))
