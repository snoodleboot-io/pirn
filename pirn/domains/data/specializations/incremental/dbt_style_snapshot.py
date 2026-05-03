"""``DbtStyleSnapshot`` — dbt-compatible timestamp/check snapshot strategy.

Implements the core of dbt's snapshot materialisation:

1. Compute a hash of the tracked columns for every source row.
2. Look up the currently-active snapshot row for each natural key.
3. Detect which rows have changed by comparing hashes.
4. Close old rows (set ``valid_to`` and ``is_current = 0``).
5. Insert new rows for changed or new natural keys.

The approach is equivalent to dbt's ``strategy: check`` / ``strategy:
timestamp`` modes collapsed into a single hash-based implementation.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class DbtStyleSnapshot(SubTapestry):
    """dbt-compatible snapshot: hash-based change detection with SCD Type 2 rows."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        tracked_columns: Sequence[str],
        valid_from_column: str = "dbt_valid_from",
        valid_to_column: str = "dbt_valid_to",
        current_flag_column: str = "dbt_is_current",
        row_hash_column: str = "dbt_scd_id",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "DbtStyleSnapshot: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "DbtStyleSnapshot: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"DbtStyleSnapshot: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        for col_label, col_name in (
            ("valid_from_column", valid_from_column),
            ("valid_to_column", valid_to_column),
            ("current_flag_column", current_flag_column),
            ("row_hash_column", row_hash_column),
        ):
            IdentifierValidator.validate_column(col_label, col_name)
        key_tuple = tuple(key_columns)
        tracked_tuple = tuple(tracked_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("tracked_columns", tracked_tuple)
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                f"DbtStyleSnapshot: key_columns and tracked_columns overlap "
                f"on {sorted(overlap)!r}"
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
        self._row_hash_column = row_hash_column
        self._source_columns = key_tuple + tracked_tuple
        super().__init__(_config=_config, **kwargs)

    def _compute_row_hash(self, tracked_values: tuple[Any, ...]) -> str:
        raw = "|".join(str(v) for v in tracked_values)
        return hashlib.md5(raw.encode()).hexdigest()

    @property
    def select_current_query(self) -> str:
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return (
            f"SELECT {self._row_hash_column} FROM {self._target_table} "
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
            self._row_hash_column,
        ]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Apply hash-based snapshot logic, closing old rows and inserting changed ones.

        Returns:
            A dict with keys ``succeeded``, ``target_table``,
            ``rows_inserted``, and ``rows_closed``.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        rows_inserted = 0
        rows_closed = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            key_values = tuple(row_dict[k] for k in self._key_columns)
            tracked_values = tuple(row_dict[k] for k in self._tracked_columns)
            new_hash = self._compute_row_hash(tracked_values)
            existing = await self._target_pool.fetch_all(
                self.select_current_query, key_values
            )
            if not existing:
                await self._target_pool.execute(
                    self.insert_query,
                    key_values + tracked_values + (now_iso, None, 1, new_hash),
                )
                rows_inserted += 1
                continue
            current_hash = existing[0][0]
            if current_hash == new_hash:
                continue
            await self._target_pool.execute(
                self.close_out_query, (now_iso,) + key_values
            )
            rows_closed += 1
            await self._target_pool.execute(
                self.insert_query,
                key_values + tracked_values + (now_iso, None, 1, new_hash),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
