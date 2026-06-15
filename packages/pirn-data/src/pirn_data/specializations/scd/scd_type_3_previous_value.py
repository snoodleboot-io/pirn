"""``ScdType3PreviousValue`` — Slowly Changing Dimension Type 3 (previous value).

SCD Type 3 stores both the current value **and** the one prior value for
each tracked attribute. When a tracked attribute changes, the old current
value shifts into the ``{col}_previous`` column and the new value is
written into the ``{col}`` column. Only one historical value is kept;
older history is lost.

Behaviour
---------
For each row from ``source_query``:

* If no row with the same ``key_columns`` exists in the target →
  insert the row with the tracked columns populated and every
  ``{col}_previous`` column set to ``NULL``.
* If a row exists with **different** values for any ``tracked_columns`` →
  shift current → previous and write the new current values in place
  (``UPDATE``).
* If a row exists with **identical** tracked values → no change.

The target table must declare ``key_columns``, ``tracked_columns``, and a
``{col}_previous`` companion for every tracked column.  Callers may
override the suffix via ``previous_suffix`` if their naming convention
differs (e.g. ``_prior``).

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows via ``source_pool.fetch_all``.
    3. For each source row, query the target for the existing row by key.
    4. If no row exists, INSERT with tracked values and NULL previous columns.
    5. If tracked values differ, UPDATE: shift current to previous, write new
       current values.
    6. If tracked values are identical, skip.
    7. Return a summary dict with ``rows_inserted`` and ``rows_updated``.

References:
    [1] Kimball Group — SCD Type 3 (add column):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-3/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class ScdType3PreviousValue(Knot):
    """Maintain SCD Type 3 (current + one prior value per tracked column)."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        tracked_columns: Knot | tuple[str, ...],
        previous_suffix: Knot | str = "_previous",
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
            previous_suffix=previous_suffix,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _select_current_query(
        target_table: str,
        key_columns: tuple[str, ...],
        tracked_columns: tuple[str, ...],
    ) -> str:
        cols = ", ".join(tracked_columns)
        where = " AND ".join(f"{c} = ?" for c in key_columns)
        return f"SELECT {cols} FROM {target_table} WHERE {where}"

    @staticmethod
    def _insert_query(
        target_table: str,
        key_columns: tuple[str, ...],
        tracked_columns: tuple[str, ...],
        previous_columns: tuple[str, ...],
    ) -> str:
        all_cols = [*key_columns, *tracked_columns, *previous_columns]
        column_list = ", ".join(all_cols)
        placeholders = ", ".join(["?"] * len(all_cols))
        return f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"

    @staticmethod
    def _update_query(
        target_table: str,
        key_columns: tuple[str, ...],
        tracked_columns: tuple[str, ...],
        previous_columns: tuple[str, ...],
    ) -> str:
        set_parts = []
        for current_col, previous_col in zip(tracked_columns, previous_columns, strict=False):
            set_parts.append(f"{previous_col} = {current_col}")
            set_parts.append(f"{current_col} = ?")
        set_clause = ", ".join(set_parts)
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
        previous_suffix: Any = "_previous",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ScdType3PreviousValue: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType3PreviousValue: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType3PreviousValue: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("ScdType3PreviousValue: target_table must be a non-empty string")
        if not isinstance(previous_suffix, str) or not previous_suffix:
            raise ValueError("ScdType3PreviousValue: previous_suffix must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        tracked_tuple = tuple(tracked_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        IdentifierValidator.validate_columns("tracked_columns", tracked_tuple)
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                "ScdType3PreviousValue: key_columns and tracked_columns overlap on "
                f"{sorted(overlap)!r}"
            )
        previous_columns = tuple(f"{c}{previous_suffix}" for c in tracked_tuple)
        for col in previous_columns:
            IdentifierValidator.validate_column("previous column", col)
        source_columns = key_tuple + tracked_tuple
        select_q = ScdType3PreviousValue._select_current_query(
            target_table, key_tuple, tracked_tuple
        )
        insert_q = ScdType3PreviousValue._insert_query(
            target_table, key_tuple, tracked_tuple, previous_columns
        )
        update_q = ScdType3PreviousValue._update_query(
            target_table, key_tuple, tracked_tuple, previous_columns
        )
        source_rows = await source_pool.fetch_all(source_query)
        rows_inserted = 0
        rows_updated = 0
        for row in source_rows:
            row_dict = dict(zip(source_columns, row, strict=False))
            key_values = tuple(row_dict[k] for k in key_tuple)
            tracked_values = tuple(row_dict[k] for k in tracked_tuple)
            existing = await target_pool.fetch_all(select_q, key_values)
            if not existing:
                nulls = (None,) * len(previous_columns)
                await target_pool.execute(
                    insert_q,
                    key_values + tracked_values + nulls,
                )
                rows_inserted += 1
                continue
            current_tracked = tuple(existing[0])
            if current_tracked == tracked_values:
                continue
            await target_pool.execute(
                update_q,
                tracked_values + key_values,
            )
            rows_updated += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
        }
