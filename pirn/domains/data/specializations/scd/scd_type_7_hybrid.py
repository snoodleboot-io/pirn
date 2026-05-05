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

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows via ``source_pool.fetch_all``.
    3. For each source row, query the target for the currently-active row.
    4. If no active row, INSERT new row with both historical and current values.
    5. If active row has identical tracked values, skip.
    6. If active row differs: close it, INSERT new row with current values,
       then backfill ``current_*`` columns on all prior rows for this key.
    7. Return a summary dict with ``rows_inserted`` and ``rows_closed``.

References:
    [1] Kimball Group — SCD Type 7 (dual-type surrogate):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-7/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType7Hybrid(Knot):
    """Maintain SCD Type 7 (current + history columns on every row)."""

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
        return (
            f"SELECT {cols} FROM {target_table} "
            f"WHERE {where} AND {current_flag_column} = 1"
        )

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
    def _update_current_mirror_query(
        target_table: str,
        key_columns: tuple[str, ...],
        current_column_names: tuple[str, ...],
    ) -> str:
        set_clause = ", ".join(f"{c} = ?" for c in current_column_names)
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"UPDATE {target_table} SET {set_clause} WHERE {where}"

    @staticmethod
    def _insert_query(
        target_table: str,
        source_columns: tuple[str, ...],
        current_column_names: tuple[str, ...],
        valid_from_column: str,
        valid_to_column: str,
        current_flag_column: str,
    ) -> str:
        all_cols = [
            *source_columns,
            *current_column_names,
            valid_from_column,
            valid_to_column,
            current_flag_column,
        ]
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
        key_columns: Any,
        tracked_columns: Any,
        current_columns: Any,
        valid_from_column: Any = "valid_from",
        valid_to_column: Any = "valid_to",
        current_flag_column: Any = "is_current",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ScdType7Hybrid: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType7Hybrid: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType7Hybrid: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("ScdType7Hybrid: target_table must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        for col_label, col_name in (
            ("valid_from_column", valid_from_column),
            ("valid_to_column", valid_to_column),
            ("current_flag_column", current_flag_column),
        ):
            IdentifierValidator.validate_column(col_label, col_name)
        key_tuple = tuple(key_columns)
        tracked_tuple = tuple(tracked_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("tracked_columns", tracked_tuple)
        if not isinstance(current_columns, Mapping):
            raise TypeError("ScdType7Hybrid: current_columns must be a Mapping[str, str]")
        missing = [c for c in tracked_tuple if c not in current_columns]
        if missing:
            raise ValueError(
                f"ScdType7Hybrid: current_columns missing entries for {missing!r}"
            )
        for label, value in current_columns.items():
            IdentifierValidator.validate_column(f"current_columns[{label!r}]", value)
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                "ScdType7Hybrid: key_columns and tracked_columns overlap on "
                f"{sorted(overlap)!r}"
            )
        current_column_names = tuple(current_columns[c] for c in tracked_tuple)
        source_columns = key_tuple + tracked_tuple
        select_q = ScdType7Hybrid._select_current_query(
            target_table, key_tuple, tracked_tuple, current_flag_column
        )
        close_q = ScdType7Hybrid._close_out_query(
            target_table, key_tuple, valid_to_column, current_flag_column
        )
        mirror_q = ScdType7Hybrid._update_current_mirror_query(
            target_table, key_tuple, current_column_names
        )
        insert_q = ScdType7Hybrid._insert_query(
            target_table,
            source_columns,
            current_column_names,
            valid_from_column,
            valid_to_column,
            current_flag_column,
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
                await target_pool.execute(
                    insert_q,
                    key_values + tracked_values + tracked_values + (now_iso, None, 1),
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
                key_values + tracked_values + tracked_values + (now_iso, None, 1),
            )
            rows_inserted += 1
            await target_pool.execute(mirror_q, tracked_values + key_values)
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
