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

Algorithm:
    1. Receive all resolved inputs in ``process()`` and validate.
    2. Fetch all source rows via ``source_pool.fetch_all``.
    3. For each source row, query the target for the currently-active row
       by natural key.
    4. If no active row exists, insert a new row with ``is_current = 1``.
    5. If the tracked columns differ from the stored values, close the
       current row (``valid_to = now``, ``is_current = 0``) then insert
       a new active row.
    6. If the tracked values are unchanged, skip the row.
    7. Return a summary dict with ``rows_inserted`` and ``rows_closed``.

References:
    [1] Kimball Group — SCD Type 2 (add row):
        https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class ScdType2History(Knot):
    """Maintain full SCD Type 2 history for a dimension table."""

    def __init__(
        self,
        *,
        source_pool: Knot | DatabaseConnectionPool,
        source_query: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        tracked_columns: Knot | tuple[str, ...],
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
    def _insert_query(
        target_table: str,
        source_columns: tuple[str, ...],
        valid_from_column: str,
        valid_to_column: str,
        current_flag_column: str,
    ) -> str:
        all_cols = [*source_columns, valid_from_column, valid_to_column, current_flag_column]
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
        valid_from_column: Any = "valid_from",
        valid_to_column: Any = "valid_to",
        current_flag_column: Any = "is_current",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError("ScdType2History: source_pool must be a DatabaseConnectionPool")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("ScdType2History: target_pool must be a DatabaseConnectionPool")
        if not isinstance(source_query, str) or not source_query:
            raise ValueError("ScdType2History: source_query must be a non-empty string")
        if not isinstance(target_table, str) or not target_table:
            raise ValueError("ScdType2History: target_table must be a non-empty string")
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
        overlap = set(key_tuple) & set(tracked_tuple)
        if overlap:
            raise ValueError(
                "ScdType2History: key_columns and tracked_columns overlap on "
                f"{sorted(overlap)!r}"
            )
        envelope_overlap = (set(key_tuple) | set(tracked_tuple)) & {
            valid_from_column,
            valid_to_column,
            current_flag_column,
        }
        if envelope_overlap:
            raise ValueError(
                "ScdType2History: key/tracked columns clash with envelope "
                f"columns: {sorted(envelope_overlap)!r}"
            )
        source_columns = key_tuple + tracked_tuple
        select_q = ScdType2History._select_current_query(
            target_table, key_tuple, tracked_tuple, current_flag_column
        )
        close_q = ScdType2History._close_out_query(
            target_table, key_tuple, valid_to_column, current_flag_column
        )
        insert_q = ScdType2History._insert_query(
            target_table, source_columns, valid_from_column, valid_to_column, current_flag_column
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
                    key_values + tracked_values + (now_iso, None, 1),
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
                key_values + tracked_values + (now_iso, None, 1),
            )
            rows_inserted += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_inserted": rows_inserted,
            "rows_closed": rows_closed,
        }
