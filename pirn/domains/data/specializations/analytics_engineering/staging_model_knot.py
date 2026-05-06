"""``StagingModelKnot`` — source-to-staging transform knot.

Reads rows from a source table via ``source_query``, applies column
renames, type casts, appends a ``_loaded_at`` metadata column, and
writes the results to a staging table.

Algorithm:
    1. Receive resolved ``source_pool``, ``source_query``, ``target_pool``,
       ``target_table``, ``column_map``, and ``loaded_at_column`` in
       ``process()``.
    2. Validate all inputs: pool types, non-empty strings, non-empty
       column_map, and identifier safety for all column names.
    3. Fetch all rows from the source via ``source_pool.fetch_all``.
    4. For each row, rename columns per ``column_map``, append the current
       UTC timestamp as ``loaded_at_column``, and INSERT into ``target_table``.
    5. Return a summary dict with ``succeeded``, ``target_table``, and
       ``rows_written``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class StagingModelKnot(Knot):
    """Apply source-to-staging transforms and write to a staging table.

    Renames columns, appends ``_loaded_at``, and inserts results into the
    target staging table.
    """

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        column_map: Knot | Any,
        loaded_at_column: Knot | str = "_loaded_at",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            column_map=column_map,
            loaded_at_column=loaded_at_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _insert_query(
        target_table: str,
        target_columns: tuple[str, ...],
    ) -> str:
        cols = ", ".join(target_columns)
        placeholders = ", ".join(["?"] * len(target_columns))
        return f"INSERT INTO {target_table} ({cols}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        column_map: Any,
        loaded_at_column: Any = "_loaded_at",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("StagingModelKnot: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("StagingModelKnot: target_pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"StagingModelKnot: {label} must be a non-empty string")
        if not column_map:
            raise ValueError("StagingModelKnot: column_map must be a non-empty mapping")
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("loaded_at_column", loaded_at_column)
        col_map = dict(column_map)
        for src_col, dst_col in col_map.items():
            IdentifierValidator.validate_column("column_map key", src_col)
            IdentifierValidator.validate_column("column_map value", dst_col)
        source_columns = list(col_map.keys())
        target_columns = tuple([*col_map.values(), loaded_at_column])
        insert_sql = StagingModelKnot._insert_query(target_table, target_columns)
        source_rows = await source_pool.fetch_all(source_query)
        loaded_at = datetime.now(UTC).isoformat()
        rows_written = 0
        for row in source_rows:
            row_dict = dict(zip(source_columns, row, strict=False))
            values = (*tuple(row_dict[c] for c in source_columns), loaded_at)
            await target_pool.execute(insert_sql, values)
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_written": rows_written,
        }
