"""``ScdType7Hybrid`` — Slowly Changing Dimension Type 7 (hybrid).

SCD Type 7 stores both the **historical** value (Type-2 style row
versioning) **and** the **current** value side-by-side on every row of
the dimension. Reports that need the latest snapshot read from the
``current_*`` columns; reports that need historical accuracy read from
the tracked columns plus ``valid_from`` / ``valid_to`` / ``is_current``.

Behaviour
---------
For each source row:

* Compute the version key (``key_columns`` + ``tracked_columns``).
* If no row with the same ``key_columns`` exists in the target →
  insert a row with both the historical *and* the current values
  populated to the new tracked values, ``valid_from = now``,
  ``valid_to = NULL``, ``is_current = 1``.
* If a current row exists with **different** values for any
  ``tracked_columns`` →
    1. Close out the existing current row (``valid_to = now``,
       ``is_current = 0``).
    2. Insert a new active row carrying the new tracked values both as
       historical and current.
    3. Backfill ``current_*`` columns on **every** historical row for
       the same key (so old versions know what "current" is now).

The caller supplies a mapping ``current_columns`` from
``tracked-source-name → current-target-column-name`` so the historical
column and its mirrored ``current_X`` companion can have engine-friendly
names without colliding.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ScdType7Hybrid(SubTapestry):
    """Maintain SCD Type 7 (current + history columns on every row)."""

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        tracked_columns: Sequence[str],
        current_columns: Mapping[str, str],
        valid_from_column: str = "valid_from",
        valid_to_column: str = "valid_to",
        current_flag_column: str = "is_current",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType7Hybrid: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType7Hybrid: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ScdType7Hybrid: {label} must be a non-empty string"
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
        if not isinstance(current_columns, Mapping):
            raise TypeError(
                "ScdType7Hybrid: current_columns must be a Mapping[str, str]"
            )
        missing = [c for c in tracked_tuple if c not in current_columns]
        if missing:
            raise ValueError(
                "ScdType7Hybrid: current_columns missing entries for "
                f"{missing!r}"
            )
        for label, value in current_columns.items():
            IdentifierValidator.validate_column(
                f"current_columns[{label!r}]", value
            )
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                "ScdType7Hybrid: key_columns and tracked_columns overlap on "
                f"{sorted(overlap)!r}"
            )
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._tracked_columns = tracked_tuple
        self._current_columns = dict(current_columns)
        # Resolve the current-mirror columns in tracked-column order so
        # the SET clause keeps the same shape as the parameter tuple.
        self._current_column_names = tuple(
            self._current_columns[c] for c in tracked_tuple
        )
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
    def update_current_mirror_query(self) -> str:
        set_clause = ", ".join(
            f"{c} = ?" for c in self._current_column_names
        )
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return (
            f"UPDATE {self._target_table} SET {set_clause} WHERE {where}"
        )

    @property
    def insert_query(self) -> str:
        all_cols = (
            list(self._source_columns)
            + list(self._current_column_names)
            + [
                self._valid_from_column,
                self._valid_to_column,
                self._current_flag_column,
            ]
        )
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
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
                    key_values
                    + tracked_values
                    + tracked_values
                    + (now_iso, None, 1),
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
                key_values
                + tracked_values
                + tracked_values
                + (now_iso, None, 1),
            )
            rows_inserted += 1
            # Backfill the current-mirror columns on every prior row
            # for this key so historical rows stay consistent with the
            # latest current_* values.
            await self._target_pool.execute(
                self.update_current_mirror_query,
                tracked_values + key_values,
            )
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
