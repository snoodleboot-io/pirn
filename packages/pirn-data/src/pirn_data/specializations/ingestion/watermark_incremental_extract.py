"""``WatermarkIncrementalExtract`` — read only rows newer than the last
successful run by using ``MAX(watermark_column)`` from the target table.

The high-water mark lives *in the target table* — pirn doesn't manage a
separate state store.  This works when the target carries the watermark
column itself (a common pattern for append-only fact tables ordered by
``loaded_at`` / ``updated_at``).

Algorithm:
    1. Receive all inputs in ``process()`` and validate.
    2. Read ``MAX(watermark_column)`` from the target table; ``None``
       signals the initial load.
    3. Build a full SELECT (no WHERE) on initial load, or an incremental
       SELECT (``WHERE watermark_column > ?``) otherwise.
    4. Fetch new rows from the source.
    5. Build the INSERT query from ``columns`` and ``target_table``.
    6. Write new rows to the target via ``execute_many``.
    7. Return a summary dict with ``succeeded`` and ``rows_inserted``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class WatermarkIncrementalExtract(Knot):
    """Read source rows newer than the target's high-water mark."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_table: Knot | str,
        columns: Knot | Sequence[str],
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        watermark_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_table=source_table,
            columns=columns,
            target_pool=target_pool,
            target_table=target_table,
            watermark_column=watermark_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _build_insert_query(target_table: str, column_tuple: tuple[str, ...]) -> str:
        column_list = ", ".join(column_tuple)
        placeholders = ", ".join(["?"] * len(column_tuple))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_table: Any,
        columns: Any,
        target_pool: Any,
        target_table: Any,
        watermark_column: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Validate inputs, detect new rows via high-water mark, insert them, return summary.

        Args:
            source_pool: Pool to read source rows from.
            source_table: Source table name (alphanumeric + underscores).
            columns: Column names to select from the source and insert into the target.
            target_pool: Pool to read the high-water mark from and write rows to.
            target_table: Target table name (alphanumeric + underscores).
            watermark_column: Watermark column name (alphanumeric + underscores).

        Returns:
            A dict with ``succeeded`` and ``rows_inserted``.

        Raises:
            TypeError: If either pool is not a ``DatabaseConnectionPool``.
            ValueError: If any string argument is empty or contains invalid characters,
                or if ``columns`` is empty.
        """
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "WatermarkIncrementalExtract: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "WatermarkIncrementalExtract: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
            ("watermark_column", watermark_column),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"WatermarkIncrementalExtract: {label} must be a non-empty string")
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("WatermarkIncrementalExtract: columns must be non-empty")
        # Read the current high-water mark from the target table.
        hwm_rows = await target_pool.fetch_all(
            f"SELECT MAX({watermark_column}) FROM {target_table}"
        )
        high_water_mark = hwm_rows[0][0] if hwm_rows else None
        # Build and execute the source SELECT query.
        column_list = ", ".join(column_tuple)
        if high_water_mark is None:
            source_query = f"SELECT {column_list} FROM {source_table} ORDER BY {watermark_column}"
            new_rows = await source_pool.fetch_all(source_query)
        else:
            source_query = (
                f"SELECT {column_list} FROM {source_table} "
                f"WHERE {watermark_column} > ? "
                f"ORDER BY {watermark_column}"
            )
            new_rows = await source_pool.fetch_all(source_query, (high_water_mark,))
        insert_query = WatermarkIncrementalExtract._build_insert_query(target_table, column_tuple)
        await target_pool.execute_many(insert_query, [tuple(r) for r in new_rows])
        return {"succeeded": True, "rows_inserted": len(new_rows)}
