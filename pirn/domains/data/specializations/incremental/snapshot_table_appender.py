"""``SnapshotTableAppender`` — appends a full dated snapshot on every run.

Each execution reads every row from the source table and appends them to
the target with a ``_snapshot_date`` column set to the current UTC date.
This pattern is appropriate for small-to-medium dimension tables where a
complete daily history of every row is required for point-in-time analysis.
"""

from __future__ import annotations

from datetime import date, timezone, datetime
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class SnapshotTableAppender(SubTapestry):
    """Append a full dated snapshot of the source table on every run."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        source_columns: Sequence[str],
        snapshot_date_column: str = "_snapshot_date",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "SnapshotTableAppender: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "SnapshotTableAppender: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"SnapshotTableAppender: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column(
            "snapshot_date_column", snapshot_date_column
        )
        column_tuple = tuple(source_columns)
        IdentifierValidator.validate_columns("source_columns", column_tuple)
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._source_columns = column_tuple
        self._snapshot_date_column = snapshot_date_column
        super().__init__(_config=_config, **kwargs)

    @property
    def insert_query(self) -> str:
        all_cols = list(self._source_columns) + [self._snapshot_date_column]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Read all source rows and append them with today's snapshot date.

        Returns:
            A dict with keys ``succeeded``, ``target_table``,
            ``rows_appended``, and ``snapshot_date``.
        """
        snapshot_date = datetime.now(timezone.utc).date().isoformat()
        source_rows = await self._source_pool.fetch_all(self._source_query)
        rows_appended = 0
        for row in source_rows:
            params = tuple(row) + (snapshot_date,)
            await self._target_pool.execute(self.insert_query, params)
            rows_appended += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_appended": rows_appended,
            "snapshot_date": snapshot_date,
        }
