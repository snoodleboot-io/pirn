"""``SnapshotTableAppender`` — appends a full dated snapshot on every run.

Each execution reads every row from the source table and appends them to
the target with a ``_snapshot_date`` column set to the current UTC date.
This pattern is appropriate for small-to-medium dimension tables where a
complete daily history of every row is required for point-in-time analysis.

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Compute today's UTC date as an ISO-8601 string.
    3. Fetch all rows from the source via ``source_pool.fetch_all``.
    4. For each row, INSERT into the target with the snapshot date appended.
    5. Return a summary dict with ``succeeded``, ``target_table``,
       ``rows_appended``, and ``snapshot_date``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class SnapshotTableAppender(Knot):
    """Append a full dated snapshot of the source table on every run."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        source_columns: Knot | tuple[str, ...],
        snapshot_date_column: Knot | str = "_snapshot_date",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            source_columns=source_columns,
            snapshot_date_column=snapshot_date_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _insert_query(
        target_table: str,
        source_columns: tuple[str, ...],
        snapshot_date_column: str,
    ) -> str:
        all_cols = [*source_columns, snapshot_date_column]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        source_columns: Any,
        snapshot_date_column: Any = "_snapshot_date",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("SnapshotTableAppender: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("SnapshotTableAppender: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("SnapshotTableAppender: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("SnapshotTableAppender: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("snapshot_date_column", snapshot_date_column)
        column_tuple = tuple(source_columns)
        IdentifierValidator.validate_columns("source_columns", column_tuple)
        snapshot_date = datetime.now(UTC).date().isoformat()
        source_rows = await source_pool.fetch_all(source_query)
        rows_appended = 0
        for row in source_rows:
            params = (*row, snapshot_date)
            await target_pool.execute(
                SnapshotTableAppender._insert_query(
                    target_table, column_tuple, snapshot_date_column
                ),
                params,
            )
            rows_appended += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_appended": rows_appended,
            "snapshot_date": snapshot_date,
        }
