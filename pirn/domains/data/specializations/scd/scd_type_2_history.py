"""``ScdType2History`` — Slowly Changing Dimension Type 2 (full history).

SCD Type 2 preserves a complete history of every tracked-attribute
change by keeping a separate row in the dimension table for every
distinct version of each natural-key entity. Each row carries
``valid_from`` / ``valid_to`` instants and an ``is_current`` flag.

Behaviour
---------
For each row from ``source_query``:

* If no row with the same ``key_columns`` exists in the target → insert
  the row with ``valid_from = now``, ``valid_to = NULL`` and
  ``is_current = 1``.
* If a current row exists with **different** values for any of the
  ``tracked_columns`` → close out the existing row
  (``valid_to = now``, ``is_current = 0``) and insert a new active
  row with the new tracked values.
* If a current row exists with identical tracked values → no change.

The target table must declare these columns up front: ``key_columns``,
``tracked_columns``, ``valid_from``, ``valid_to``, ``is_current``. The
caller supplies the column names so non-default conventions
(``effective_from`` etc.) work without wrapping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ScdType2History(SubTapestry):
    """Maintain full SCD Type 2 history for a dimension table."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        tracked_columns: Sequence[str],
        valid_from_column: str = "valid_from",
        valid_to_column: str = "valid_to",
        current_flag_column: str = "is_current",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType2History: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType2History: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ScdType2History: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column(
            "valid_from_column", valid_from_column
        )
        IdentifierValidator.validate_column(
            "valid_to_column", valid_to_column
        )
        IdentifierValidator.validate_column(
            "current_flag_column", current_flag_column
        )
        key_tuple = tuple(key_columns)
        tracked_tuple = tuple(tracked_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns(
            "tracked_columns", tracked_tuple
        )
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                "ScdType2History: key_columns and tracked_columns overlap on "
                f"{sorted(overlap)!r}"
            )
        envelope_overlap = (
            set(key_tuple) | set(tracked_tuple)
        ) & {valid_from_column, valid_to_column, current_flag_column}
        if envelope_overlap:
            raise ValueError(
                "ScdType2History: key/tracked columns clash with envelope "
                f"columns: {sorted(envelope_overlap)!r}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._tracked_columns = tracked_tuple
        self._valid_from_column = valid_from_column
        self._valid_to_column = valid_to_column
        self._current_flag_column = current_flag_column
        self._source_columns = key_tuple + tracked_tuple
        super().__init__(_config=_config, **kwargs)

    @property
    def select_current_query(self) -> str:
        cols = ", ".join(self._tracked_columns)
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return (
            f"SELECT {cols} FROM {self._target_table} "
            f"WHERE {where} AND {self._current_flag_column} = 1"
        )

    @property
    def close_out_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return (
            f"UPDATE {self._target_table} "
            f"SET {self._valid_to_column} = ?, {self._current_flag_column} = 0 "
            f"WHERE {where} AND {self._current_flag_column} = 1"
        )

    @property
    def insert_query(self) -> str:
        all_cols = list(self._source_columns) + [
            self._valid_from_column,
            self._valid_to_column,
            self._current_flag_column,
        ]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Apply Type 2 effective-dated history logic to each source row, closing old versions and inserting new ones.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, ``rows_inserted``, and ``rows_closed``
            summarising the merge outcome.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        rows_inserted = 0
        rows_closed = 0
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            key_values = tuple(row_dict[k] for k in self._key_columns)
            tracked_values = tuple(
                row_dict[k] for k in self._tracked_columns
            )
            existing = await self._target_pool.fetch_all(
                self.select_current_query, key_values
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            if not existing:
                await self._target_pool.execute(
                    self.insert_query,
                    key_values + tracked_values + (now_iso, None, 1),
                )
                rows_inserted += 1
                continue
            current_tracked = tuple(existing[0])
            if current_tracked == tracked_values:
                continue
            await self._target_pool.execute(
                self.close_out_query, (now_iso,) + key_values
            )
            rows_closed += 1
            await self._target_pool.execute(
                self.insert_query,
                key_values + tracked_values + (now_iso, None, 1),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
