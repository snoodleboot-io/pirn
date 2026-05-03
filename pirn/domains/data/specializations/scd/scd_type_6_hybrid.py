"""``ScdType6Hybrid`` — Slowly Changing Dimension Type 6 (hybrid).

SCD Type 6 combines the behaviours of Type 1, Type 2, and Type 3
simultaneously:

* **Type 2** — a new history row is added on every change; old rows get
  ``valid_to`` stamped and ``is_current = 0``.
* **Type 1** — ``current_*`` columns on **every** row (including old
  history rows) are backfilled to always reflect the *latest* values of
  the tracked attributes.
* **Type 3** — ``previous_*`` columns on the *current* row carry the
  one-prior value at the moment of the change.

Behaviour
---------
For each source row:

* **New entity** → insert a single history row with
  ``valid_from = now``, ``valid_to = NULL``, ``is_current = 1``,
  ``current_*`` = new values, ``previous_*`` = NULL.
* **Changed entity** →
  1. Close the existing current row (``valid_to = now``, ``is_current = 0``).
  2. Insert a new current row with ``previous_*`` = old current tracked
     values and ``current_*`` = new tracked values.
  3. Backfill ``current_*`` on **all** rows for this key.
* **Unchanged entity** → no action.
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


class ScdType6Hybrid(SubTapestry):
    """Maintain SCD Type 6 (Type 1 + Type 2 + Type 3 combined)."""

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
        previous_columns: Mapping[str, str],
        valid_from_column: str = "valid_from",
        valid_to_column: str = "valid_to",
        current_flag_column: str = "is_current",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType6Hybrid: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "ScdType6Hybrid: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ScdType6Hybrid: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("target_table", target_table)
        for col_name, col_val in (
            ("valid_from_column", valid_from_column),
            ("valid_to_column", valid_to_column),
            ("current_flag_column", current_flag_column),
        ):
            IdentifierValidator.validate_column(col_name, col_val)
        key_tuple = tuple(key_columns)
        tracked_tuple = tuple(tracked_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("tracked_columns", tracked_tuple)
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                "ScdType6Hybrid: key_columns and tracked_columns overlap on "
                f"{sorted(overlap)!r}"
            )
        if not isinstance(current_columns, Mapping):
            raise TypeError(
                "ScdType6Hybrid: current_columns must be a Mapping[str, str]"
            )
        if not isinstance(previous_columns, Mapping):
            raise TypeError(
                "ScdType6Hybrid: previous_columns must be a Mapping[str, str]"
            )
        missing_current = [c for c in tracked_tuple if c not in current_columns]
        if missing_current:
            raise ValueError(
                f"ScdType6Hybrid: current_columns missing entries for {missing_current!r}"
            )
        missing_previous = [c for c in tracked_tuple if c not in previous_columns]
        if missing_previous:
            raise ValueError(
                f"ScdType6Hybrid: previous_columns missing entries for {missing_previous!r}"
            )
        for label, mapping in (
            ("current_columns", current_columns),
            ("previous_columns", previous_columns),
        ):
            for src, tgt in mapping.items():
                IdentifierValidator.validate_column(f"{label}[{src!r}]", tgt)
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._tracked_columns = tracked_tuple
        self._current_columns = dict(current_columns)
        self._previous_columns = dict(previous_columns)
        self._current_col_names = tuple(
            self._current_columns[c] for c in tracked_tuple
        )
        self._previous_col_names = tuple(
            self._previous_columns[c] for c in tracked_tuple
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
    def insert_query(self) -> str:
        all_cols = (
            list(self._key_columns)
            + list(self._tracked_columns)
            + list(self._current_col_names)
            + list(self._previous_col_names)
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

    @property
    def backfill_current_query(self) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in self._current_col_names)
        where = " AND ".join(f"{c} = ?" for c in self._key_columns)
        return f"UPDATE {self._target_table} SET {set_clause} WHERE {where}"

    async def process(self, **_: Any) -> dict[str, Any]:
        """Apply Type 6 hybrid SCD: insert new history rows, shift previous values, and backfill current columns on all rows.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, ``rows_inserted``,
            and ``rows_closed`` summarising the merge outcome.
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
                nulls = (None,) * len(self._previous_col_names)
                await self._target_pool.execute(
                    self.insert_query,
                    key_values
                    + tracked_values
                    + tracked_values
                    + nulls
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
                + current_tracked
                + (now_iso, None, 1),
            )
            rows_inserted += 1
            await self._target_pool.execute(
                self.backfill_current_query,
                tracked_values + key_values,
            )
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
