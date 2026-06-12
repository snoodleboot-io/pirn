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

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows via ``source_pool.fetch_all``.
    3. For each source row, query the target for the currently-active row.
    4. If no active row, INSERT new row with current values and NULL previous.
    5. If active row has identical tracked values, skip.
    6. If active row differs: close it, INSERT new row with previous = old
       values, then backfill ``current_*`` on all rows for this key.
    7. Return a summary dict with ``rows_inserted`` and ``rows_closed``.

References:
    [1] Kimball Group — SCD Type 6 (hybrid):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-6/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType6Hybrid(Knot):
    """Maintain SCD Type 6 (Type 1 + Type 2 + Type 3 combined)."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        tracked_columns: Knot | tuple[str, ...],
        current_columns: Knot | Mapping[str, str],
        previous_columns: Knot | Mapping[str, str],
        valid_from_column: Knot | str = "valid_from",
        valid_to_column: Knot | str = "valid_to",
        current_flag_column: Knot | str = "is_current",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source_pool=source_pool,
            source_query=source_query,
            target_pool=target_pool,
            target_table=target_table,
            key_columns=key_columns,
            tracked_columns=tracked_columns,
            current_columns=current_columns,
            previous_columns=previous_columns,
            valid_from_column=valid_from_column,
            valid_to_column=valid_to_column,
            current_flag_column=current_flag_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _select_current_query(
        target_table: str,
        key_columns: tuple[str, ...],
        tracked_columns: tuple[str, ...],
        current_flag_column: str,
    ) -> str:
        cols = ", ".join(tracked_columns)
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"SELECT {cols} FROM {target_table} WHERE {where} AND {current_flag_column} = 1"

    @staticmethod
    def _close_out_query(
        target_table: str,
        key_columns: tuple[str, ...],
        valid_to_column: str,
        current_flag_column: str,
    ) -> str:
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return (
            f"UPDATE {target_table} "
            f"SET {valid_to_column} = ?, {current_flag_column} = 0 "
            f"WHERE {where} AND {current_flag_column} = 1"
        )

    @staticmethod
    def _insert_query(
        target_table: str,
        key_columns: tuple[str, ...],
        tracked_columns: tuple[str, ...],
        current_col_names: tuple[str, ...],
        previous_col_names: tuple[str, ...],
        valid_from_column: str,
        valid_to_column: str,
        current_flag_column: str,
    ) -> str:
        all_cols = [
            *key_columns,
            *tracked_columns,
            *current_col_names,
            *previous_col_names,
            valid_from_column,
            valid_to_column,
            current_flag_column,
        ]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def _backfill_current_query(
        target_table: str,
        key_columns: tuple[str, ...],
        current_col_names: tuple[str, ...],
    ) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in current_col_names)
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where}"

    async def process(
        self,
        *,
        source_pool: Any,
        source_query: Any,
        target_pool: Any,
        target_table: Any,
        key_columns: Any,
        tracked_columns: Any,
        current_columns: Any,
        previous_columns: Any,
        valid_from_column: Any = "valid_from",
        valid_to_column: Any = "valid_to",
        current_flag_column: Any = "is_current",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ScdType6Hybrid: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType6Hybrid: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType6Hybrid: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("ScdType6Hybrid: target_table must be a non-empty string")
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
                f"ScdType6Hybrid: key_columns and tracked_columns overlap on {sorted(overlap)!r}"
            )
        if not isinstance(current_columns, Mapping):
            raise TypeError("ScdType6Hybrid: current_columns must be a Mapping[str, str]")
        if not isinstance(previous_columns, Mapping):
            raise TypeError("ScdType6Hybrid: previous_columns must be a Mapping[str, str]")
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
        current_col_names = tuple(current_columns[c] for c in tracked_tuple)
        previous_col_names = tuple(previous_columns[c] for c in tracked_tuple)
        source_columns = key_tuple + tracked_tuple
        select_q = ScdType6Hybrid._select_current_query(
            target_table, key_tuple, tracked_tuple, current_flag_column
        )
        close_q = ScdType6Hybrid._close_out_query(
            target_table, key_tuple, valid_to_column, current_flag_column
        )
        insert_q = ScdType6Hybrid._insert_query(
            target_table,
            key_tuple,
            tracked_tuple,
            current_col_names,
            previous_col_names,
            valid_from_column,
            valid_to_column,
            current_flag_column,
        )
        backfill_q = ScdType6Hybrid._backfill_current_query(
            target_table, key_tuple, current_col_names
        )
        source_rows = await source_pool.fetch_all(source_query)
        rows_inserted = 0
        rows_closed = 0
        for row in source_rows:
            row_dict = dict(zip(source_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            tracked_values = tuple(row_dict[k] for k in tracked_tuple)
            existing = await target_pool.fetch_all(select_q, key_values)
            now_iso = datetime.now(UTC).isoformat()
            if not existing:
                nulls = (None,) * len(previous_col_names)
                await target_pool.execute(
                    insert_q,
                    key_values + tracked_values + tracked_values + nulls + (now_iso, None, 1),
                )
                rows_inserted += 1
                continue
            current_tracked = tuple(existing[0])
            if current_tracked == tracked_values:
                continue
            await target_pool.execute(close_q, (now_iso, *key_values))
            rows_closed += 1
            await target_pool.execute(
                insert_q,
                key_values + tracked_values + tracked_values + current_tracked + (now_iso, None, 1),
            )
            rows_inserted += 1
            await target_pool.execute(backfill_q, tracked_values + key_values)
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
